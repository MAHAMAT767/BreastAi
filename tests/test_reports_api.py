"""Tests des endpoints de rapport."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import Analysis, AnalysisStatus
from app.models.audit_log import AuditAction, AuditLog
from app.models.patient import Patient
from app.models.user import User
from tests.conftest import DOCTOR_PASSWORD, auth_headers
from tests.factories import make_png_bytes

PREFIX = settings.api_v1_prefix


def upload(client: TestClient, headers: dict[str, str], patient: Patient) -> str:
    response = client.post(
        f"{PREFIX}/analyses",
        headers=headers,
        data={"patient_id": str(patient.id)},
        files={"file": ("mammo.png", make_png_bytes(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# --------------------------------------------------------------------------- #
# Téléchargement
# --------------------------------------------------------------------------- #


def test_download_returns_a_pdf(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient)

    response = client.get(f"{PREFIX}/analyses/{analysis_id}/report", headers=doctor_headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert len(PdfReader(BytesIO(response.content)).pages) >= 1


def test_download_proposes_a_filename(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient)

    response = client.get(f"{PREFIX}/analyses/{analysis_id}/report", headers=doctor_headers)

    assert "attachment" in response.headers["content-disposition"]
    assert ".pdf" in response.headers["content-disposition"]


def test_report_is_not_cached_by_intermediaries(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Le document contient des données patients identifiantes."""
    analysis_id = upload(client, doctor_headers, patient)

    response = client.get(f"{PREFIX}/analyses/{analysis_id}/report", headers=doctor_headers)

    assert "no-store" in response.headers["cache-control"]


def test_download_generates_the_report_on_first_access(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient)
    analysis = db.scalar(select(Analysis))
    assert analysis is not None and analysis.report_path is None

    client.get(f"{PREFIX}/analyses/{analysis_id}/report", headers=doctor_headers)

    db.refresh(analysis)
    assert analysis.report_path is not None


def test_analysis_response_reports_availability(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient)

    before = client.get(f"{PREFIX}/analyses/{analysis_id}", headers=doctor_headers).json()
    assert before["has_report"] is False

    client.get(f"{PREFIX}/analyses/{analysis_id}/report", headers=doctor_headers)

    after = client.get(f"{PREFIX}/analyses/{analysis_id}", headers=doctor_headers).json()
    assert after["has_report"] is True
    assert after["report_signature"]
    assert after["report_generated_at"]


def test_export_is_audited(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Savoir qui a sorti un compte rendu fait partie de la traçabilité."""
    analysis_id = upload(client, doctor_headers, patient)
    client.get(f"{PREFIX}/analyses/{analysis_id}/report", headers=doctor_headers)

    entry = db.scalar(
        select(AuditLog).where(AuditLog.action == AuditAction.REPORT_EXPORT.value)
    )
    assert entry is not None
    assert entry.resource_id == analysis_id


# --------------------------------------------------------------------------- #
# Contrôle d'accès
# --------------------------------------------------------------------------- #


def test_anonymous_cannot_download_a_report(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient)

    assert client.get(f"{PREFIX}/analyses/{analysis_id}/report").status_code == 401


def test_researcher_cannot_download_a_report(
    client: TestClient,
    doctor_headers: dict[str, str],
    patient: Patient,
    researcher_user: User,
) -> None:
    analysis_id = upload(client, doctor_headers, patient)
    headers = auth_headers(client, researcher_user.email, DOCTOR_PASSWORD)

    assert client.get(f"{PREFIX}/analyses/{analysis_id}/report", headers=headers).status_code == 403


def test_unknown_analysis_returns_404(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"

    response = client.get(f"{PREFIX}/analyses/{unknown}/report", headers=doctor_headers)
    assert response.status_code == 404


def test_incomplete_analysis_is_refused(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient)
    analysis = db.scalar(select(Analysis))
    assert analysis is not None
    analysis.status = AnalysisStatus.FAILED.value
    db.commit()

    response = client.get(f"{PREFIX}/analyses/{analysis_id}/report", headers=doctor_headers)

    assert response.status_code == 409
    assert "terminée" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# Régénération et vérification
# --------------------------------------------------------------------------- #


def test_regeneration_returns_metadata(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient)

    response = client.post(f"{PREFIX}/analyses/{analysis_id}/report", headers=doctor_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["signature"]) == 64
    assert body["size_bytes"] > 1000
    assert body["is_placeholder_model"] is True
    assert "AUCUNE VALEUR CLINIQUE" in body["model_warning"]


def test_verification_confirms_a_fresh_report(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient)
    client.get(f"{PREFIX}/analyses/{analysis_id}/report", headers=doctor_headers)

    response = client.get(
        f"{PREFIX}/analyses/{analysis_id}/report/verify", headers=doctor_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_report"] is True
    assert body["signature_valid"] is True


def test_verification_detects_an_altered_analysis(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient)
    client.get(f"{PREFIX}/analyses/{analysis_id}/report", headers=doctor_headers)

    analysis = db.scalar(select(Analysis))
    assert analysis is not None
    analysis.probability = 0.99
    db.commit()

    body = client.get(
        f"{PREFIX}/analyses/{analysis_id}/report/verify", headers=doctor_headers
    ).json()

    assert body["signature_valid"] is False
    assert "régénéré" in body["detail"]


def test_verification_without_a_report(
    client: TestClient, doctor_headers: dict[str, str], patient: Patient
) -> None:
    analysis_id = upload(client, doctor_headers, patient)

    body = client.get(
        f"{PREFIX}/analyses/{analysis_id}/report/verify", headers=doctor_headers
    ).json()

    assert body["has_report"] is False
    assert body["signature_valid"] is False
