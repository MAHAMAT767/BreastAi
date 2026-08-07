"""Tests de la gestion des comptes et du contrôle des rôles."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.models.user import User
from tests.conftest import DOCTOR_PASSWORD, auth_headers

PREFIX = settings.api_v1_prefix

NEW_USER = {
    "email": "nouveau@breastai.td",
    "full_name": "Dr Nouveau",
    "role": "doctor",
    "password": "MotDePasseNouveau-2026",
}


def test_admin_can_create_a_user(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(f"{PREFIX}/users", headers=admin_headers, json=NEW_USER)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == NEW_USER["email"]
    assert body["role"] == "doctor"
    assert "hashed_password" not in body


def test_created_user_can_log_in(client: TestClient, admin_headers: dict[str, str]) -> None:
    client.post(f"{PREFIX}/users", headers=admin_headers, json=NEW_USER)

    auth_headers(client, NEW_USER["email"], NEW_USER["password"])


def test_doctor_cannot_create_a_user(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.post(f"{PREFIX}/users", headers=doctor_headers, json=NEW_USER)

    assert response.status_code == 403


def test_researcher_cannot_list_users(client: TestClient, researcher_user: User) -> None:
    headers = auth_headers(client, researcher_user.email, DOCTOR_PASSWORD)

    assert client.get(f"{PREFIX}/users", headers=headers).status_code == 403


def test_anonymous_cannot_list_users(client: TestClient) -> None:
    assert client.get(f"{PREFIX}/users").status_code == 401


def test_duplicate_email_is_refused(client: TestClient, admin_headers: dict[str, str]) -> None:
    client.post(f"{PREFIX}/users", headers=admin_headers, json=NEW_USER)
    second = client.post(f"{PREFIX}/users", headers=admin_headers, json=NEW_USER)

    assert second.status_code == 409


def test_weak_password_is_refused(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        f"{PREFIX}/users", headers=admin_headers, json={**NEW_USER, "password": "1234"}
    )

    assert response.status_code == 422


def test_invalid_email_is_refused(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        f"{PREFIX}/users", headers=admin_headers, json={**NEW_USER, "email": "pas-un-email"}
    )

    assert response.status_code == 422


def test_unknown_role_is_refused(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        f"{PREFIX}/users", headers=admin_headers, json={**NEW_USER, "role": "chef"}
    )

    assert response.status_code == 422


def test_admin_can_list_users(
    client: TestClient, admin_headers: dict[str, str], doctor_user: User
) -> None:
    response = client.get(f"{PREFIX}/users", headers=admin_headers)

    assert response.status_code == 200
    emails = {user["email"] for user in response.json()}
    assert doctor_user.email in emails


def test_admin_can_deactivate_another_user(
    client: TestClient, admin_headers: dict[str, str], doctor_user: User
) -> None:
    response = client.patch(
        f"{PREFIX}/users/{doctor_user.id}", headers=admin_headers, json={"is_active": False}
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_admin_cannot_deactivate_themselves(
    client: TestClient, admin_headers: dict[str, str], admin_user: User
) -> None:
    """Sinon la plateforme peut se retrouver sans administrateur actif."""
    response = client.patch(
        f"{PREFIX}/users/{admin_user.id}", headers=admin_headers, json={"is_active": False}
    )

    assert response.status_code == 400


def test_admin_cannot_downgrade_their_own_role(
    client: TestClient, admin_headers: dict[str, str], admin_user: User
) -> None:
    response = client.patch(
        f"{PREFIX}/users/{admin_user.id}", headers=admin_headers, json={"role": "doctor"}
    )

    assert response.status_code == 400


def test_unknown_user_returns_404(client: TestClient, admin_headers: dict[str, str]) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"

    assert client.get(f"{PREFIX}/users/{unknown}", headers=admin_headers).status_code == 404
