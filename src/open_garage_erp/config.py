from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(env_prefix="OPEN_GARAGE_", env_file=".env", extra="ignore")

    database_url: str = Field(default="sqlite:///./data/open-garage.db")
    app_name: str = "Open Garage ERP"
    debug: bool = False

    @field_validator("database_url")
    @classmethod
    def require_sqlite(cls, value: str) -> str:
        if not value.startswith("sqlite:///"):
            raise ValueError("The MVP supports SQLite database URLs only")
        parsed_url = make_url(value)
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
