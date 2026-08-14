"""Tests de l'assistant conversationnel.

Aucun appel réseau n'est fait ici : le fournisseur est simulé. Les tests portent
sur ce que l'application garantit d'elle-même — ce qui sort vers le tiers, et ce
qui accompagne la réponse quoi que dise le modèle. Une conversation réelle a été
vérifiée séparément (voir docs/API.md).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import Analysis, AnalysisStatus
from app.models.audit_log import AuditAction, AuditLog
from app.models.patient import Patient
from app.models.user import User
from app.services import assistant_service
from app.services.assistant_service import (
    AssistantMessage,
    AssistantQuotaError,
    AssistantUnavailableError,
    build_context,
    build_messages,
    compose_answer,
)
from tests.conftest import DOCTOR_PASSWORD, auth_headers

PREFIX = settings.api_v1_prefix

PROVIDER = "app.services.assistant_service._call_provider"


@pytest.fixture
def identified_patient(db: Session, patient: Patient) -> Patient:
    """Dossier renseigné avec tout ce qui ne doit surtout pas sortir."""
    patient.first_name = "Fatimé"
    patient.last_name = "Abakar"
    patient.birth_date = date(1974, 6, 3)
    patient.phone = "+235 66 12 34 56"
    patient.email = "fatime.abakar@hopital.td"
    patient.address = "Quartier Klemat, N'Djamena"
    patient.medical_history = "Antécédent familial : mère, cancer du sein à 52 ans."
    db.commit()
    db.refresh(patient)
    return patient


@pytest.fixture
def analysis(db: Session, identified_patient: Patient, doctor_user: User) -> Analysis:
    entry = Analysis(
        patient_id=identified_patient.id,
        created_by_id=doctor_user.id,
        original_filename="mammographie_MLO.dcm",
        image_path="/uploads/m.dcm",
        image_format="dicom",
        status=AnalysisStatus.COMPLETED.value,
        prediction="benign",
        probability=0.464,
        confidence=0.536,
        inference_time_ms=1453.0,
        model_version="placeholder-efficientnet_b0-imagenet",
        preprocessing_version="v1",
        doctor_comment="Sein dense. Contrôle à 12 mois. Patiente prévenue par téléphone.",
        region_x=0,
        region_y=0,
        region_width=106,
        region_height=384,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@pytest.fixture(autouse=True)
def configured_assistant(monkeypatch):
    """Un jeton est présent : l'assistant se croit configuré."""
    monkeypatch.setattr(settings, "huggingface_api_token", "hf_jeton_de_test")


# --------------------------------------------------------------------------- #
# Ce qui sort de l'établissement
# --------------------------------------------------------------------------- #


def test_context_excludes_direct_identifiers(
    analysis: Analysis, identified_patient: Patient
) -> None:
    """Rien de ce qui désigne la patiente ne doit atteindre le fournisseur."""
    context = build_context(analysis, identified_patient)

    for forbidden in [
        "Fatimé",
        "Abakar",
        identified_patient.code,
        "1974",
        "66 12 34 56",
        "fatime.abakar",
        "Klemat",
    ]:
        assert forbidden not in context, f"{forbidden!r} ne doit pas être transmis"


def test_context_excludes_the_doctor_free_text(
    analysis: Analysis, identified_patient: Patient
) -> None:
    """Le commentaire est du texte libre : un nom peut s'y trouver."""
    context = build_context(analysis, identified_patient)

    assert "Contrôle à 12 mois" not in context
    assert "téléphone" not in context


def test_context_keeps_what_the_question_needs(
    analysis: Analysis, identified_patient: Patient
) -> None:
    context = build_context(analysis, identified_patient)

    assert "bénin" in context
    assert "46.4 %" in context
    assert "53.6 %" in context
    assert "106 × 384" in context
    assert "placeholder-efficientnet_b0-imagenet" in context


def test_context_sends_age_not_birth_date(
    analysis: Analysis, identified_patient: Patient
) -> None:
    """L'âge conditionne la lecture d'une mammographie ; seul, il n'identifie personne."""
    context = build_context(analysis, identified_patient)

    assert "ans" in context
    assert "03/06/1974" not in context
    assert "1974-06-03" not in context


def test_context_reports_a_failed_analysis(
    db: Session, analysis: Analysis, identified_patient: Patient
) -> None:
    analysis.status = AnalysisStatus.FAILED.value
    analysis.error_message = "Décodage impossible."
    db.commit()

    context = build_context(analysis, identified_patient)

    assert "non terminée" in context
    assert "46.4 %" not in context


# --------------------------------------------------------------------------- #
# Consigne système
# --------------------------------------------------------------------------- #


def test_placeholder_rule_is_added_to_the_system_prompt() -> None:
    messages = build_messages("contexte", "question", [], "placeholder")

    assert "DÉMONSTRATION" in messages[0]["content"]


def test_placeholder_rule_disappears_for_a_trained_model() -> None:
    messages = build_messages("contexte", "question", [], "trained_unvalidated")

    assert "DÉMONSTRATION" not in messages[0]["content"]


def test_unvalidated_rule_is_added_for_a_trained_but_unvalidated_model() -> None:
    """Un modèle entraîné non validé reçoit sa propre consigne, pas le silence."""
    messages = build_messages("contexte", "question", [], "trained_unvalidated")

    assert "AUCUNE VALIDATION CLINIQUE" in messages[0]["content"]


def test_validated_model_receives_no_provenance_rule() -> None:
    messages = build_messages("contexte", "question", [], "validated")

    assert "DÉMONSTRATION" not in messages[0]["content"]
    assert "AUCUNE VALIDATION CLINIQUE" not in messages[0]["content"]


def test_history_is_truncated(monkeypatch) -> None:
    """Chaque tour conservé est refacturé à chaque question."""
    monkeypatch.setattr(settings, "assistant_history_turns", 2)
    history = [
        AssistantMessage(role="user" if index % 2 == 0 else "assistant", content=f"m{index}")
        for index in range(20)
    ]

    messages = build_messages("contexte", "question", history, "trained_unvalidated")

    # système + 2 tours (4 messages) + la question courante
    assert len(messages) == 6
    assert messages[-1]["content"].endswith("Question : question")


def test_empty_history_messages_are_dropped() -> None:
    history = [AssistantMessage(role="user", content="   ")]

    messages = build_messages("contexte", "question", history, "trained_unvalidated")

    assert len(messages) == 2


# --------------------------------------------------------------------------- #
# Avertissements, indépendants du modèle
# --------------------------------------------------------------------------- #


def test_disclaimer_is_appended_by_code() -> None:
    """Le modèle n'est pas chargé de se souvenir de l'avertissement."""
    composed = compose_answer("Réponse du modèle.", "validated")

    assert "Réponse du modèle." in composed
    assert "ne remplacent pas l'avis" in composed


def test_placeholder_warning_precedes_the_answer() -> None:
    composed = compose_answer("Réponse du modèle.", "placeholder")

    assert composed.index("AUCUNE VALEUR CLINIQUE") < composed.index("Réponse du modèle.")


def test_unvalidated_warning_precedes_the_answer() -> None:
    """Le cas intermédiaire porte lui aussi son avertissement dans le texte."""
    composed = compose_answer("Réponse du modèle.", "trained_unvalidated")

    assert composed.index("NON VALIDÉ CLINIQUEMENT") < composed.index("Réponse du modèle.")
    assert "ne remplacent pas l'avis" in composed


def test_warnings_survive_a_model_that_ignores_its_instructions() -> None:
    """À la mise au point, le modèle a omis l'avertissement une fois sur deux."""
    composed = compose_answer("Cette image est clairement cancéreuse.", "placeholder")

    assert "AUCUNE VALEUR CLINIQUE" in composed
    assert "ne remplacent pas l'avis" in composed


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #


def test_question_returns_an_answer(
    client: TestClient, doctor_headers: dict[str, str], analysis: Analysis
) -> None:
    with patch(PROVIDER, return_value=("La probabilité est une sortie de classifieur.", {})):
        response = client.post(
            f"{PREFIX}/assistant/analyses/{analysis.id}",
            headers=doctor_headers,
            json={"question": "Que signifie ce score ?"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "sortie de classifieur" in body["answer"]
    assert "ne remplacent pas l'avis" in body["answer"]
    assert body["model"] == settings.assistant_model


def test_answer_carries_the_disclaimer_field(
    client: TestClient, doctor_headers: dict[str, str], analysis: Analysis
) -> None:
    with patch(PROVIDER, return_value=("Réponse.", {})):
        body = client.post(
            f"{PREFIX}/assistant/analyses/{analysis.id}",
            headers=doctor_headers,
            json={"question": "Pourquoi ?"},
        ).json()

    assert "ne remplacent pas l'avis" in body["disclaimer"]
    assert body["is_placeholder_model"] is True
    assert "AUCUNE VALEUR CLINIQUE" in body["model_warning"]


def test_context_sent_is_returned_for_inspection(
    client: TestClient, doctor_headers: dict[str, str], analysis: Analysis
) -> None:
    """L'utilisateur doit pouvoir vérifier ce qui est sorti de l'établissement."""
    with patch(PROVIDER, return_value=("Réponse.", {})):
        body = client.post(
            f"{PREFIX}/assistant/analyses/{analysis.id}",
            headers=doctor_headers,
            json={"question": "Pourquoi ?"},
        ).json()

    assert "Contexte de l'analyse" in body["context_sent"]
    assert "Fatimé" not in body["context_sent"]


def test_history_is_forwarded(
    client: TestClient, doctor_headers: dict[str, str], analysis: Analysis
) -> None:
    with patch(PROVIDER, return_value=("Réponse.", {})) as provider:
        client.post(
            f"{PREFIX}/assistant/analyses/{analysis.id}",
            headers=doctor_headers,
            json={
                "question": "Et donc ?",
                "history": [
                    {"role": "user", "content": "Que mesure Grad-CAM ?"},
                    {"role": "assistant", "content": "Les régions influentes."},
                ],
            },
        )

    sent = provider.call_args.args[0]
    assert any(message["content"] == "Les régions influentes." for message in sent)


def test_query_is_audited_without_its_text(
    client: TestClient, db: Session, doctor_headers: dict[str, str], analysis: Analysis
) -> None:
    """La trace importe ; le texte de la question n'a pas à figurer au journal."""
    with patch(PROVIDER, return_value=("Réponse.", {})):
        client.post(
            f"{PREFIX}/assistant/analyses/{analysis.id}",
            headers=doctor_headers,
            json={"question": "Antécédent familial chez cette patiente ?"},
        )

    entry = db.scalar(
        select(AuditLog).where(AuditLog.action == AuditAction.ASSISTANT_QUERY.value)
    )
    assert entry is not None
    assert entry.resource_id == str(analysis.id)
    assert "Antécédent" not in (entry.detail or "")


# --------------------------------------------------------------------------- #
# Défaillances
# --------------------------------------------------------------------------- #


def test_quota_exhausted_is_explained(
    client: TestClient, doctor_headers: dict[str, str], analysis: Analysis
) -> None:
    with patch(PROVIDER, side_effect=AssistantQuotaError("Le quota est épuisé.")):
        response = client.post(
            f"{PREFIX}/assistant/analyses/{analysis.id}",
            headers=doctor_headers,
            json={"question": "Pourquoi ?"},
        )

    assert response.status_code == 503
    assert "quota" in response.json()["detail"].lower()


def test_provider_failure_is_not_a_500(
    client: TestClient, doctor_headers: dict[str, str], analysis: Analysis
) -> None:
    with patch(PROVIDER, side_effect=AssistantUnavailableError("Injoignable.")):
        response = client.post(
            f"{PREFIX}/assistant/analyses/{analysis.id}",
            headers=doctor_headers,
            json={"question": "Pourquoi ?"},
        )

    assert response.status_code == 502


def test_assistant_without_token_is_disabled(
    client: TestClient, doctor_headers: dict[str, str], analysis: Analysis, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "huggingface_api_token", None)

    response = client.post(
        f"{PREFIX}/assistant/analyses/{analysis.id}",
        headers=doctor_headers,
        json={"question": "Pourquoi ?"},
    )

    assert response.status_code == 503
    assert "pas configuré" in response.json()["detail"]


def test_empty_question_is_refused(
    client: TestClient, doctor_headers: dict[str, str], analysis: Analysis
) -> None:
    response = client.post(
        f"{PREFIX}/assistant/analyses/{analysis.id}",
        headers=doctor_headers,
        json={"question": "   "},
    )

    assert response.status_code in (400, 422)


def test_overlong_question_is_refused(
    client: TestClient, doctor_headers: dict[str, str], analysis: Analysis
) -> None:
    response = client.post(
        f"{PREFIX}/assistant/analyses/{analysis.id}",
        headers=doctor_headers,
        json={"question": "a" * 2000},
    )

    assert response.status_code == 422


def test_unknown_analysis_returns_404(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"{PREFIX}/assistant/analyses/{unknown}",
        headers=doctor_headers,
        json={"question": "Pourquoi ?"},
    )

    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Accès et état
# --------------------------------------------------------------------------- #


def test_anonymous_has_no_access(client: TestClient, analysis: Analysis) -> None:
    response = client.post(
        f"{PREFIX}/assistant/analyses/{analysis.id}", json={"question": "Pourquoi ?"}
    )

    assert response.status_code == 401


def test_researcher_has_no_access(
    client: TestClient, analysis: Analysis, researcher_user: User
) -> None:
    """L'assistant parle d'un dossier précis : il reste fermé au rôle chercheur."""
    headers = auth_headers(client, researcher_user.email, DOCTOR_PASSWORD)

    response = client.post(
        f"{PREFIX}/assistant/analyses/{analysis.id}",
        headers=headers,
        json={"question": "Pourquoi ?"},
    )

    assert response.status_code == 403


def test_status_reports_the_model(
    client: TestClient, doctor_headers: dict[str, str]
) -> None:
    body = client.get(f"{PREFIX}/assistant/status", headers=doctor_headers).json()

    assert body["enabled"] is True
    assert body["model"] == settings.assistant_model
    assert "jamais le" in body["notice"]


def test_status_when_disabled(
    client: TestClient, doctor_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(settings, "huggingface_api_token", None)

    body = client.get(f"{PREFIX}/assistant/status", headers=doctor_headers).json()

    assert body["enabled"] is False
    assert body["model"] is None
    assert "restent disponibles" in body["notice"]


def test_service_refuses_when_disabled(
    analysis: Analysis, identified_patient: Patient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "huggingface_api_token", None)

    with pytest.raises(assistant_service.AssistantDisabledError):
        assistant_service.ask(analysis, identified_patient, "Pourquoi ?")
