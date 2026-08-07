"""Création et consultation des analyses de mammographies.

Chaîne complète : dépôt → validation → prétraitement → inférence → Grad-CAM.
L'inférence tourne de façon synchrone dans la requête. Sur CPU, EfficientNet-B0
en 384×384 prend quelques centaines de millisecondes : acceptable pour un dépôt
manuel, à repasser en tâche de fond si le volume augmente.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Final

import torch
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.ai.explainability import GradCAM, locate_suspicious_region, overlay_heatmap
from app.ai.explainability import encode_png as encode_overlay_png
from app.ai.inference import Predictor, get_predictor
from app.ai.preprocessing import (
    ALLOWED_EXTENSIONS,
    ImageLoadError,
    PreprocessedImage,
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
GRADCAM_FILENAME: Final[str] = "gradcam.png"


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
        preprocessing_version=result.version,
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

    return run_inference(db, analysis, preprocessed=result)


# --------------------------------------------------------------------------- #
# Inférence et explicabilité
# --------------------------------------------------------------------------- #


def _load_preprocessed(analysis: Analysis) -> PreprocessedImage:
    """Reconstruit le tenseur d'entrée à partir du fichier d'origine archivé.

    On repart de l'original et non de l'image traitée : c'est la seule façon de
    profiter d'une correction du prétraitement lors d'une réexécution.
    """
    return preprocess_for_inference(storage_service.read_bytes(analysis.image_path))


def run_inference(
    db: Session,
    analysis: Analysis,
    *,
    preprocessed: PreprocessedImage | None = None,
    predictor: Predictor | None = None,
) -> Analysis:
    """Exécute la prédiction et le Grad-CAM, puis met l'analyse à jour.

    Un échec n'interrompt pas le dépôt : l'analyse passe au statut `failed` avec
    son message d'erreur, l'image reste archivée et l'inférence est rejouable.
    Perdre une mammographie parce que le modèle a échoué serait bien pire que de
    rendre une analyse sans prédiction.
    """
    analysis.status = AnalysisStatus.PROCESSING.value
    analysis.error_message = None
    db.commit()

    try:
        result = preprocessed or _load_preprocessed(analysis)
        engine = predictor or get_predictor()
        prediction = engine.predict(result.tensor)

        class_index = engine.bundle.class_names.index(prediction.label)
        batch = torch.from_numpy(result.tensor).unsqueeze(0).to(engine.bundle.device)

        with GradCAM(engine.bundle.model, engine.bundle.target_layer) as gradcam:
            cam = gradcam.compute(batch, class_index)

        region = locate_suspicious_region(cam)
        overlay = overlay_heatmap(result.display, cam, region=region)

        directory = storage_service.analysis_directory(analysis.patient_id, analysis.id)
        gradcam_path = storage_service.save_bytes(
            directory, GRADCAM_FILENAME, encode_overlay_png(overlay)
        )

    except Exception as exc:  # noqa: BLE001 - toute défaillance doit être tracée, pas propagée
        logger.exception("Échec de l'inférence sur l'analyse %s", analysis.id)
        analysis.status = AnalysisStatus.FAILED.value
        analysis.error_message = f"{type(exc).__name__}: {exc}"
        db.commit()
        db.refresh(analysis)
        return analysis

    analysis.status = AnalysisStatus.COMPLETED.value
    analysis.prediction = prediction.label
    analysis.probability = prediction.probability
    analysis.confidence = prediction.confidence
    analysis.inference_time_ms = prediction.inference_time_ms
    analysis.model_version = prediction.model_version
    analysis.preprocessing_version = result.version
    analysis.gradcam_path = gradcam_path

    if region is not None:
        analysis.region_x = region.x
        analysis.region_y = region.y
        analysis.region_width = region.width
        analysis.region_height = region.height

    db.commit()
    db.refresh(analysis)

    logger.info(
        "Analyse %s : %s (p=%.3f, %.0f ms, modèle %s).",
        analysis.id,
        prediction.label,
        prediction.probability,
        prediction.inference_time_ms,
        prediction.model_version,
    )
    return analysis


def rerun_inference(db: Session, analysis: Analysis) -> Analysis:
    """Rejoue l'inférence sur une analyse existante.

    Utile après le remplacement du modèle : les analyses déjà rendues peuvent
    être réévaluées sans redemander le cliché.
    """
    return run_inference(db, analysis)


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
