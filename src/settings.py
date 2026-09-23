from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_db: str = "orchestrator"
    postgres_user: str = "orchestrator"
    postgres_password: str = "orchestrator"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    app_port: int = 8000

    database_url: str = (
        "postgresql+psycopg://orchestrator:orchestrator@localhost:5432/orchestrator"
    )

    @property
    def postgres_dsn(self) -> str:
        """Строка подключения SQLAlchemy к Postgres."""

        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
