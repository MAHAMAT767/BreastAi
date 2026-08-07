"""Tests de la limitation de débit sur les endpoints d'authentification."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.auth import rate_limit
from app.config import settings
from app.models.user import User
from tests.conftest import DOCTOR_PASSWORD

PREFIX = settings.api_v1_prefix


@pytest.fixture
def enabled_rate_limiting() -> Iterator[None]:
    """Réactive le limiteur, que la fixture globale désactive pour les autres tests."""
    rate_limit.limiter.enabled = True
    rate_limit.reset()
    yield
    rate_limit.limiter.enabled = False
    rate_limit.reset()


def attempt_login(client: TestClient, email: str, password: str):
    return client.post(
        f"{PREFIX}/auth/login", data={"username": email, "password": password}
    )


def test_repeated_failed_logins_are_throttled(
    client: TestClient, doctor_user: User, enabled_rate_limiting: None
) -> None:
    """Sans quota, une attaque par force brute n'a aucune limite côté serveur."""
    del enabled_rate_limiting
    statuses = [
        attempt_login(client, doctor_user.email, "mauvais-mot-de-passe").status_code
        for _ in range(15)
    ]

    assert 429 in statuses
    # Le quota par défaut est de 10 par minute : les premières tentatives passent.
    assert statuses[0] == 401


def test_throttled_response_is_explicit_but_vague(
    client: TestClient, doctor_user: User, enabled_rate_limiting: None
) -> None:
    del enabled_rate_limiting
    response = None
    for _ in range(15):
        response = attempt_login(client, doctor_user.email, "mauvais-mot-de-passe")
        if response.status_code == 429:
            break

    assert response is not None
    assert response.status_code == 429
    assert "Trop de tentatives" in response.json()["detail"]


def test_valid_credentials_are_also_throttled(
    client: TestClient, doctor_user: User, enabled_rate_limiting: None
) -> None:
    """Le quota porte sur l'endpoint, pas seulement sur les échecs.

    Compter uniquement les échecs laisserait un attaquant sonder indéfiniment
    dès qu'il a trouvé un mot de passe valide.
    """
    del enabled_rate_limiting
    statuses = [
        attempt_login(client, doctor_user.email, DOCTOR_PASSWORD).status_code
        for _ in range(15)
    ]

    assert statuses[0] == 200
    assert 429 in statuses


def test_password_reset_requests_are_throttled(
    client: TestClient, enabled_rate_limiting: None
) -> None:
    del enabled_rate_limiting
    statuses = [
        client.post(
            f"{PREFIX}/auth/password-reset/request", json={"email": "quelquun@breastai.td"}
        ).status_code
        for _ in range(10)
    ]

    assert 429 in statuses


def test_rate_limiting_is_disabled_by_default_in_tests(
    client: TestClient, doctor_user: User
) -> None:
    """Garde-fou : si la fixture globale cessait d'agir, les tests d'auth casseraient."""
    statuses = [
        attempt_login(client, doctor_user.email, DOCTOR_PASSWORD).status_code
        for _ in range(15)
    ]

    assert 429 not in statuses
