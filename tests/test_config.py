"""Tests de la configuration applicative."""

from __future__ import annotations

from app.config import Settings


def test_sqlalchemy_url_is_built_from_components() -> None:
    settings = Settings(
        database_url=None,
        postgres_user="u",
        postgres_password="p",
        postgres_host="db",
        postgres_port=5432,
        postgres_db="breastai",
    )

    assert settings.sqlalchemy_url == "postgresql+psycopg://u:p@db:5432/breastai"


def test_explicit_database_url_takes_precedence() -> None:
    settings = Settings(database_url="postgresql+psycopg://x:y@host:5555/other")

    assert settings.sqlalchemy_url == "postgresql+psycopg://x:y@host:5555/other"


def test_cors_origins_accept_comma_separated_string() -> None:
    """`CORS_ORIGINS` est fourni en CSV dans .env : le validateur doit le découper."""
    settings = Settings(cors_origins="http://a.test, http://b.test")

    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_is_production_flag() -> None:
    assert Settings(environment="production").is_production is True
    assert Settings(environment="development").is_production is False
