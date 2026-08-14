"""Tests des agrégats du tableau de bord."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import Analysis, AnalysisStatus
from app.models.patient import Patient
from app.models.user import User
from app.services import patient_service, stats_service
from tests.conftest import DOCTOR_PASSWORD, auth_headers

PREFIX = settings.api_v1_prefix


def add_analysis(
    db: Session,
    patient: Patient,
    *,
    prediction: str | None = "benign",
    status: str = AnalysisStatus.COMPLETED.value,
    inference_time_ms: float | None = 500.0,
    validated: bool = False,
    model_version: str = "placeholder-efficientnet_b0-imagenet",
    clinically_validated: bool = False,
    created_at: datetime | None = None,
) -> Analysis:
    analysis = Analysis(
        patient_id=patient.id,
        original_filename="m.png",
        image_path="/uploads/m.png",
        status=status,
        prediction=prediction,
        probability=0.4 if prediction == "benign" else 0.8,
        confidence=0.6,
        inference_time_ms=inference_time_ms,
        model_version=model_version,
        clinically_validated=clinically_validated,
        doctor_validated=validated,
    )
    db.add(analysis)
    db.flush()
    if created_at is not None:
        analysis.created_at = created_at
    db.commit()
    db.refresh(analysis)
    return analysis


# --------------------------------------------------------------------------- #
# Compteurs
# --------------------------------------------------------------------------- #


def test_empty_dashboard(client: TestClient, doctor_headers: dict[str, str]) -> None:
    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["total_patients"] == 0
    assert body["total_analyses"] == 0
    assert body["average_inference_time_ms"] is None
    assert body["doctor_validation_rate"] is None
    assert body["is_placeholder_model"] is False
    # Un tableau vide n'est pas une validation : sans aucune analyse, rien ne
    # permet d'affirmer qu'un modèle validé est en service.
    assert body["clinically_validated"] is False
    assert body["model_status"] == "trained_unvalidated"


def test_counts_by_prediction_and_status(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    add_analysis(db, patient, prediction="benign")
    add_analysis(db, patient, prediction="benign")
    add_analysis(db, patient, prediction="malignant")
    add_analysis(db, patient, prediction=None, status=AnalysisStatus.PENDING.value)
    add_analysis(db, patient, prediction=None, status=AnalysisStatus.FAILED.value)

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["total_analyses"] == 5
    assert body["completed_analyses"] == 3
    assert body["pending_analyses"] == 1
    assert body["failed_analyses"] == 1
    assert body["benign_count"] == 2
    assert body["malignant_count"] == 1


def test_deleted_patients_are_not_counted(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Un dossier supprimé ne doit plus peser dans les compteurs."""
    patient_service.create_patient(db, code="TCD-2026-0002", first_name="Z", last_name="O")
    patient_service.soft_delete(db, patient)

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["total_patients"] == 1


def test_average_inference_time_ignores_incomplete_analyses(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    add_analysis(db, patient, inference_time_ms=400.0)
    add_analysis(db, patient, inference_time_ms=600.0)
    add_analysis(
        db, patient, status=AnalysisStatus.FAILED.value, inference_time_ms=99_999.0
    )

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["average_inference_time_ms"] == 500.0


def test_validation_rate(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    add_analysis(db, patient, validated=True)
    add_analysis(db, patient, validated=True)
    add_analysis(db, patient, validated=False)
    add_analysis(db, patient, validated=False)

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["doctor_validated_count"] == 2
    assert body["doctor_validation_rate"] == 0.5


# --------------------------------------------------------------------------- #
# Honnêteté des indicateurs
# --------------------------------------------------------------------------- #


def test_no_accuracy_is_published(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Sans diagnostic de référence, aucun taux d'exactitude n'est calculable.

    En publier un — ne serait-ce qu'en le nommant ainsi — laisserait croire que
    la justesse du modèle a été mesurée.
    """
    add_analysis(db, patient, validated=True)

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["accuracy_available"] is False
    assert "accuracy" not in {key.lower() for key in body if key != "accuracy_available"} - {
        "accuracy_note"
    }
    assert "diagnostic de référence" in body["accuracy_note"]
    assert "pas la justesse du modèle" in body["accuracy_note"]


def test_placeholder_model_is_reported(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    add_analysis(db, patient, model_version="placeholder-efficientnet_b0-imagenet")

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["is_placeholder_model"] is True
    assert body["model_status"] == "placeholder"
    assert "AUCUNE VALEUR CLINIQUE" in body["model_warning"]


def test_trained_but_unvalidated_model_still_warns(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Ne plus être un placeholder ne suffit pas à faire disparaître le bandeau."""
    add_analysis(db, patient, model_version="efficientnet_b0-mini-mias-v1")

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["is_placeholder_model"] is False
    assert body["clinically_validated"] is False
    assert body["model_status"] == "trained_unvalidated"
    assert body["model_warning"] is not None
    assert "NON VALIDÉ CLINIQUEMENT" in body["model_warning"]


def test_validated_model_carries_no_provenance_warning(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    add_analysis(
        db,
        patient,
        model_version="efficientnet_b0-cbis-ddsm-v1",
        clinically_validated=True,
    )

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["is_placeholder_model"] is False
    assert body["clinically_validated"] is True
    assert body["model_status"] == "validated"
    assert body["model_warning"] is None


def test_one_unvalidated_analysis_is_enough_to_warn(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Le tableau de bord agrège : il doit porter l'avertissement le plus sévère."""
    add_analysis(
        db,
        patient,
        model_version="efficientnet_b0-cbis-ddsm-v1",
        clinically_validated=True,
    )
    add_analysis(
        db,
        patient,
        model_version="efficientnet_b0-mini-mias-v1",
        clinically_validated=False,
    )

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["clinically_validated"] is False
    assert body["model_status"] == "trained_unvalidated"


def test_model_versions_are_listed(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Deux versions coexistent après un remplacement de modèle."""
    add_analysis(db, patient, model_version="placeholder-efficientnet_b0-imagenet")
    add_analysis(db, patient, model_version="efficientnet_b0-cbis-ddsm-v1")

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert body["model_versions"] == [
        "efficientnet_b0-cbis-ddsm-v1",
        "placeholder-efficientnet_b0-imagenet",
    ]


# --------------------------------------------------------------------------- #
# Répartition mensuelle
# --------------------------------------------------------------------------- #


def test_monthly_series_always_covers_twelve_months(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    """Les mois sans activité valent zéro et ne sont pas omis.

    Un axe temporel troué laisserait lire une baisse là où il n'y a qu'une
    absence de données.
    """
    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()

    assert len(body["monthly"]) == stats_service.MONTHS_SHOWN
    assert all(bucket["total"] == 0 for bucket in body["monthly"])


def test_monthly_series_is_chronological(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    months = [
        bucket["month"]
        for bucket in client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers)
        .json()["monthly"]
    ]

    assert months == sorted(months)


def test_current_month_counts_new_analyses(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    add_analysis(db, patient, prediction="benign")
    add_analysis(db, patient, prediction="malignant")

    body = client.get(f"{PREFIX}/stats/dashboard", headers=doctor_headers).json()
    current = body["monthly"][-1]

    assert current["month"] == datetime.now(UTC).strftime("%Y-%m")
    assert current["total"] == 2
    assert current["benign"] == 1
    assert current["malignant"] == 1


def test_month_range_wraps_across_years() -> None:
    months = stats_service._month_range(datetime(2026, 2, 15, tzinfo=UTC), months=4)

    assert months == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]


# --------------------------------------------------------------------------- #
# Accès
# --------------------------------------------------------------------------- #


def test_anonymous_has_no_access(client: TestClient) -> None:
    assert client.get(f"{PREFIX}/stats/dashboard").status_code == 401


def test_researcher_can_read_aggregates(
    client: TestClient, researcher_user: User
) -> None:
    """Des chiffres agrégés ne désignent aucune patiente : c'est le rôle même du chercheur."""
    headers = auth_headers(client, researcher_user.email, DOCTOR_PASSWORD)

    response = client.get(f"{PREFIX}/stats/dashboard", headers=headers)

    assert response.status_code == 200


def test_admin_can_read_aggregates(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    assert client.get(f"{PREFIX}/stats/dashboard", headers=admin_headers).status_code == 200
