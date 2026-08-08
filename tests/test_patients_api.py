"""Tests du CRUD patients et du contrôle d'accès associé."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit_log import AuditAction, AuditLog
from app.models.patient import Patient
from app.models.user import User
from tests.conftest import DOCTOR_PASSWORD, auth_headers

PREFIX = settings.api_v1_prefix

NEW_PATIENT = {
    "code": "TCD-2026-0042",
    "first_name": "Fatimé",
    "last_name": "Mahamat",
    "birth_date": "1975-03-18",
    "sex": "F",
    "phone": "+235 66 00 00 00",
    "medical_history": "Antécédent familial au premier degré.",
}


# --------------------------------------------------------------------------- #
# Création
# --------------------------------------------------------------------------- #


def test_doctor_can_create_a_patient(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.post(f"{PREFIX}/patients", headers=doctor_headers, json=NEW_PATIENT)

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "TCD-2026-0042"
    assert body["full_name"] == "Fatimé Mahamat"
    assert body["is_deleted"] is False


def test_patient_code_is_normalized_to_uppercase(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{PREFIX}/patients", headers=doctor_headers, json={**NEW_PATIENT, "code": " tcd-2026-9 "}
    )

    assert response.json()["code"] == "TCD-2026-9"


def test_duplicate_patient_code_is_refused(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    client.post(f"{PREFIX}/patients", headers=doctor_headers, json=NEW_PATIENT)
    second = client.post(f"{PREFIX}/patients", headers=doctor_headers, json=NEW_PATIENT)

    assert second.status_code == 409


def test_future_birth_date_is_refused(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{PREFIX}/patients",
        headers=doctor_headers,
        json={**NEW_PATIENT, "birth_date": "2999-01-01"},
    )

    assert response.status_code == 422


def test_unknown_sex_is_refused(client: TestClient, doctor_headers: dict[str, str]) -> None:
    response = client.post(
        f"{PREFIX}/patients", headers=doctor_headers, json={**NEW_PATIENT, "sex": "Z"}
    )

    assert response.status_code == 422


def test_patient_with_an_internal_domain_email_can_be_read(
    client: TestClient, db: Session, doctor_headers: dict[str, str]
) -> None:
    """Un dossier ne doit pas devenir illisible à cause d'une adresse interne."""
    from app.services import patient_service

    patient = patient_service.create_patient(
        db, code="TCD-2026-LOCAL", first_name="Test", last_name="Interne"
    )
    patient.email = "contact@hopital.local"
    db.commit()

    response = client.get(f"{PREFIX}/patients/{patient.id}", headers=doctor_headers)

    assert response.status_code == 200
    assert response.json()["email"] == "contact@hopital.local"


def test_male_patient_is_accepted(client: TestClient, doctor_headers: dict[str, str]) -> None:
    """Le cancer du sein masculin est rare mais réel."""
    response = client.post(
        f"{PREFIX}/patients",
        headers=doctor_headers,
        json={**NEW_PATIENT, "code": "TCD-2026-0100", "sex": "M"},
    )

    assert response.status_code == 201


# --------------------------------------------------------------------------- #
# Contrôle d'accès
# --------------------------------------------------------------------------- #


def test_anonymous_cannot_list_patients(client: TestClient) -> None:
    assert client.get(f"{PREFIX}/patients").status_code == 401


def test_researcher_cannot_access_patient_records(
    client: TestClient, researcher_user: User
) -> None:
    """Le rôle chercheur n'a pas vocation à voir des dossiers nominatifs."""
    headers = auth_headers(client, researcher_user.email, DOCTOR_PASSWORD)

    assert client.get(f"{PREFIX}/patients", headers=headers).status_code == 403
    assert client.post(f"{PREFIX}/patients", headers=headers, json=NEW_PATIENT).status_code == 403


def test_admin_can_access_patient_records(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    assert client.get(f"{PREFIX}/patients", headers=admin_headers).status_code == 200


# --------------------------------------------------------------------------- #
# Recherche et pagination
# --------------------------------------------------------------------------- #


def test_search_matches_last_name(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    response = client.get(
        f"{PREFIX}/patients", headers=doctor_headers, params={"search": "ali"}
    )

    assert response.status_code == 200
    assert {item["code"] for item in response.json()["items"]} == {patient.code}


def test_search_matches_code(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    response = client.get(
        f"{PREFIX}/patients", headers=doctor_headers, params={"search": "TCD-2026-0001"}
    )

    assert response.json()["total"] == 1


def test_search_without_match_returns_empty_page(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    del patient
    response = client.get(
        f"{PREFIX}/patients", headers=doctor_headers, params={"search": "introuvable"}
    )

    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_pagination_limits_results(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    for index in range(5):
        client.post(
            f"{PREFIX}/patients",
            headers=doctor_headers,
            json={**NEW_PATIENT, "code": f"TCD-2026-{index:04d}"},
        )

    response = client.get(f"{PREFIX}/patients", headers=doctor_headers, params={"limit": 2})
    body = response.json()

    assert len(body["items"]) == 2
    assert body["total"] == 5


def test_limit_above_maximum_is_refused(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.get(f"{PREFIX}/patients", headers=doctor_headers, params={"limit": 500})

    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Consultation, modification, suppression
# --------------------------------------------------------------------------- #


def test_get_patient_by_id(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    response = client.get(f"{PREFIX}/patients/{patient.id}", headers=doctor_headers)

    assert response.status_code == 200
    assert response.json()["code"] == patient.code


def test_unknown_patient_returns_404(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"

    assert client.get(f"{PREFIX}/patients/{unknown}", headers=doctor_headers).status_code == 404


def test_viewing_a_record_is_audited(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Savoir qui a ouvert quel dossier fait partie de la protection des données."""
    client.get(f"{PREFIX}/patients/{patient.id}", headers=doctor_headers)

    entry = db.scalar(
        select(AuditLog).where(AuditLog.action == AuditAction.PATIENT_VIEW.value)
    )
    assert entry is not None
    assert entry.resource_id == str(patient.id)


def test_partial_update_leaves_other_fields_untouched(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    response = client.patch(
        f"{PREFIX}/patients/{patient.id}",
        headers=doctor_headers,
        json={"phone": "+235 99 99 99 99"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "+235 99 99 99 99"
    assert body["first_name"] == "Amina"


def test_update_to_an_existing_code_is_refused(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    client.post(
        f"{PREFIX}/patients", headers=doctor_headers, json={**NEW_PATIENT, "code": "TCD-AUTRE"}
    )

    response = client.patch(
        f"{PREFIX}/patients/{patient.id}", headers=doctor_headers, json={"code": "TCD-AUTRE"}
    )

    assert response.status_code == 409


def test_delete_is_logical_not_physical(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Un dossier rattaché à des analyses rendues doit rester reconstituable."""
    deletion = client.delete(f"{PREFIX}/patients/{patient.id}", headers=doctor_headers)
    assert deletion.status_code == 200

    # Absent des listes et des consultations...
    assert client.get(f"{PREFIX}/patients/{patient.id}", headers=doctor_headers).status_code == 404
    assert client.get(f"{PREFIX}/patients", headers=doctor_headers).json()["total"] == 0

    # ...mais toujours présent en base.
    db.expire_all()
    stored = db.scalar(select(Patient).where(Patient.id == patient.id))
    assert stored is not None
    assert stored.is_deleted is True
    assert stored.deleted_at is not None
