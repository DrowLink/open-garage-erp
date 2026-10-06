from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(env_prefix="OPEN_GARAGE_", env_file=".env", extra="ignore")

    database_url: str = Field(default="sqlite:///./data/open-garage.db")
    app_name: str = "Open Garage ERP"
    debug: bool = False

    @field_validator("database_url")
    @classmethod
    def require_sqlite(cls, value: str) -> str:
        try:
            parsed_url = make_url(value)
        except ArgumentError as exc:
            raise ValueError("Database URL must be a valid SQLAlchemy database URL") from exc
        if parsed_url.get_backend_name() != "sqlite":
            raise ValueError("The MVP supports SQLite database URLs only")
        database_path = parsed_url.database
        if database_path is None or not database_path.strip():
            raise ValueError("SQLite database URL must include a database path")
        if (
            database_path.casefold() == ":memory:"
            or database_path.casefold().startswith("file:")
            or parsed_url.query
        ):
            raise ValueError("The MVP requires file-backed SQLite storage without URI options")
        return value

    def ensure_local_database_directory(self) -> None:
        database_path = make_url(self.database_url).database
        if database_path is not None:
            path = Path(database_path)
            if path.parent != Path("."):
                path.parent.mkdir(parents=True, exist_ok=True)
