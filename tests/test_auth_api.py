"""Tests des endpoints d'authentification."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import create_password_reset_token
from app.config import settings
from app.models.audit_log import AuditAction, AuditLog
from app.models.user import User
from app.services import user_service
from tests.conftest import ADMIN_PASSWORD, DOCTOR_PASSWORD, auth_headers, login

PREFIX = settings.api_v1_prefix


# --------------------------------------------------------------------------- #
# Connexion
# --------------------------------------------------------------------------- #


def test_login_returns_token_pair(client: TestClient, doctor_user: User) -> None:
    body = login(client, doctor_user.email, DOCTOR_PASSWORD)

    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] == settings.access_token_expire_minutes * 60


def test_login_is_case_insensitive_on_email(client: TestClient, doctor_user: User) -> None:
    response = client.post(
        f"{PREFIX}/auth/login",
        data={"username": doctor_user.email.upper(), "password": DOCTOR_PASSWORD},
    )

    assert response.status_code == 200


def test_login_with_wrong_password_is_rejected(client: TestClient, doctor_user: User) -> None:
    response = client.post(
        f"{PREFIX}/auth/login",
        data={"username": doctor_user.email, "password": "mauvais-mot-de-passe"},
    )

    assert response.status_code == 401


def test_login_with_unknown_email_gives_the_same_error(client: TestClient) -> None:
    """Le message ne doit pas permettre de distinguer un compte existant."""
    response = client.post(
        f"{PREFIX}/auth/login",
        data={"username": "inconnu@breastai.td", "password": "peu-importe-1234"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Adresse e-mail ou mot de passe incorrect."


def test_deactivated_account_cannot_log_in(
    client: TestClient, db: Session, doctor_user: User
) -> None:
    user_service.set_active(db, doctor_user, False)

    response = client.post(
        f"{PREFIX}/auth/login",
        data={"username": doctor_user.email, "password": DOCTOR_PASSWORD},
    )

    assert response.status_code == 401


def test_login_updates_last_login(client: TestClient, db: Session, doctor_user: User) -> None:
    assert doctor_user.last_login_at is None

    login(client, doctor_user.email, DOCTOR_PASSWORD)
    db.refresh(doctor_user)

    assert doctor_user.last_login_at is not None


# --------------------------------------------------------------------------- #
# Profil et protection des routes
# --------------------------------------------------------------------------- #


def test_me_returns_profile_without_password(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.get(f"{PREFIX}/auth/me", headers=doctor_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "medecin@breastai.td"
    assert body["role"] == "doctor"
    assert "hashed_password" not in body
    assert "password" not in body


def test_me_works_for_an_internal_domain_account(client: TestClient, db: Session) -> None:
    """Un compte sur un domaine interne doit pouvoir lire son profil.

    `.local` est un domaine à usage réservé, refusé par `EmailStr`. Tant que les
    schémas de sortie le revalidaient, un tel compte — typique du réseau d'un
    établissement de soins, et créé tel quel par `init_db` — pouvait se
    connecter mais recevait un 500 sur `/auth/me`.
    """
    user_service.create_user(
        db,
        email="admin@hopital.local",
        password="MotDePasseInterne-2026",
        full_name="Admin Interne",
    )
    headers = auth_headers(client, "admin@hopital.local", "MotDePasseInterne-2026")

    response = client.get(f"{PREFIX}/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "admin@hopital.local"


def test_me_requires_a_token(client: TestClient) -> None:
    assert client.get(f"{PREFIX}/auth/me").status_code == 401


def test_me_rejects_a_garbage_token(client: TestClient) -> None:
    response = client.get(
        f"{PREFIX}/auth/me", headers={"Authorization": "Bearer pas-un-jeton"}
    )

    assert response.status_code == 401


def test_refresh_token_is_not_accepted_as_access_token(
    client: TestClient, doctor_user: User
) -> None:
    tokens = login(client, doctor_user.email, DOCTOR_PASSWORD)

    response = client.get(
        f"{PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )

    assert response.status_code == 401


def test_token_stops_working_once_account_is_deactivated(
    client: TestClient, db: Session, doctor_user: User, doctor_headers: dict[str, str]
) -> None:
    """Un jeton encore valide ne doit pas survivre à la désactivation du compte."""
    assert client.get(f"{PREFIX}/auth/me", headers=doctor_headers).status_code == 200

    user_service.set_active(db, doctor_user, False)

    assert client.get(f"{PREFIX}/auth/me", headers=doctor_headers).status_code == 401


# --------------------------------------------------------------------------- #
# Renouvellement et déconnexion
# --------------------------------------------------------------------------- #


def test_refresh_issues_a_usable_access_token(client: TestClient, doctor_user: User) -> None:
    tokens = login(client, doctor_user.email, DOCTOR_PASSWORD)

    response = client.post(
        f"{PREFIX}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 200
    new_access = response.json()["access_token"]
    assert (
        client.get(
            f"{PREFIX}/auth/me", headers={"Authorization": f"Bearer {new_access}"}
        ).status_code
        == 200
    )


def test_access_token_is_not_accepted_for_refresh(client: TestClient, doctor_user: User) -> None:
    tokens = login(client, doctor_user.email, DOCTOR_PASSWORD)

    response = client.post(
        f"{PREFIX}/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )

    assert response.status_code == 401


def test_logout_requires_authentication(client: TestClient) -> None:
    assert client.post(f"{PREFIX}/auth/logout").status_code == 401


def test_logout_is_recorded(
    client: TestClient, db: Session, doctor_headers: dict[str, str]
) -> None:
    assert client.post(f"{PREFIX}/auth/logout", headers=doctor_headers).status_code == 200

    actions = set(db.scalars(select(AuditLog.action)))
    assert AuditAction.LOGOUT.value in actions


# --------------------------------------------------------------------------- #
# Mot de passe
# --------------------------------------------------------------------------- #


def test_password_change_invalidates_previous_tokens(
    client: TestClient, doctor_user: User, doctor_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{PREFIX}/auth/password/change",
        headers=doctor_headers,
        json={
            "current_password": DOCTOR_PASSWORD,
            "new_password": "NouveauMotDePasse-2026",
        },
    )
    assert response.status_code == 200

    # Le jeton émis avant le changement ne doit plus ouvrir aucune porte.
    assert client.get(f"{PREFIX}/auth/me", headers=doctor_headers).status_code == 401
    # Et le nouveau mot de passe fonctionne.
    login(client, doctor_user.email, "NouveauMotDePasse-2026")


def test_password_change_requires_the_current_password(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{PREFIX}/auth/password/change",
        headers=doctor_headers,
        json={"current_password": "faux-mot-de-passe", "new_password": "PeuImporte-2026"},
    )

    assert response.status_code == 400


def test_password_change_refuses_a_short_password(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{PREFIX}/auth/password/change",
        headers=doctor_headers,
        json={"current_password": DOCTOR_PASSWORD, "new_password": "court"},
    )

    assert response.status_code == 422


def test_reset_request_answers_the_same_for_unknown_email(client: TestClient) -> None:
    """Réponse identique dans tous les cas : sinon on énumère les comptes."""
    response = client.post(
        f"{PREFIX}/auth/password-reset/request", json={"email": "inconnu@breastai.td"}
    )

    assert response.status_code == 200
    assert "Si un compte existe" in response.json()["message"]


def test_reset_request_never_returns_the_token(client: TestClient, doctor_user: User) -> None:
    response = client.post(
        f"{PREFIX}/auth/password-reset/request", json={"email": doctor_user.email}
    )

    assert response.status_code == 200
    assert set(response.json()) == {"message"}


def test_reset_confirm_sets_the_new_password(client: TestClient, doctor_user: User) -> None:
    token = create_password_reset_token(str(doctor_user.id), doctor_user.password_changed_at)

    response = client.post(
        f"{PREFIX}/auth/password-reset/confirm",
        json={"token": token, "new_password": "MotDePasseReinitialise-2026"},
    )

    assert response.status_code == 200
    login(client, doctor_user.email, "MotDePasseReinitialise-2026")


def test_reset_token_works_only_once(client: TestClient, doctor_user: User) -> None:
    """Le jeton porte l'horodatage du mot de passe : il périme dès qu'on l'utilise."""
    token = create_password_reset_token(str(doctor_user.id), doctor_user.password_changed_at)

    first = client.post(
        f"{PREFIX}/auth/password-reset/confirm",
        json={"token": token, "new_password": "PremierePasse-2026"},
    )
    assert first.status_code == 200

    second = client.post(
        f"{PREFIX}/auth/password-reset/confirm",
        json={"token": token, "new_password": "SecondePasse-2026"},
    )
    assert second.status_code == 400


def test_reset_confirm_rejects_an_access_token(client: TestClient, doctor_user: User) -> None:
    tokens = login(client, doctor_user.email, DOCTOR_PASSWORD)

    response = client.post(
        f"{PREFIX}/auth/password-reset/confirm",
        json={"token": tokens["access_token"], "new_password": "PeuImporte-2026"},
    )

    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Journalisation
# --------------------------------------------------------------------------- #


def test_successful_login_is_audited(
    client: TestClient, db: Session, doctor_user: User
) -> None:
    login(client, doctor_user.email, DOCTOR_PASSWORD)

    entry = db.scalar(
        select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_SUCCESS.value)
    )
    assert entry is not None
    assert entry.user_id == doctor_user.id


def test_failed_login_is_audited(client: TestClient, db: Session, doctor_user: User) -> None:
    client.post(
        f"{PREFIX}/auth/login",
        data={"username": doctor_user.email, "password": "mauvais-mot-de-passe"},
    )

    entry = db.scalar(
        select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_FAILURE.value)
    )
    assert entry is not None


def test_admin_can_log_in(client: TestClient, admin_user: User) -> None:
    body = login(client, admin_user.email, ADMIN_PASSWORD)

    assert body["access_token"]
