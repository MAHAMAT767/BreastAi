"""Création et consultation des analyses de mammographies.

Phase 3 : dépôt du fichier, validation, prétraitement, archivage. L'analyse reste
au statut `pending` — l'inférence est branchée en Phase 4.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Final

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.ai.preprocessing import (
    ALLOWED_EXTENSIONS,
    ImageLoadError,
    UnsupportedFormatError,
    encode_png,
    preprocess_for_inference,
)
from app.config import settings
from app.models.analysis import Analysis, AnalysisStatus
from app.models.patient import Patient
from app.services import storage_service

logger = logging.getLogger(__name__)

ORIGINAL_FILENAME: Final[str] = "original"
PROCESSED_FILENAME: Final[str] = "processed.png"


class UploadValidationError(Exception):
    """Le fichier déposé est refusé avant même le décodage."""


class PreprocessingFailedError(Exception):
    """Le fichier a passé la validation mais n'a pas pu être prétraité."""


def max_upload_bytes() -> int:
    return settings.max_upload_size_mb * 1024 * 1024


def validate_upload(filename: str, data: bytes) -> None:
    """Contrôles bon marché, avant tout décodage.

    L'extension et la taille sont vérifiées d'abord parce qu'elles coûtent
    presque rien : inutile de décoder 50 Mo pour découvrir ensuite que le fichier
    est trop gros.
    """
    if not data:
        raise UploadValidationError("Fichier vide.")

    if len(data) > max_upload_bytes():
        raise UploadValidationError(
            f"Fichier trop volumineux : maximum {settings.max_upload_size_mb} Mo."
        )

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            "Extension non acceptée. Formats attendus : DICOM (.dcm), PNG, JPG, JPEG."
        )


def create_from_upload(
    db: Session,
    *,
    patient: Patient,
    filename: str,
    data: bytes,
    created_by_id: uuid.UUID | None = None,
) -> Analysis:
    """Valide, prétraite et enregistre une mammographie.

    L'analyse n'est écrite en base qu'une fois le prétraitement réussi : une
    ligne pointant vers des fichiers inexistants serait pire qu'une absence de
    ligne.
    """
    validate_upload(filename, data)

    try:
        result = preprocess_for_inference(data)
    except UnsupportedFormatError as exc:
        raise UploadValidationError(str(exc)) from exc
    except ImageLoadError as exc:
        raise PreprocessingFailedError(str(exc)) from exc

    analysis_id = uuid.uuid4()
    directory = storage_service.analysis_directory(patient.id, analysis_id)

    safe_name = storage_service.sanitize_filename(filename)
    extension = Path(safe_name).suffix.lower() or ".bin"
    original_path = storage_service.save_bytes(
        directory, f"{ORIGINAL_FILENAME}{extension}", data
    )
    processed_path = storage_service.save_bytes(
        directory, PROCESSED_FILENAME, encode_png(result.display)
    )

    analysis = Analysis(
        id=analysis_id,
        patient_id=patient.id,
        created_by_id=created_by_id,
        original_filename=safe_name,
        image_path=original_path,
        processed_image_path=processed_path,
        image_format=result.image_format.value,
        file_size_bytes=len(data),
        status=AnalysisStatus.PENDING.value,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    logger.info(
        "Analyse %s créée pour le patient %s (%s, %.0f ms de prétraitement).",
        analysis.id,
        patient.code,
        result.image_format.value,
        result.duration_ms,
    )
    return analysis


def get_by_id(db: Session, analysis_id: uuid.UUID) -> Analysis | None:
    return db.get(Analysis, analysis_id)


def _base_query(patient_id: uuid.UUID | None) -> Select[tuple[Analysis]]:
    statement = select(Analysis)
    if patient_id is not None:
        statement = statement.where(Analysis.patient_id == patient_id)
    return statement


def count_analyses(db: Session, *, patient_id: uuid.UUID | None = None) -> int:
    statement = select(func.count()).select_from(Analysis)
    if patient_id is not None:
        statement = statement.where(Analysis.patient_id == patient_id)
    return db.scalar(statement) or 0


def list_analyses(
    db: Session,
    *,
    patient_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Analysis]:
    """Liste paginée, la plus récente d'abord."""
    statement = (
        _base_query(patient_id).order_by(Analysis.created_at.desc()).limit(limit).offset(offset)
    )
    return list(db.scalars(statement))


def set_doctor_review(
    db: Session, analysis: Analysis, *, comment: str | None, validated: bool | None
) -> Analysis:
    """Enregistre la lecture du médecin, qui prime sur la sortie du modèle."""
    if comment is not None:
        analysis.doctor_comment = comment
    if validated is not None:
        analysis.doctor_validated = validated
    db.commit()
    db.refresh(analysis)
    return analysis
