"""Fixtures partagées par les tests backend.

Les tests tournent sur SQLite en mémoire : rapides, isolés, sans service externe.
Le schéma est créé depuis `Base.metadata`, pas via Alembic — les migrations sont
vérifiées séparément contre un vrai PostgreSQL (voir docs/ARCHITECTURE.md).

Les adresses de test utilisent le domaine `breastai.td` : `email-validator`
refuse les TLD à usage réservé (`.test`, `.local`, `.invalid`), qui feraient
échouer la validation Pydantic pour une raison sans rapport avec le test.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import rate_limit
from app.auth.roles import UserRole
from app.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.main import create_app
from app.models.patient import Patient
from app.models.user import User
from app.services import patient_service, user_service

# Mots de passe de test : au moins 12 caractères, comme l'impose la validation.
ADMIN_PASSWORD = "AdminBreastAI-2026"
DOCTOR_PASSWORD = "DocteurBreastAI-2026"


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch) -> None:
    """Chaque test écrit ses images dans son propre répertoire temporaire.

    Sans cela, les tests d'upload pollueraient le dossier `uploads/` du dépôt
    avec des fichiers qui survivraient à la session.
    """
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))


@pytest.fixture(autouse=True)
def disabled_rate_limiting() -> Iterator[None]:
    """Désactive la limitation de débit par défaut.

    Les tests d'authentification enchaînent bien plus de connexions que le quota
    réel ; ils échoueraient en 429 pour une raison sans rapport avec ce qu'ils
    vérifient. Le test dédié la réactive explicitement.
    """
    previous = rate_limit.limiter.enabled
    rate_limit.limiter.enabled = False
    rate_limit.reset()
    yield
    rate_limit.limiter.enabled = previous
    rate_limit.reset()


@pytest.fixture
def db_engine():
    """Moteur SQLite en mémoire, partagé par toutes les connexions du test.

    `StaticPool` est indispensable : sans lui, chaque connexion ouvrirait sa
    propre base vide et les données écrites disparaîtraient d'un appel à l'autre.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db(db_engine) -> Iterator[Session]:
    factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine, db) -> Iterator[TestClient]:
    """Client HTTP branché sur la base de test."""
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Comptes de test
# --------------------------------------------------------------------------- #


@pytest.fixture
def admin_user(db: Session) -> User:
    return user_service.create_user(
        db,
        email="admin@breastai.td",
        password=ADMIN_PASSWORD,
        full_name="Administrateur Test",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def doctor_user(db: Session) -> User:
    return user_service.create_user(
        db,
        email="medecin@breastai.td",
        password=DOCTOR_PASSWORD,
        full_name="Dr Test",
        role=UserRole.DOCTOR,
    )


@pytest.fixture
def researcher_user(db: Session) -> User:
    return user_service.create_user(
        db,
        email="chercheur@breastai.td",
        password=DOCTOR_PASSWORD,
        full_name="Chercheur Test",
        role=UserRole.RESEARCHER,
    )


@pytest.fixture
def patient(db: Session, doctor_user: User) -> Patient:
    return patient_service.create_patient(
        db,
        code="TCD-2026-0001",
        first_name="Amina",
        last_name="Ali",
        created_by_id=doctor_user.id,
    )


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    """Connecte un utilisateur et renvoie la réponse JSON de `/auth/login`."""
    response = client.post(
        f"{settings.api_v1_prefix}/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    tokens = login(client, email, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def admin_headers(client: TestClient, admin_user: User) -> dict[str, str]:
    return auth_headers(client, admin_user.email, ADMIN_PASSWORD)


@pytest.fixture
def doctor_headers(client: TestClient, doctor_user: User) -> dict[str, str]:
    return auth_headers(client, doctor_user.email, DOCTOR_PASSWORD)
