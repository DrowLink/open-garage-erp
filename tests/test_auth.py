from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from open_garage_erp import models
from open_garage_erp.database import build_session_factory
from open_garage_erp.models import LoginAttempt, SessionToken, Shop, User, utc_now
from open_garage_erp.security import DUMMY_PASSWORD_HASH, hash_password


def test_user_roles_define_shop_responsibilities() -> None:
    assert set(models.UserRole) == {
        models.UserRole.OWNER,
        models.UserRole.SERVICE_ADVISOR,
        models.UserRole.TECHNICIAN,
        models.UserRole.ACCOUNTANT,
    }
    assert {role.value for role in models.UserRole} == {
        "owner",
        "service_advisor",
        "technician",
        "accountant",
    }


def test_login_runs_password_verification_for_unknown_user(client, monkeypatch) -> None:
    verification_calls = 0

    def record_verification(_password: str, _password_hash: str) -> bool:
        nonlocal verification_calls
        verification_calls += 1
        return False

    monkeypatch.setattr("open_garage_erp.app.verify_password", record_verification)

    response = client.post(
        "/api/auth/login",
        json={"shop_id": 999, "email": "unknown@example.com", "password": "guess"},
    )

    assert response.status_code == 401
    assert verification_calls == 1


def test_login_unauthorized_response_advertises_bearer_authentication(client) -> None:
    response = client.post(
        "/api/auth/login",
        json={"shop_id": 999, "email": "unknown@example.com", "password": "guess"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_verifies_inactive_user_password_against_dummy_hash(client, monkeypatch) -> None:
    user = create_user(client)
    session_factory = build_session_factory(client.app.state.database_url)
    with session_factory() as session:
        stored_user = session.get(User, user.id)
        stored_user.is_active = False
        session.commit()

    verified_hashes = []

    def record_verification(_password: str, password_hash: str) -> bool:
        verified_hashes.append(password_hash)
        return False

    monkeypatch.setattr("open_garage_erp.app.verify_password", record_verification)

    response = client.post(
        "/api/auth/login",
        json={"shop_id": user.shop_id, "email": user.email, "password": "guess"},
    )

    assert response.status_code == 401
    assert verified_hashes == [DUMMY_PASSWORD_HASH]


def create_user(client, *, password: str = "correct horse battery staple") -> User:
    session_factory = build_session_factory(client.app.state.database_url)
    with session_factory() as session:
        shop = Shop(name="Honest Auto")
        session.add(shop)
        session.flush()
        user = User(
            shop_id=shop.id,
            email="owner@example.com",
            display_name="Owner",
            password_hash=hash_password(password),
            role=models.UserRole.OWNER,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


def test_explicit_user_role_reloads_as_enum(client) -> None:
    user = create_user(client)
    session_factory = build_session_factory(client.app.state.database_url)

    with session_factory() as session:
        reloaded_user = session.get(User, user.id)

        assert reloaded_user is not None
        assert reloaded_user.role is models.UserRole.OWNER
        assert type(reloaded_user.role) is models.UserRole


def test_orm_user_creation_requires_explicit_role(client) -> None:
    session_factory = build_session_factory(client.app.state.database_url)
    with session_factory() as session:
        shop = Shop(name="Honest Auto")
        session.add(shop)
        session.flush()
        session.add(
            User(
                shop_id=shop.id,
                email="unspecified@example.com",
                display_name="Unspecified",
                password_hash="hash",
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_login_with_valid_credentials_returns_bearer_session_token(client) -> None:
    user = create_user(client)

    response = client.post(
        "/api/auth/login",
        json={
            "shop_id": user.shop_id,
            "email": user.email,
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) >= 32
    assert body["expires_at"].endswith("Z")


def test_owner_check_requires_bearer_credentials(client) -> None:
    response = client.get("/api/auth/owner-check")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "invalid_session",
            "message": "Session token is invalid or expired",
            "details": None,
        }
    }


def test_owner_check_rejects_unknown_bearer_token(client) -> None:
    response = client.get(
        "/api/auth/owner-check",
        headers={"Authorization": "Bearer not-a-valid-session-token"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "invalid_session"


def test_owner_check_allows_owner_session(client) -> None:
    user = create_user(client)
    login_response = client.post(
        "/api/auth/login",
        json={
            "shop_id": user.shop_id,
            "email": user.email,
            "password": "correct horse battery staple",
        },
    )

    response = client.get(
        "/api/auth/owner-check",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "authorized"}


def test_owner_check_forbids_technician_session(client) -> None:
    user = create_user(client)
    session_factory = build_session_factory(client.app.state.database_url)
    with session_factory() as session:
        stored_user = session.get(User, user.id)
        stored_user.role = models.UserRole.TECHNICIAN
        session.commit()

    login_response = client.post(
        "/api/auth/login",
        json={
            "shop_id": user.shop_id,
            "email": user.email,
            "password": "correct horse battery staple",
        },
    )

    response = client.get(
        "/api/auth/owner-check",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "insufficient_role",
            "message": "Owner role required",
            "details": None,
        }
    }


def test_logout_rejects_unknown_bearer_token(client) -> None:
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": "Bearer not-a-valid-session-token"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "invalid_session",
            "message": "Session token is invalid or expired",
            "details": None,
        }
    }


def test_logout_revokes_the_current_session_token(client) -> None:
    user = create_user(client)
    login_response = client.post(
        "/api/auth/login",
        json={
            "shop_id": user.shop_id,
            "email": user.email,
            "password": "correct horse battery staple",
        },
    )
    authorization = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.post("/api/auth/logout", headers=authorization)

    assert response.status_code == 204
    assert response.content == b""
    assert client.post("/api/auth/logout", headers=authorization).status_code == 401


def test_login_rate_limits_repeated_failures(client) -> None:
    user = create_user(client)
    credentials = {
        "shop_id": user.shop_id,
        "email": user.email,
        "password": "wrong password",
    }

    for _ in range(5):
        assert client.post("/api/auth/login", json=credentials).status_code == 401

    response = client.post("/api/auth/login", json=credentials)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"
    assert response.json()["error"]["code"] == "login_rate_limited"


def test_locked_identity_is_rejected_without_password_verification(client, monkeypatch) -> None:
    user = create_user(client)
    session_factory = build_session_factory(client.app.state.database_url)
    with session_factory() as session:
        session.add(
            LoginAttempt(
                shop_id=user.shop_id,
                email=user.email,
                failed_attempts=5,
                locked_until=utc_now() + timedelta(minutes=15),
            )
        )
        session.commit()

    def unexpected_verification(_password: str, _password_hash: str) -> bool:
        pytest.fail("locked identities must not run password verification")
        return False

    monkeypatch.setattr("open_garage_erp.app.verify_password", unexpected_verification)
    response = client.post(
        "/api/auth/login",
        json={"shop_id": user.shop_id, "email": user.email, "password": "guess"},
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "login_rate_limited"


def test_login_rate_limits_repeated_failures_for_unknown_accounts(client) -> None:
    credentials = {
        "shop_id": 999,
        "email": "unknown@example.com",
        "password": "wrong password",
    }

    for _ in range(5):
        assert client.post("/api/auth/login", json=credentials).status_code == 401

    response = client.post("/api/auth/login", json=credentials)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"
    assert response.json()["error"]["code"] == "login_rate_limited"


def test_login_attempt_storage_is_capped_for_arbitrary_unknown_identities(
    client, monkeypatch
) -> None:
    monkeypatch.setattr("open_garage_erp.app.MAX_LOGIN_ATTEMPT_ROWS", 2)

    statuses = []
    for identity in range(3):
        response = client.post(
            "/api/auth/login",
            json={
                "shop_id": 999,
                "email": f"unknown-{identity}@example.com",
                "password": "wrong password",
            },
        )
        statuses.append(response.status_code)

    assert statuses == [401, 401, 503]
    session_factory = build_session_factory(client.app.state.database_url)
    with session_factory() as session:
        assert session.query(LoginAttempt).count() == 2


def test_login_attempt_cap_does_not_evict_an_active_lock(client, monkeypatch) -> None:
    monkeypatch.setattr("open_garage_erp.app.MAX_LOGIN_ATTEMPT_ROWS", 1)
    session_factory = build_session_factory(client.app.state.database_url)
    locked_until = utc_now() + timedelta(minutes=15)
    with session_factory() as session:
        session.add(
            LoginAttempt(
                shop_id=1,
                email="locked@example.com",
                failed_attempts=5,
                locked_until=locked_until,
            )
        )
        session.commit()

    response = client.post(
        "/api/auth/login",
        json={"shop_id": 999, "email": "unknown@example.com", "password": "guess"},
    )

    assert response.status_code == 503
    with session_factory() as session:
        attempt = session.get(LoginAttempt, (1, "locked@example.com"))
        assert attempt is not None
        assert attempt.locked_until == locked_until


def test_login_attempt_cap_rechecks_capacity_when_stale_identity_is_reinserted(
    client, monkeypatch
) -> None:
    monkeypatch.setattr("open_garage_erp.app.MAX_LOGIN_ATTEMPT_ROWS", 1)
    session_factory = build_session_factory(client.app.state.database_url)
    stale_identity = (999, "stale@example.com")
    with session_factory() as session:
        session.add(
            LoginAttempt(
                shop_id=stale_identity[0],
                email=stale_identity[1],
                failed_attempts=1,
                locked_until=None,
            )
        )
        session.commit()

    verification_started = Event()
    capacity_reused = Event()

    def wait_while_capacity_is_reused(_password: str, _password_hash: str) -> bool:
        verification_started.set()
        assert capacity_reused.wait(timeout=5)
        return False

    monkeypatch.setattr("open_garage_erp.app.verify_password", wait_while_capacity_is_reused)
    with ThreadPoolExecutor(max_workers=1) as executor:
        response_future = executor.submit(
            client.post,
            "/api/auth/login",
            json={
                "shop_id": stale_identity[0],
                "email": stale_identity[1],
                "password": "wrong",
            },
        )
        assert verification_started.wait(timeout=5)
        with session_factory() as session:
            stale_attempt = session.get(LoginAttempt, stale_identity)
            assert stale_attempt is not None
            session.delete(stale_attempt)
            session.add(
                LoginAttempt(
                    shop_id=999,
                    email="replacement@example.com",
                    failed_attempts=1,
                    locked_until=None,
                )
            )
            session.commit()
        capacity_reused.set()
        response = response_future.result(timeout=5)

    assert response.status_code == 503
    with session_factory() as session:
        assert session.query(LoginAttempt).count() == 1
        assert session.get(LoginAttempt, (999, "replacement@example.com")) is not None


def test_login_fails_closed_when_rate_limit_lookup_has_database_error(
    client, monkeypatch
) -> None:
    original_get = Session.get

    def fail_login_attempt_lookup(self, entity, ident, **kwargs):
        if entity is LoginAttempt:
            raise OperationalError("SELECT login_attempts", {}, Exception("database offline"))
        return original_get(self, entity, ident, **kwargs)

    monkeypatch.setattr(Session, "get", fail_login_attempt_lookup)
    response = client.post(
        "/api/auth/login",
        json={"shop_id": 999, "email": "unknown@example.com", "password": "guess"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "authentication_unavailable",
            "message": "Authentication service is temporarily unavailable",
            "details": None,
        }
    }


def test_login_fails_closed_when_rate_limit_update_has_database_error(
    client, monkeypatch
) -> None:
    original_execute = Session.execute

    def fail_login_attempt_update(self, statement, *args, **kwargs):
        if statement.__class__.__name__ == "Insert":
            raise OperationalError("INSERT login_attempts", {}, Exception("database offline"))
        return original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", fail_login_attempt_update)
    response = client.post(
        "/api/auth/login",
        json={"shop_id": 999, "email": "unknown@example.com", "password": "guess"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "authentication_unavailable"


def test_concurrent_login_failures_are_counted_atomically(client, monkeypatch) -> None:
    user = create_user(client)
    credentials = {
        "shop_id": user.shop_id,
        "email": user.email,
        "password": "wrong password",
    }
    verification_barrier = Barrier(2)

    def fail_together(_password: str, _password_hash: str) -> bool:
        verification_barrier.wait()
        return False

    monkeypatch.setattr("open_garage_erp.app.verify_password", fail_together)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda _: client.post("/api/auth/login", json=credentials), range(2))
        )

    assert [response.status_code for response in responses] == [401, 401]
    session_factory = build_session_factory(client.app.state.database_url)
    with session_factory() as session:
        assert session.query(LoginAttempt).one().failed_attempts == 2


def test_concurrent_threshold_failure_prevents_success_from_clearing_lock(
    client, monkeypatch
) -> None:
    password = "correct horse battery staple"
    user = create_user(client, password=password)
    session_factory = build_session_factory(client.app.state.database_url)
    with session_factory() as session:
        session.add(
            LoginAttempt(
                shop_id=user.shop_id,
                email=user.email,
                failed_attempts=4,
                locked_until=None,
            )
        )
        session.commit()

    success_verifying = Event()
    failure_committed = Event()

    def coordinate_verification(candidate: str, _password_hash: str) -> bool:
        if candidate == password:
            success_verifying.set()
            assert failure_committed.wait(timeout=5)
            return True
        return False

    def submit_failure():
        response = client.post(
            "/api/auth/login",
            json={"shop_id": user.shop_id, "email": user.email, "password": "wrong"},
        )
        failure_committed.set()
        return response

    monkeypatch.setattr("open_garage_erp.app.verify_password", coordinate_verification)
    with ThreadPoolExecutor(max_workers=2) as executor:
        success_future = executor.submit(
            client.post,
            "/api/auth/login",
            json={"shop_id": user.shop_id, "email": user.email, "password": password},
        )
        assert success_verifying.wait(timeout=5)
        failure_response = executor.submit(submit_failure).result(timeout=5)
        success_response = success_future.result(timeout=5)

    assert failure_response.status_code == 401
    assert success_response.status_code == 429
    with session_factory() as session:
        attempt = session.get(LoginAttempt, (user.shop_id, user.email))
        assert attempt is not None
        assert attempt.locked_until is not None
        assert attempt.locked_until > utc_now()
        assert session.query(SessionToken).count() == 0
