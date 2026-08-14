"""Génération du compte rendu PDF d'une analyse.

Un rapport imprimé circule hors de l'application : il est transmis, photocopié,
photographié. Il doit donc porter seul tout ce qui conditionne sa lecture — le
statut du modèle, l'avertissement médical, la limite du Grad-CAM — sans dépendre
du contexte dans lequel il a été produit.

C'est pourquoi l'avertissement « modèle de démonstration » est ici bien plus
visible que dans l'API : bandeau rouge en tête et filigrane diagonal sur chaque
page. Un rapport qui sortirait du service sans se dénoncer serait la pire
défaillance possible de cette phase.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Final

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.ai.inference import is_placeholder_version
from app.ai.preprocessing import encode_png, load_image
from app.config import settings
from app.disclaimer import (
    GRADCAM_DISCLAIMER,
    MEDICAL_DISCLAIMER,
    ModelStatus,
    derive_model_status,
    model_warning_for,
)
from app.models.analysis import Analysis, AnalysisStatus
from app.models.patient import Patient
from app.models.user import User
from app.services import storage_service

logger = logging.getLogger(__name__)

REPORT_FILENAME: Final[str] = "rapport.pdf"

#: Libellés cliniques. La sortie brute du modèle est en anglais ; un compte rendu
#: remis dans un service de santé francophone ne doit pas l'être.
PREDICTION_LABELS_FR: Final[dict[str, str]] = {
    "benign": "Bénin",
    "malignant": "Malin",
}

STATUS_LABELS_FR: Final[dict[str, str]] = {
    "pending": "En attente",
    "processing": "En cours",
    "completed": "Terminée",
    "failed": "Échec",
}

WATERMARK_TEXT: Final[str] = "MODELE DE DEMONSTRATION - SANS VALEUR CLINIQUE"

#: Filigrane du cas intermédiaire. Un rapport imprimé se détache de l'interface :
#: sans marque sur le document lui-même, plus rien ne rappelle au lecteur que ces
#: chiffres n'ont pas été validés.
UNVALIDATED_WATERMARK_TEXT: Final[str] = "MODELE NON VALIDE CLINIQUEMENT - USAGE ACADEMIQUE"

#: Filigrane à imprimer selon l'état du modèle. `None` pour un modèle validé :
#: seul l'avertissement médical général subsiste alors.
WATERMARK_BY_STATUS: Final[dict[ModelStatus, str | None]] = {
    "placeholder": WATERMARK_TEXT,
    "trained_unvalidated": UNVALIDATED_WATERMARK_TEXT,
    "validated": None,
}

#: Largeur maximale d'une image dans le corps du document.
IMAGE_WIDTH: Final[float] = 78 * mm


class ReportGenerationError(Exception):
    """Le rapport ne peut pas être produit pour cette analyse."""


@dataclass(frozen=True, slots=True)
class ReportResult:
    """Rapport produit et son empreinte."""

    pdf: bytes
    signature: str
    generated_at: datetime


# --------------------------------------------------------------------------- #
# Texte
# --------------------------------------------------------------------------- #


def pdf_safe(text: str) -> str:
    """Retire les caractères que les polices de base de ReportLab ne savent pas rendre.

    Helvetica est encodée en WinAnsi : les accents passent, mais un emoji comme
    celui qui ouvre `PLACEHOLDER_MODEL_WARNING` apparaîtrait en carré noir ou
    ferait échouer le rendu. La mise en forme du bandeau porte déjà l'alerte
    visuelle que l'emoji apportait.
    """
    return text.encode("latin-1", "ignore").decode("latin-1").strip()


def format_probability(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f} %"


def build_automatic_summary(analysis: Analysis, status: ModelStatus) -> str:
    """Synthèse rédigée à partir des valeurs enregistrées.

    Gabarit déterministe issu des chiffres, et non un modèle de langage : le
    distinguer évite de laisser croire qu'un raisonnement a eu lieu.
    """
    if status == "placeholder":
        return (
            "Aucune synthèse n'est produite : le modèle déployé est un modèle de "
            "démonstration, ses sorties ne décrivent pas le cliché analysé."
        )

    if analysis.prediction is None:
        return "Aucun résultat de modèle n'est disponible pour cette analyse."

    label = PREDICTION_LABELS_FR.get(analysis.prediction, analysis.prediction)
    probability = format_probability(analysis.probability)

    sentences = [
        f"Le modèle oriente vers une classification « {label} », avec une "
        f"probabilité estimée de malignité de {probability}.",
    ]

    if analysis.region_width:
        sentences.append(
            "La carte Grad-CAM fait ressortir une zone d'intérêt principale, "
            f"délimitée par le rectangle vert de l'image annotée "
            f"({analysis.region_width} × {analysis.region_height} pixels)."
        )

    if status == "trained_unvalidated":
        sentences.append(
            "Ces valeurs proviennent d'un modèle dont la validité clinique n'a "
            "pas été établie : elles sont fournies à titre académique et "
            "démonstratif."
        )

    sentences.append(
        "Cette synthèse est produite automatiquement à partir des valeurs "
        "ci-dessus. Elle ne constitue pas une interprétation clinique."
    )
    return " ".join(sentences)


# --------------------------------------------------------------------------- #
# Signature
# --------------------------------------------------------------------------- #


def canonical_timestamp(value: datetime) -> str:
    """Représentation stable d'une date pour la signature.

    Deux précautions, chacune motivée par une façon concrète de casser la
    vérification :

    - le fuseau est normalisé en UTC, et une date sans fuseau est lue comme de
      l'UTC : PostgreSQL rend les `TIMESTAMPTZ` avec leur fuseau, SQLite les rend
      nus, et la même donnée produirait sinon deux chaînes différentes ;
    - les sous-secondes sont retirées : un backend de stockage qui arrondirait
      les microsecondes invaliderait silencieusement tous les rapports déjà émis.
      Le document n'affiche de toute façon l'heure qu'à la seconde.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat()


def signature_payload(analysis: Analysis, patient: Patient, generated_at: datetime) -> str:
    """Chaîne canonique couvrant les faits que le rapport affirme.

    Modifier l'un de ces éléments après coup change l'empreinte : un rapport
    présenté comme se rapportant à une autre patiente, ou annonçant un autre
    résultat, ne se vérifie plus.

    La **lecture médicale** en fait partie, et pas seulement la sortie du modèle :
    c'est elle qui fait foi cliniquement, et c'est elle qu'un tiers aurait le plus
    d'intérêt à modifier. Sans elle dans le périmètre, un rapport portant un
    ancien commentaire continuerait à se vérifier après révision du dossier.
    """
    fields = [
        str(analysis.id),
        patient.code,
        analysis.prediction or "",
        f"{analysis.probability:.6f}" if analysis.probability is not None else "",
        analysis.model_version or "",
        analysis.preprocessing_version or "",
        analysis.doctor_comment or "",
        "1" if analysis.doctor_validated else "0",
        canonical_timestamp(generated_at),
    ]
    return "|".join(fields)


def sign(payload: str) -> str:
    """Empreinte HMAC-SHA256, dérivée de `SECRET_KEY`.

    Détecte l'altération d'un rapport, mais **n'est pas** une signature
    électronique qualifiée : il n'y a ni certificat, ni autorité, ni horodatage
    opposable. Voir docs/PRODUCTION_CHECKLIST.md.
    """
    return hmac.new(
        settings.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_signature(analysis: Analysis, patient: Patient) -> bool:
    """Recalcule l'empreinte et la compare à celle enregistrée."""
    if not analysis.report_signature or not analysis.report_generated_at:
        return False

    expected = sign(signature_payload(analysis, patient, analysis.report_generated_at))
    # Comparaison en temps constant : la vérification est exposée par l'API.
    return hmac.compare_digest(expected, analysis.report_signature)


# --------------------------------------------------------------------------- #
# Mise en page
# --------------------------------------------------------------------------- #


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "BreastTitle",
            parent=base["Title"],
            fontSize=20,
            spaceAfter=2,
            textColor=colors.HexColor("#8B2252"),
        ),
        "subtitle": ParagraphStyle(
            "BreastSubtitle",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#555555"),
        ),
        "heading": ParagraphStyle(
            "BreastHeading",
            parent=base["Heading2"],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=4,
            textColor=colors.HexColor("#8B2252"),
        ),
        "body": ParagraphStyle(
            "BreastBody", parent=base["Normal"], fontSize=9, leading=12, alignment=TA_JUSTIFY
        ),
        "caption": ParagraphStyle(
            "BreastCaption",
            parent=base["Normal"],
            fontSize=7.5,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"),
        ),
        "alert": ParagraphStyle(
            "BreastAlert",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#7F1D1D"),
        ),
        "mono": ParagraphStyle(
            "BreastMono", parent=base["Normal"], fontName="Courier", fontSize=7.5, leading=10
        ),
        "cell": ParagraphStyle(
            "BreastCell", parent=base["Normal"], fontSize=9, leading=11.5
        ),
    }


def _alert_box(text: str, styles: dict[str, ParagraphStyle]) -> Table:
    """Encadré rouge, destiné à être vu avant toute autre chose."""
    table = Table([[Paragraph(pdf_safe(text), styles["alert"])]], colWidths=[170 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEE2E2")),
                ("BOX", (0, 0), (-1, -1), 1.6, colors.HexColor("#B91C1C")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _info_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    """Tableau libellé/valeur.

    La valeur est un `Paragraph` et non une chaîne : une chaîne nue déborde de sa
    cellule au lieu de passer à la ligne, ce qui tronque silencieusement les
    champs longs — les antécédents médicaux en premier.
    """
    table = Table(
        [[label, Paragraph(pdf_safe(value), styles["cell"])] for label, value in rows],
        colWidths=[50 * mm, 120 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#E5E7EB")),
            ]
        )
    )
    return table


def _scaled_image(data: bytes, width: float = IMAGE_WIDTH) -> Image:
    """Image mise à l'échelle en conservant ses proportions."""
    reader = ImageReader(BytesIO(data))
    source_width, source_height = reader.getSize()
    return Image(BytesIO(data), width=width, height=width * source_height / source_width)


class _ReportCanvas(Canvas):
    """Canvas ajoutant le filigrane, le pied de page et la pagination.

    La pagination exige de connaître le nombre total de pages : les pages sont
    donc accumulées puis rendues à la fermeture du document.
    """

    def __init__(
        self, *args, watermark: str | None = None, reference: str = "", **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        #: Texte du filigrane, `None` pour ne rien imprimer.
        self._watermark = watermark
        self._reference = reference
        self._pages: list[dict] = []

    def showPage(self) -> None:  # noqa: N802 - API de ReportLab
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._pages)
        for page in self._pages:
            self.__dict__.update(page)
            self._draw_watermark()
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_watermark(self) -> None:
        if not self._watermark:
            return

        width, height = A4
        self.saveState()
        self.translate(width / 2, height / 2)
        self.rotate(38)
        # Le texte du cas « non validé » est plus long : réduire le corps évite
        # qu'il ne déborde de la page une fois incliné.
        self.setFont("Helvetica-Bold", 21 if len(self._watermark) <= 46 else 15)
        # Rouge très clair : lisible sans masquer le texte ni les images.
        self.setFillColorRGB(0.85, 0.20, 0.20, alpha=0.16)
        for offset in (150, 0, -150):
            self.drawCentredString(0, offset, self._watermark)
        self.restoreState()

    def _draw_footer(self, total: int) -> None:
        width, _ = A4
        self.saveState()
        self.setFont("Helvetica", 7)
        self.setFillColor(colors.HexColor("#6B7280"))
        self.drawString(20 * mm, 12 * mm, pdf_safe(f"BreastAI - Rapport {self._reference}"))
        self.drawRightString(width - 20 * mm, 12 * mm, f"Page {self._page_number()} / {total}")
        self.setStrokeColor(colors.HexColor("#E5E7EB"))
        self.line(20 * mm, 15 * mm, width - 20 * mm, 15 * mm)
        self.restoreState()

    def _page_number(self) -> int:
        return self._pageNumber


# --------------------------------------------------------------------------- #
# Construction du document
# --------------------------------------------------------------------------- #


def _render_original_preview(analysis: Analysis) -> bytes | None:
    """Décode le fichier d'origine pour l'insérer dans le PDF.

    Rendu à la demande plutôt que stocké : un DICOM ne s'affiche pas dans un PDF,
    et conserver une copie supplémentaire de chaque mammographie sur un stockage
    non chiffré ne se justifie pas pour un aperçu.
    """
    try:
        image, _ = load_image(storage_service.read_bytes(analysis.image_path))
        return encode_png(image)
    except Exception:  # noqa: BLE001 - un aperçu absent ne doit pas bloquer le rapport
        logger.warning("Aperçu de l'image d'origine indisponible pour %s", analysis.id)
        return None


def build_pdf(
    analysis: Analysis,
    patient: Patient,
    generated_by: User | None,
    generated_at: datetime,
    signature: str,
    status: ModelStatus,
) -> bytes:
    """Assemble le document."""
    styles = _styles()
    buffer = BytesIO()
    reference = str(analysis.id)[:8].upper()

    document = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=20 * mm,
        title=f"BreastAI - Rapport {reference}",
        author="BreastAI",
        creator="BreastAI",
        subject="Compte rendu d'aide au depistage",
    )
    frame = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        id="corps",
    )
    document.addPageTemplates([PageTemplate(id="rapport", frames=[frame])])

    watermark_text = WATERMARK_BY_STATUS[status]

    story: list = []

    # ---------- En-tête ----------
    story.append(Paragraph("BreastAI", styles["title"]))
    story.append(
        Paragraph(
            pdf_safe(
                f"Compte rendu d'aide au dépistage · Référence {reference} · "
                f"Établi le {generated_at.strftime('%d/%m/%Y à %H:%M')} UTC"
            ),
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 8))

    # ---------- Avertissement placeholder, avant tout le reste ----------
    provenance_warning = model_warning_for(status)
    if provenance_warning:
        story.append(_alert_box(provenance_warning, styles))
        story.append(Spacer(1, 8))

    # ---------- Patient ----------
    story.append(Paragraph("Patient", styles["heading"]))
    birth_date = patient.birth_date.strftime("%d/%m/%Y") if patient.birth_date else "—"
    story.append(
        _info_table(
            [
                ("Code dossier", patient.code),
                ("Nom", patient.full_name),
                ("Date de naissance", birth_date),
                ("Sexe", {"F": "Féminin", "M": "Masculin", "O": "Autre"}.get(patient.sex, "—")),
                ("Antécédents", patient.medical_history or "Non renseignés"),
            ],
            styles,
        )
    )

    # ---------- Examen ----------
    story.append(Paragraph("Examen", styles["heading"]))
    story.append(
        _info_table(
            [
                ("Fichier déposé", analysis.original_filename),
                ("Format", (analysis.image_format or "—").upper()),
                ("Date de l'analyse", analysis.created_at.strftime("%d/%m/%Y à %H:%M")),
                ("Statut", STATUS_LABELS_FR.get(analysis.status, analysis.status)),
            ],
            styles,
        )
    )

    # ---------- Résultat ----------
    story.append(Paragraph("Résultat du modèle", styles["heading"]))
    prediction = (
        PREDICTION_LABELS_FR.get(analysis.prediction, analysis.prediction)
        if analysis.prediction
        else "—"
    )
    story.append(
        _info_table(
            [
                ("Classification", prediction),
                ("Probabilité de malignité", format_probability(analysis.probability)),
                ("Score de confiance", format_probability(analysis.confidence)),
                (
                    "Temps d'inférence",
                    f"{analysis.inference_time_ms:.0f} ms"
                    if analysis.inference_time_ms
                    else "—",
                ),
                ("Modèle", analysis.model_version or "—"),
                ("Prétraitement", analysis.preprocessing_version or "—"),
            ],
            styles,
        )
    )

    # ---------- Images ----------
    original = _render_original_preview(analysis)
    gradcam = (
        storage_service.read_bytes(analysis.gradcam_path)
        if analysis.gradcam_path and storage_service.exists(analysis.gradcam_path)
        else None
    )

    if original or gradcam:
        cells = [
            [
                _scaled_image(original) if original else Paragraph("Indisponible", styles["body"]),
                _scaled_image(gradcam) if gradcam else Paragraph("Indisponible", styles["body"]),
            ],
            [
                Paragraph("Image d'origine, telle que déposée", styles["caption"]),
                Paragraph(
                    "Grad-CAM sur l'image prétraitée (384 × 384, ratio conservé)",
                    styles["caption"],
                ),
            ],
        ]
        images = Table(cells, colWidths=[85 * mm, 85 * mm])
        images.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    # Alignées en haut : les deux images n'ont pas le même cadrage,
                    # l'une étant redimensionnée et complétée par du remplissage.
                    ("VALIGN", (0, 0), (-1, 0), "TOP"),
                    ("TOPPADDING", (0, 1), (-1, 1), 3),
                ]
            )
        )
        # Le titre, les images et leur mise en garde restent solidaires : un
        # saut de page entre les deux laisserait la carte Grad-CAM seule, sans
        # le rappel qui conditionne sa lecture.
        story.append(
            KeepTogether(
                [
                    Paragraph("Imagerie", styles["heading"]),
                    images,
                    Spacer(1, 4),
                    Paragraph(pdf_safe(GRADCAM_DISCLAIMER), styles["body"]),
                ]
            )
        )

    # ---------- Synthèse et lecture médicale ----------
    story.append(Paragraph("Synthèse automatique", styles["heading"]))
    story.append(
        Paragraph(pdf_safe(build_automatic_summary(analysis, status)), styles["body"])
    )

    story.append(Paragraph("Lecture médicale", styles["heading"]))
    story.append(
        Paragraph(
            pdf_safe(analysis.doctor_comment or "Aucun commentaire n'a été saisi."),
            styles["body"],
        )
    )
    story.append(Spacer(1, 3))
    story.append(
        Paragraph(
            "Validation par le médecin : "
            + ("OUI" if analysis.doctor_validated else "NON"),
            styles["body"],
        )
    )

    # ---------- Avertissement médical ----------
    story.append(Spacer(1, 8))
    story.append(_alert_box(MEDICAL_DISCLAIMER, styles))

    # ---------- Signature ----------
    signatory = generated_by.full_name if generated_by else "Non identifié"
    signature_block = [
        Paragraph("Signature numérique", styles["heading"]),
        _info_table(
            [
                ("Établi par", signatory),
                ("Date d'établissement", generated_at.strftime("%d/%m/%Y %H:%M:%S UTC")),
                ("Algorithme", "HMAC-SHA256"),
            ],
            styles,
        ),
        Spacer(1, 3),
        Paragraph(f"Empreinte : {signature}", styles["mono"]),
        Spacer(1, 3),
        Paragraph(
            pdf_safe(
                "Cette empreinte permet de vérifier que le rapport correspond bien "
                "à l'analyse enregistrée. Il ne s'agit pas d'une signature "
                "électronique qualifiée : elle n'engage aucune autorité de "
                "certification et ne vaut pas horodatage opposable."
            ),
            styles["body"],
        ),
    ]
    story.append(KeepTogether(signature_block))

    document.build(
        story,
        canvasmaker=lambda *args, **kwargs: _ReportCanvas(
            *args, watermark=watermark_text, reference=reference, **kwargs
        ),
    )
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #


def generate_report(
    db: Session, analysis: Analysis, generated_by: User | None = None
) -> ReportResult:
    """Produit le PDF, l'archive et enregistre son empreinte.

    Refuse les analyses non terminées : un compte rendu sans résultat n'a pas
    d'objet, et en produire un laisserait croire qu'une lecture a eu lieu.
    """
    if analysis.status != AnalysisStatus.COMPLETED.value:
        raise ReportGenerationError(
            "Le rapport n'est disponible que pour une analyse terminée "
            f"(statut actuel : {STATUS_LABELS_FR.get(analysis.status, analysis.status)})."
        )

    patient = analysis.patient
    if patient is None:
        raise ReportGenerationError("Dossier patient introuvable pour cette analyse.")

    generated_at = datetime.now(UTC)
    signature = sign(signature_payload(analysis, patient, generated_at))
    status = derive_model_status(
        is_placeholder_version(analysis.model_version), analysis.clinically_validated
    )

    pdf = build_pdf(
        analysis=analysis,
        patient=patient,
        generated_by=generated_by,
        generated_at=generated_at,
        signature=signature,
        status=status,
    )

    directory = storage_service.analysis_directory(analysis.patient_id, analysis.id)
    analysis.report_path = storage_service.save_bytes(directory, REPORT_FILENAME, pdf)
    analysis.report_signature = signature
    analysis.report_generated_at = generated_at
    db.commit()
    db.refresh(analysis)

    logger.info(
        "Rapport généré pour l'analyse %s (%d octets, modèle : %s).",
        analysis.id,
        len(pdf),
        status,
    )
    return ReportResult(pdf=pdf, signature=signature, generated_at=generated_at)


def get_or_generate(
    db: Session, analysis: Analysis, generated_by: User | None = None
) -> bytes:
    """Renvoie le PDF archivé, ou le produit s'il n'existe pas encore."""
    if analysis.report_path and storage_service.exists(analysis.report_path):
        return storage_service.read_bytes(analysis.report_path)
    return generate_report(db, analysis, generated_by).pdf
