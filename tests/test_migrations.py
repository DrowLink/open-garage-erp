from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from open_garage_erp.app import create_app
from open_garage_erp.config import Settings


def test_initial_migration_creates_mvp_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    tables = set(inspect(create_engine(f"sqlite:///{database_path}")).get_table_names())
    assert {"alembic_version", "customers", "vehicles", "repair_orders"} <= tables


def test_user_migration_creates_shop_scoped_auth_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "users.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path}"))
    assert {"shops", "users"} <= set(inspector.get_table_names())
    assert {column["name"] for column in inspector.get_columns("users")} == {
        "id",
        "shop_id",
        "email",
        "display_name",
        "password_hash",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert inspector.get_foreign_keys("users") == [
        {
            "name": None,
            "constrained_columns": ["shop_id"],
            "referred_schema": None,
            "referred_table": "shops",
            "referred_columns": ["id"],
            "options": {"ondelete": "RESTRICT"},
        }
    ]
    user_unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("users")
    }
    assert user_unique_columns == {("shop_id", "email")}


def test_migration_round_trip_returns_to_empty_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "round-trip.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    tables = set(inspect(create_engine(f"sqlite:///{database_path}")).get_table_names())
    assert not ({"customers", "vehicles", "repair_orders"} & tables)


def test_create_app_does_not_create_unversioned_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "application.db"

    create_app(Settings(database_url=f"sqlite:///{database_path}"))

    assert inspect(create_engine(f"sqlite:///{database_path}")).get_table_names() == []


def test_explicit_alembic_url_takes_precedence_over_environment(
    tmp_path: Path, monkeypatch
) -> None:
    explicit_path = tmp_path / "explicit.db"
    ambient_path = tmp_path / "ambient.db"
    monkeypatch.setenv("OPEN_GARAGE_DATABASE_URL", f"sqlite:///{ambient_path}")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{explicit_path}")

    command.upgrade(config, "head")

    assert "customers" in inspect(create_engine(f"sqlite:///{explicit_path}")).get_table_names()
    assert not ambient_path.exists()


def test_explicit_default_alembic_url_still_takes_precedence_over_environment(
    tmp_path: Path, monkeypatch
) -> None:
    ambient_path = tmp_path / "ambient.db"
    explicit_path = tmp_path / "data/open-garage.db"
    explicit_path.parent.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPEN_GARAGE_DATABASE_URL", f"sqlite:///{ambient_path}")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", "sqlite:///./data/open-garage.db")

    command.upgrade(config, "head")

    assert "customers" in inspect(create_engine(f"sqlite:///{explicit_path}")).get_table_names()
    assert not ambient_path.exists()


def test_default_alembic_config_accepts_environment_database_url(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "environment.db"
    monkeypatch.setenv("OPEN_GARAGE_DATABASE_URL", f"sqlite:///{database_path}")

    command.upgrade(Config("alembic.ini"), "head")

    assert "customers" in inspect(create_engine(f"sqlite:///{database_path}")).get_table_names()


def test_initial_migration_adds_domain_check_constraints(tmp_path: Path) -> None:
    database_path = tmp_path / "constraints.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")
    inspector = inspect(create_engine(f"sqlite:///{database_path}"))

    vehicle_checks = {check["name"] for check in inspector.get_check_constraints("vehicles")}
    repair_order_checks = {
        check["name"] for check in inspector.get_check_constraints("repair_orders")
    }

    assert vehicle_checks == {"ck_vehicles_year_range"}
    assert repair_order_checks == {
        "ck_repair_orders_estimate_nonnegative",
        "ck_repair_orders_status",
    }


def test_database_rejects_values_outside_domain_constraints(tmp_path: Path) -> None:
    database_path = tmp_path / "constraint-enforcement.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO customers (id, name, created_at, updated_at) "
                "VALUES (1, 'Owner', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO vehicles "
                "(id, customer_id, year, make, model, created_at, updated_at) "
                "VALUES (1, 1, 1885, 'Old', 'Car', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO vehicles "
                "(id, customer_id, year, make, model, created_at, updated_at) "
                "VALUES (1, 1, 2020, 'Safe', 'Car', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )

    for estimate_cents, order_status in [(-1, "draft"), (0, "unknown")]:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO repair_orders "
                    "(vehicle_id, description, estimate_cents, status, created_at, updated_at) "
                    "VALUES (1, 'Invalid', :estimate_cents, :status, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"estimate_cents": estimate_cents, "status": order_status},
            )
