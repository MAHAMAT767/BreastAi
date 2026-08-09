"""Tests de l'historique et de la recherche d'analyses."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import Analysis, AnalysisStatus
from app.models.patient import Patient
from app.services import analysis_service, patient_service

PREFIX = settings.api_v1_prefix


def make_analysis(
    db: Session,
    patient: Patient,
    *,
    prediction: str | None = "benign",
    status: str = AnalysisStatus.COMPLETED.value,
    validated: bool = False,
    created_at: datetime | None = None,
) -> Analysis:
    analysis = Analysis(
        patient_id=patient.id,
        original_filename="m.png",
        image_path="/uploads/m.png",
        status=status,
        prediction=prediction,
        probability=0.2 if prediction == "benign" else 0.9,
        doctor_validated=validated,
    )
    db.add(analysis)
    db.flush()
    if created_at is not None:
        analysis.created_at = created_at
    db.commit()
    db.refresh(analysis)
    return analysis


@pytest.fixture
def dataset(db: Session, patient: Patient) -> dict[str, object]:
    """Deux dossiers, quatre analyses réparties dans le temps."""
    other = patient_service.create_patient(
        db, code="TCD-2026-0777", first_name="Zara", last_name="Oumar"
    )

    now = datetime.now(UTC)
    return {
        "amina": patient,
        "zara": other,
        "recent_benign": make_analysis(db, patient, prediction="benign", created_at=now),
        "old_malignant": make_analysis(
            db, patient, prediction="malignant", created_at=now - timedelta(days=40)
        ),
        "zara_malignant": make_analysis(
            db, other, prediction="malignant", validated=True, created_at=now - timedelta(days=3)
        ),
        "failed": make_analysis(
            db, other, prediction=None, status=AnalysisStatus.FAILED.value, created_at=now
        ),
    }


def search(client: TestClient, headers: dict[str, str], **params) -> dict:
    response = client.get(f"{PREFIX}/analyses", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Sans filtre
# --------------------------------------------------------------------------- #


def test_lists_everything_by_default(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    del dataset

    assert search(client, doctor_headers)["total"] == 4


def test_most_recent_first(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    items = search(client, doctor_headers)["items"]
    dates = [item["created_at"] for item in items]

    assert dates == sorted(dates, reverse=True)


def test_ordering_is_stable_for_identical_timestamps(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Sans départage, deux analyses de même horodatage peuvent changer de place
    d'une page à l'autre et l'une d'elles disparaître de la pagination."""
    moment = datetime.now(UTC)
    for _ in range(5):
        make_analysis(db, patient, created_at=moment)

    first = [item["id"] for item in search(client, doctor_headers, limit=5)["items"]]
    second = [item["id"] for item in search(client, doctor_headers, limit=5)["items"]]

    assert first == second


# --------------------------------------------------------------------------- #
# Par patient
# --------------------------------------------------------------------------- #


def test_filter_by_patient_id(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    body = search(client, doctor_headers, patient_id=str(dataset["zara"].id))

    assert body["total"] == 2
    assert {item["patient_id"] for item in body["items"]} == {str(dataset["zara"].id)}


def test_search_by_patient_name(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    body = search(client, doctor_headers, search="Oumar")

    assert body["total"] == 2
    assert {item["patient_id"] for item in body["items"]} == {str(dataset["zara"].id)}


def test_search_by_patient_code(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    del dataset

    assert search(client, doctor_headers, search="TCD-2026-0777")["total"] == 2


def test_search_is_case_insensitive(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    del dataset

    assert search(client, doctor_headers, search="oUMAr")["total"] == 2


def test_search_without_match(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    del dataset
    body = search(client, doctor_headers, search="Personne")

    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


# --------------------------------------------------------------------------- #
# Par diagnostic
# --------------------------------------------------------------------------- #


def test_filter_by_prediction(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    del dataset
    body = search(client, doctor_headers, prediction="malignant")

    assert body["total"] == 2
    assert {item["prediction"] for item in body["items"]} == {"malignant"}


def test_filter_by_status(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    del dataset

    assert search(client, doctor_headers, status="failed")["total"] == 1


def test_filter_by_doctor_validation(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    del dataset

    assert search(client, doctor_headers, doctor_validated=True)["total"] == 1
    assert search(client, doctor_headers, doctor_validated=False)["total"] == 3


def test_unknown_prediction_is_refused(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{PREFIX}/analyses", headers=doctor_headers, params={"prediction": "peut-etre"}
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Par date
# --------------------------------------------------------------------------- #


def test_filter_from_a_date(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    del dataset
    since = (datetime.now(UTC) - timedelta(days=7)).date().isoformat()

    assert search(client, doctor_headers, date_from=since)["total"] == 3


def test_filter_up_to_a_date_includes_that_whole_day(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    """Une analyse de 14 h doit entrer dans « jusqu'au » de ce jour-là.

    C'est le piège classique d'une borne haute posée à minuit : la journée
    entière disparaît du résultat.
    """
    day = datetime(2026, 5, 20, 14, 30, tzinfo=UTC)
    make_analysis(db, patient, created_at=day)

    body = search(client, doctor_headers, date_from="2026-05-20", date_to="2026-05-20")

    assert body["total"] == 1


def test_date_range_excludes_what_is_outside(
    client: TestClient, db: Session, doctor_headers: dict[str, str], patient: Patient
) -> None:
    make_analysis(db, patient, created_at=datetime(2026, 5, 19, 23, 59, tzinfo=UTC))
    make_analysis(db, patient, created_at=datetime(2026, 5, 21, 0, 1, tzinfo=UTC))

    body = search(client, doctor_headers, date_from="2026-05-20", date_to="2026-05-20")

    assert body["total"] == 0


def test_malformed_date_is_refused(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{PREFIX}/analyses", headers=doctor_headers, params={"date_from": "20 mai"}
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Combinaisons et pagination
# --------------------------------------------------------------------------- #


def test_filters_combine(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    body = search(client, doctor_headers, search="Oumar", prediction="malignant")

    assert body["total"] == 1
    assert body["items"][0]["id"] == str(dataset["zara_malignant"].id)


def test_total_matches_the_filters_not_the_table(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    """Comptage et liste doivent partager exactement les mêmes conditions."""
    del dataset
    body = search(client, doctor_headers, prediction="malignant", limit=1)

    assert body["total"] == 2
    assert len(body["items"]) == 1


def test_pagination_walks_the_filtered_set(
    client: TestClient, doctor_headers: dict[str, str], dataset: dict
) -> None:
    del dataset
    first = search(client, doctor_headers, prediction="malignant", limit=1, offset=0)
    second = search(client, doctor_headers, prediction="malignant", limit=1, offset=1)

    assert first["items"][0]["id"] != second["items"][0]["id"]


# --------------------------------------------------------------------------- #
# Accès
# --------------------------------------------------------------------------- #


def test_anonymous_cannot_search(client: TestClient) -> None:
    assert client.get(f"{PREFIX}/analyses").status_code == 401


def test_service_accepts_no_filters(db: Session, patient: Patient) -> None:
    make_analysis(db, patient)

    assert analysis_service.count_analyses(db) == 1
    assert len(analysis_service.list_analyses(db)) == 1
