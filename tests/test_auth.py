from open_garage_erp.database import build_session_factory
from open_garage_erp.models import Shop, User
from open_garage_erp.security import DUMMY_PASSWORD_HASH, hash_password


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
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


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
