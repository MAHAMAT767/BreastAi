"""Moteur SQLAlchemy et dépendance de session FastAPI."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,  # recycle les connexions coupées par le réseau
    echo=settings.debug and not settings.is_production,
    future=True,
)

session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Iterator[Session]:
    """Dépendance FastAPI : ouvre une session et la referme systématiquement."""
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
