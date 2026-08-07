"""Configuration centralisée de l'application, chargée depuis l'environnement."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres de l'application.

    Les valeurs sont lues depuis les variables d'environnement, puis depuis un
    fichier `.env` à la racine du dépôt. Toute valeur sensible doit venir de
    l'environnement en production — jamais du code.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- Application ----------
    app_name: str = "BreastAI"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # ---------- Base de données ----------
    postgres_user: str = "breastai"
    postgres_password: str = "breastai"
    postgres_db: str = "breastai"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str | None = None

    # ---------- Sécurité (utilisé en Phase 2) ----------
    secret_key: str = "dev-only-insecure-secret-key-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ---------- CORS ----------
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # ---------- Stockage (Phase 3) ----------
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50

    # ---------- IA (Phase 4) ----------
    model_path: str = "./models/breastai_efficientnet.pt"
    model_device: str = "cpu"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Accepte `CORS_ORIGINS=a,b,c` en plus d'une liste JSON."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def sqlalchemy_url(self) -> str:
        """URL de connexion PostgreSQL, dérivée des composants si non fournie."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Instance unique de configuration (mise en cache pour l'injection FastAPI)."""
    return Settings()


settings = get_settings()
