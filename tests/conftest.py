from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    from open_garage_erp.app import create_app
    from open_garage_erp.config import Settings

    database_path = tmp_path / "test.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")
    app = create_app(Settings(database_url=f"sqlite:///{database_path}"))
    with TestClient(app) as test_client:
        yield test_client
