"""Configuration centralisée de l'application, chargée depuis l'environnement."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    # ---------- Sécurité ----------
    secret_key: str = "dev-only-insecure-secret-key-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_reset_token_expire_minutes: int = 30

    # ---------- Limitation de débit ----------
    #: Désactivable pour les tests. Le stockage est en mémoire, par processus :
    #: voir la réserve multi-instance dans app/auth/rate_limit.py.
    rate_limit_enabled: bool = True
    login_rate_limit: str = "10/minute"
    password_reset_rate_limit: str = "5/minute"
    #: Chaque question à l'assistant consomme du crédit chez le fournisseur :
    #: le quota est ici une protection budgétaire autant qu'une protection
    #: contre les abus.
    assistant_rate_limit: str = "10/minute"

    # ---------- Assistant conversationnel (Phase 7) ----------
    #: Sans jeton, l'assistant est désactivé et l'API le dit explicitement
    #: plutôt que d'échouer à l'appel.
    huggingface_api_token: str | None = None
    assistant_base_url: str = "https://router.huggingface.co/v1"
    assistant_model: str = "Qwen/Qwen2.5-7B-Instruct"
    assistant_max_tokens: int = 400
    assistant_temperature: float = 0.2
    assistant_timeout_seconds: float = 45.0
    #: Nombre de tours conservés dans l'historique envoyé au modèle. Chaque tour
    #: est refacturé à chaque question : au-delà, le coût grimpe sans que la
    #: réponse s'améliore.
    assistant_history_turns: int = 6

    # ---------- Compte administrateur initial ----------
    # Utilisé une seule fois par `python -m app.database.init_db`.
    first_admin_email: str | None = None
    first_admin_password: str | None = None
    first_admin_name: str = "Administrateur BreastAI"

    # ---------- CORS ----------
    #: `NoDecode` désactive le décodage JSON que pydantic-settings applique par
    #: défaut aux champs de type complexe lus depuis l'environnement. Sans lui,
    #: la valeur `CORS_ORIGINS=a,b` — celle que documente .env.example — fait
    #: échouer le démarrage avant même que le validateur ci-dessous ne s'exécute.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

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
    def assistant_enabled(self) -> bool:
        return bool(self.huggingface_api_token)

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
