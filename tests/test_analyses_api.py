"""Tests du dépôt de mammographies : validation, prétraitement, archivage.

Les fichiers envoyés sont de vrais PNG, JPEG et DICOM : le décodage réel est
exercé de bout en bout, à travers le même endpoint que le frontend utilisera.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.preprocessing import detect_format
from app.config import settings
from app.models.analysis import AnalysisStatus
from app.models.audit_log import AuditAction, AuditLog
from app.models.patient import Patient
from app.models.user import User
from app.services import storage_service
from tests.conftest import DOCTOR_PASSWORD, auth_headers
from tests.factories import (
    make_corrupted_png_bytes,
    make_dicom_bytes,
    make_jpeg_bytes,
    make_png16_bytes,
    make_png_bytes,
)

PREFIX = settings.api_v1_prefix


def upload(
    client: TestClient,
    headers: dict[str, str],
    patient: Patient,
    data: bytes,
    filename: str = "mammo.png",
):
    return client.post(
        f"{PREFIX}/analyses",
        headers=headers,
        data={"patient_id": str(patient.id)},
        files={"file": (filename, data, "application/octet-stream")},
    )


# --------------------------------------------------------------------------- #
# Dépôt réussi
# --------------------------------------------------------------------------- #


def test_upload_png(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    response = upload(client, doctor_headers, patient, make_png_bytes())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["patient_id"] == str(patient.id)
    assert body["image_format"] == "png"
    assert body["original_filename"] == "mammo.png"
    assert body["file_size_bytes"] > 0


def test_upload_jpeg(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    response = upload(client, doctor_headers, patient, make_jpeg_bytes(), "cliche.jpg")

    assert response.status_code == 201
    assert response.json()["image_format"] == "jpeg"


def test_upload_dicom(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    response = upload(client, doctor_headers, patient, make_dicom_bytes(), "cliche.dcm")

    assert response.status_code == 201
    assert response.json()["image_format"] == "dicom"


def test_upload_16bit_png(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    assert upload(client, doctor_headers, patient, make_png16_bytes()).status_code == 201


def test_analysis_waits_for_inference(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Le prétraitement est fait, mais le modèle n'est branché qu'en Phase 4."""
    body = upload(client, doctor_headers, patient, make_png_bytes()).json()

    assert body["status"] == AnalysisStatus.PENDING.value
    assert body["prediction"] is None
    assert body["probability"] is None
    assert body["doctor_validated"] is False


def test_analysis_response_carries_the_disclaimer(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    body = upload(client, doctor_headers, patient, make_png_bytes()).json()

    assert "ne remplacent pas l'avis" in body["disclaimer"]


def test_upload_is_audited(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    upload(client, doctor_headers, patient, make_png_bytes())

    entry = db.scalar(
        select(AuditLog).where(AuditLog.action == AuditAction.ANALYSIS_CREATE.value)
    )
    assert entry is not None


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def test_unsupported_extension_is_refused(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    response = upload(client, doctor_headers, patient, make_png_bytes(), "rapport.pdf")

    assert response.status_code == 400
    assert "Extension" in response.json()["detail"]


def test_empty_file_is_refused(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    response = upload(client, doctor_headers, patient, b"", "vide.png")

    assert response.status_code == 400


def test_file_with_valid_extension_but_wrong_content_is_refused(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """L'extension ne fait pas foi : le contenu est vérifié."""
    response = upload(client, doctor_headers, patient, b"MZ\x90\x00" + b"\x00" * 300, "faux.png")

    assert response.status_code == 400


def test_corrupted_image_is_refused(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Signature PNG correcte mais contenu illisible : 422, pas 500."""
    response = upload(client, doctor_headers, patient, make_corrupted_png_bytes(), "casse.png")

    assert response.status_code == 422


def test_oversized_file_is_refused(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    oversized = make_png_bytes() + b"\x00" * (2 * 1024 * 1024)

    response = upload(client, doctor_headers, patient, oversized)

    assert response.status_code == 400
    assert "volumineux" in response.json()["detail"]


def test_upload_to_unknown_patient_returns_404(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{PREFIX}/analyses",
        headers=doctor_headers,
        data={"patient_id": "00000000-0000-0000-0000-000000000000"},
        files={"file": ("m.png", make_png_bytes(), "image/png")},
    )

    assert response.status_code == 404


def test_nothing_is_written_when_validation_fails(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Une ligne pointant vers des fichiers absents serait pire qu'aucune ligne."""
    upload(client, doctor_headers, patient, make_corrupted_png_bytes(), "casse.png")

    listing = client.get(f"{PREFIX}/analyses", headers=doctor_headers).json()
    assert listing["total"] == 0


# --------------------------------------------------------------------------- #
# Contrôle d'accès
# --------------------------------------------------------------------------- #


def test_anonymous_cannot_upload(client: TestClient, patient: Patient) -> None:
    response = client.post(
        f"{PREFIX}/analyses",
        data={"patient_id": str(patient.id)},
        files={"file": ("m.png", make_png_bytes(), "image/png")},
    )

    assert response.status_code == 401


def test_researcher_cannot_upload(
    client: TestClient, patient: Patient, researcher_user: User
) -> None:
    headers = auth_headers(client, researcher_user.email, DOCTOR_PASSWORD)

    assert upload(client, headers, patient, make_png_bytes()).status_code == 403


def test_anonymous_cannot_download_an_image(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Une mammographie ne doit jamais être servie sans contrôle d'accès."""
    analysis_id = upload(client, doctor_headers, patient, make_png_bytes()).json()["id"]

    assert client.get(f"{PREFIX}/analyses/{analysis_id}/image").status_code == 401


# --------------------------------------------------------------------------- #
# Fichiers stockés
# --------------------------------------------------------------------------- #


def test_processed_image_is_served_as_png(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient, make_dicom_bytes(), "c.dcm").json()["id"]

    response = client.get(f"{PREFIX}/analyses/{analysis_id}/image", headers=doctor_headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert detect_format(response.content) is not None


def test_original_file_is_served_unchanged(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    data = make_png_bytes()
    analysis_id = upload(client, doctor_headers, patient, data).json()["id"]

    response = client.get(
        f"{PREFIX}/analyses/{analysis_id}/image",
        headers=doctor_headers,
        params={"kind": "original"},
    )

    assert response.status_code == 200
    assert response.content == data


def test_images_are_not_cached_by_intermediaries(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient, make_png_bytes()).json()["id"]

    response = client.get(f"{PREFIX}/analyses/{analysis_id}/image", headers=doctor_headers)

    assert "no-store" in response.headers["cache-control"]


def test_stored_paths_are_relative_to_the_storage_root(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Déplacer le volume de stockage ne doit pas invalider les analyses existantes."""
    from app.models.analysis import Analysis

    upload(client, doctor_headers, patient, make_png_bytes())
    analysis = db.scalar(select(Analysis))

    assert analysis is not None
    assert not analysis.image_path.startswith("/")
    assert storage_service.exists(analysis.image_path)
    assert storage_service.exists(analysis.processed_image_path)


def test_hostile_filename_does_not_escape_the_storage_root(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Le nom fourni par le client ne sert jamais à construire un chemin."""
    from app.models.analysis import Analysis

    upload(client, doctor_headers, patient, make_png_bytes(), "../../../etc/passwd.png")
    analysis = db.scalar(select(Analysis))

    assert analysis is not None
    assert ".." not in analysis.original_filename
    assert ".." not in analysis.image_path
    assert storage_service.exists(analysis.image_path)


# --------------------------------------------------------------------------- #
# Consultation et lecture médicale
# --------------------------------------------------------------------------- #


def test_analyses_can_be_filtered_by_patient(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    from app.services import patient_service

    other = patient_service.create_patient(
        db, code="TCD-2026-0002", first_name="Zara", last_name="Oumar"
    )
    upload(client, doctor_headers, patient, make_png_bytes())
    upload(client, doctor_headers, other, make_png_bytes())

    response = client.get(
        f"{PREFIX}/analyses", headers=doctor_headers, params={"patient_id": str(patient.id)}
    )

    assert response.json()["total"] == 1


def test_unknown_analysis_returns_404(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"

    assert client.get(f"{PREFIX}/analyses/{unknown}", headers=doctor_headers).status_code == 404


def test_doctor_review_is_recorded(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """La lecture du médecin prime sur la sortie du modèle."""
    analysis_id = upload(client, doctor_headers, patient, make_png_bytes()).json()["id"]

    response = client.patch(
        f"{PREFIX}/analyses/{analysis_id}/review",
        headers=doctor_headers,
        json={
            "doctor_comment": "Cliché de bonne qualité, à recontrôler à 6 mois.",
            "doctor_validated": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["doctor_validated"] is True
    assert "recontrôler" in body["doctor_comment"]
