"""Tests de la génération du rapport PDF.

Les assertions portent sur le **contenu réellement présent dans le document**,
relu avec pypdf : vérifier qu'un fichier a été écrit ne dirait rien de ce qu'un
médecin lira dessus.
"""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

import pytest
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.disclaimer import GRADCAM_DISCLAIMER, MEDICAL_DISCLAIMER
from app.models.analysis import Analysis, AnalysisStatus
from app.models.patient import Patient
from app.models.user import User
from app.services import analysis_service, report_service
from app.services.report_service import (
    WATERMARK_TEXT,
    ReportGenerationError,
    canonical_timestamp,
    pdf_safe,
)
from tests.factories import make_png_bytes

LONG_HISTORY = (
    "Antécédent familial au premier degré (mère, cancer du sein diagnostiqué à "
    "52 ans). Nulliparité. Traitement hormonal substitutif pendant six ans. "
    "Aucune intervention mammaire antérieure. Première mammographie de dépistage."
)


def read_text(pdf: bytes) -> str:
    reader = PdfReader(BytesIO(pdf))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def page_texts(pdf: bytes) -> list[str]:
    return [page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages]


@pytest.fixture
def analysis(db: Session, patient: Patient, doctor_user: User) -> Analysis:
    """Analyse complète : image déposée, inférence et Grad-CAM exécutés."""
    patient.medical_history = LONG_HISTORY
    db.commit()

    return analysis_service.create_from_upload(
        db,
        patient=patient,
        filename="mammographie_MLO.png",
        data=make_png_bytes(height=800, width=600),
        created_by_id=doctor_user.id,
    )


@pytest.fixture
def report(db: Session, analysis: Analysis, doctor_user: User) -> report_service.ReportResult:
    return report_service.generate_report(db, analysis, generated_by=doctor_user)


# --------------------------------------------------------------------------- #
# Document
# --------------------------------------------------------------------------- #


def test_produces_a_valid_pdf(report: report_service.ReportResult) -> None:
    assert report.pdf.startswith(b"%PDF")
    assert len(PdfReader(BytesIO(report.pdf)).pages) >= 1


def test_report_is_archived_and_referenced(
    db: Session, analysis: Analysis, report: report_service.ReportResult
) -> None:
    from app.services import storage_service

    db.refresh(analysis)
    assert analysis.report_path
    assert storage_service.exists(analysis.report_path)
    assert analysis.report_signature == report.signature
    assert analysis.report_generated_at is not None


def test_contains_patient_identity(report: report_service.ReportResult) -> None:
    text = read_text(report.pdf)

    assert "TCD-2026-0001" in text
    assert "Amina" in text
    assert "Ali" in text


def test_long_medical_history_is_not_truncated(report: report_service.ReportResult) -> None:
    """Une cellule qui déborde tronque silencieusement : ici, des antécédents."""
    text = read_text(report.pdf).replace("\n", " ")

    assert "Première mammographie de dépistage." in text
    assert "Traitement hormonal substitutif pendant six ans." in text


def test_contains_the_result(
    db: Session, analysis: Analysis, report: report_service.ReportResult
) -> None:
    db.refresh(analysis)
    text = read_text(report.pdf)

    expected_label = {"benign": "Bénin", "malignant": "Malin"}[analysis.prediction]
    assert expected_label in text
    assert f"{analysis.probability * 100:.1f} %" in text
    assert analysis.model_version in text


def test_embeds_both_images(report: report_service.ReportResult) -> None:
    """Image d'origine et superposition Grad-CAM."""
    reader = PdfReader(BytesIO(report.pdf))
    images = [image for page in reader.pages for image in page.images]

    assert len(images) == 2


def test_contains_the_medical_disclaimer(report: report_service.ReportResult) -> None:
    text = read_text(report.pdf).replace("\n", " ")

    assert "ne remplacent pas l'avis" in text
    assert pdf_safe(MEDICAL_DISCLAIMER)[:40] in text


def test_contains_the_gradcam_caveat(report: report_service.ReportResult) -> None:
    text = read_text(report.pdf).replace("\n", " ")

    assert "non l'emplacement d'une lésion" in text
    assert pdf_safe(GRADCAM_DISCLAIMER)[:40] in text


def test_contains_the_doctor_reading(
    db: Session, analysis: Analysis, doctor_user: User
) -> None:
    analysis_service.set_doctor_review(
        db, analysis, comment="Sein dense, contrôle à 12 mois.", validated=True
    )
    result = report_service.generate_report(db, analysis, generated_by=doctor_user)
    text = read_text(result.pdf).replace("\n", " ")

    assert "Sein dense, contrôle à 12 mois." in text
    assert "Validation par le médecin : OUI" in text


def test_names_the_signatory(
    report: report_service.ReportResult, doctor_user: User
) -> None:
    assert doctor_user.full_name in read_text(report.pdf)


# --------------------------------------------------------------------------- #
# Avertissement placeholder
# --------------------------------------------------------------------------- #


def test_placeholder_warning_is_on_the_first_page(
    report: report_service.ReportResult,
) -> None:
    first_page = page_texts(report.pdf)[0].replace("\n", " ")

    assert "AUCUNE VALEUR CLINIQUE" in first_page
    assert "jamais été entraîné sur des mammographies" in first_page


def test_watermark_is_on_every_page(report: report_service.ReportResult) -> None:
    """Un rapport imprimé circule hors de l'application : il doit se dénoncer seul."""
    pages = page_texts(report.pdf)

    assert len(pages) >= 2
    for index, text in enumerate(pages, start=1):
        assert WATERMARK_TEXT in text, f"filigrane absent de la page {index}"


def test_no_watermark_once_a_real_model_is_deployed(
    db: Session, analysis: Analysis, doctor_user: User
) -> None:
    """Le bandeau et le filigrane doivent disparaître d'eux-mêmes, sans intervention."""
    analysis.model_version = "efficientnet_b0-cbis-ddsm-v1"
    db.commit()

    result = report_service.generate_report(db, analysis, generated_by=doctor_user)
    text = read_text(result.pdf)

    assert WATERMARK_TEXT not in text
    assert "AUCUNE VALEUR CLINIQUE" not in text
    # L'avertissement médical, lui, reste en toutes circonstances.
    assert "ne remplacent pas l'avis" in text.replace("\n", " ")


def test_summary_is_withheld_for_the_placeholder(
    report: report_service.ReportResult,
) -> None:
    """Décrire un cliché à partir de sorties arbitraires serait pire que se taire."""
    text = read_text(report.pdf).replace("\n", " ")

    assert "Aucune synthèse n'est produite" in text


def test_summary_is_written_for_a_real_model(
    db: Session, analysis: Analysis, doctor_user: User
) -> None:
    analysis.model_version = "efficientnet_b0-cbis-ddsm-v1"
    db.commit()

    text = read_text(report_service.generate_report(db, analysis, doctor_user).pdf)

    assert "Le modèle oriente vers une classification" in text.replace("\n", " ")


# --------------------------------------------------------------------------- #
# Signature
# --------------------------------------------------------------------------- #


def test_signature_is_printed_on_the_document(
    report: report_service.ReportResult,
) -> None:
    assert report.signature in read_text(report.pdf).replace("\n", "")


def test_signature_verifies(
    db: Session, analysis: Analysis, patient: Patient, report: report_service.ReportResult
) -> None:
    del report
    db.refresh(analysis)

    assert report_service.verify_signature(analysis, patient) is True


def test_altered_probability_invalidates_the_signature(
    db: Session, analysis: Analysis, patient: Patient, report: report_service.ReportResult
) -> None:
    del report
    analysis.probability = 0.99
    db.commit()

    assert report_service.verify_signature(analysis, patient) is False


def test_altered_prediction_invalidates_the_signature(
    db: Session, analysis: Analysis, patient: Patient, report: report_service.ReportResult
) -> None:
    del report
    analysis.prediction = "malignant" if analysis.prediction == "benign" else "benign"
    db.commit()

    assert report_service.verify_signature(analysis, patient) is False


def test_reattributing_the_report_to_another_patient_invalidates_it(
    db: Session, analysis: Analysis, report: report_service.ReportResult
) -> None:
    del report
    other = Patient(code="TCD-2026-9999", first_name="Zara", last_name="Oumar", sex="F")
    db.add(other)
    db.commit()

    assert report_service.verify_signature(analysis, other) is False


def test_unsigned_analysis_does_not_verify(
    db: Session, analysis: Analysis, patient: Patient
) -> None:
    del db

    assert report_service.verify_signature(analysis, patient) is False


def test_signature_covers_the_medical_reading(
    db: Session, analysis: Analysis, patient: Patient, report: report_service.ReportResult
) -> None:
    """C'est la lecture du médecin qui fait foi : elle doit être couverte.

    Sans cela, un rapport portant un ancien commentaire continuerait à se
    vérifier après révision du dossier.
    """
    analysis_service.set_doctor_review(
        db, analysis, comment="Révision : contrôle rapproché à 6 mois.", validated=True
    )

    assert report_service.verify_signature(analysis, patient) is False

    second = report_service.generate_report(db, analysis)
    assert second.signature != report.signature
    assert report_service.verify_signature(analysis, patient) is True


def test_regeneration_without_change_keeps_the_report_verifiable(
    db: Session, analysis: Analysis, patient: Patient, doctor_user: User
) -> None:
    """L'empreinte est celle du contenu : elle ne change pas sans raison."""
    report_service.generate_report(db, analysis, generated_by=doctor_user)
    report_service.generate_report(db, analysis, generated_by=doctor_user)

    assert report_service.verify_signature(analysis, patient) is True


def test_canonical_timestamp_reads_naive_dates_as_utc() -> None:
    """PostgreSQL rend le fuseau, SQLite non : sans cela, rien ne se vérifierait."""
    aware = datetime(2026, 8, 8, 10, 30, 0, tzinfo=UTC)
    naive = datetime(2026, 8, 8, 10, 30, 0)

    assert canonical_timestamp(naive) == canonical_timestamp(aware)


def test_canonical_timestamp_drops_sub_seconds() -> None:
    """Un backend qui arrondirait les microsecondes invaliderait tout l'existant."""
    with_microseconds = datetime(2026, 8, 8, 10, 30, 0, 123456, tzinfo=UTC)
    without = datetime(2026, 8, 8, 10, 30, 0, tzinfo=UTC)

    assert canonical_timestamp(with_microseconds) == canonical_timestamp(without)


# --------------------------------------------------------------------------- #
# Refus
# --------------------------------------------------------------------------- #


def test_pending_analysis_has_no_report(db: Session, analysis: Analysis) -> None:
    analysis.status = AnalysisStatus.PENDING.value
    db.commit()

    with pytest.raises(ReportGenerationError, match="terminée"):
        report_service.generate_report(db, analysis)


def test_failed_analysis_has_no_report(db: Session, analysis: Analysis) -> None:
    """Produire un compte rendu sans résultat laisserait croire à une lecture."""
    analysis.status = AnalysisStatus.FAILED.value
    db.commit()

    with pytest.raises(ReportGenerationError):
        report_service.generate_report(db, analysis)


def test_pdf_safe_removes_unsupported_characters() -> None:
    """Helvetica est en WinAnsi : un emoji casserait le rendu."""
    cleaned = pdf_safe("⚠️ Attention : résultat à vérifier")

    assert "Attention : résultat à vérifier" in cleaned
    cleaned.encode("latin-1")  # ne doit pas lever
