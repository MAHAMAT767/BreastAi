"""Endpoints de dépôt et de consultation des analyses de mammographies."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.dependencies import ClinicalUser
from app.database.session import get_db
from app.models.analysis import Analysis
from app.models.audit_log import AuditAction
from app.models.schemas import AnalysisRead, AnalysisReview, Page
from app.services import (
    analysis_service,
    audit_service,
    patient_service,
    storage_service,
)

router = APIRouter(prefix="/analyses", tags=["analyses"])

DbSession = Annotated[Session, Depends(get_db)]


def _get_or_404(db: Session, analysis_id: uuid.UUID) -> Analysis:
    analysis = analysis_service.get_by_id(db, analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analyse introuvable."
        )
    return analysis


@router.post(
    "",
    response_model=AnalysisRead,
    status_code=status.HTTP_201_CREATED,
    summary="Déposer une mammographie",
)
async def upload_analysis(
    request: Request,
    db: DbSession,
    user: ClinicalUser,
    patient_id: Annotated[uuid.UUID, Form(description="Dossier patient rattaché.")],
    file: Annotated[UploadFile, File(description="DICOM, PNG, JPG ou JPEG.")],
) -> AnalysisRead:
    """Dépose une mammographie, la valide et la prétraite.

    L'inférence n'est pas encore branchée : l'analyse reste au statut `pending`
    jusqu'à la Phase 4.
    """
    patient = patient_service.get_by_id(db, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dossier patient introuvable."
        )

    data = await file.read()

    try:
        analysis = analysis_service.create_from_upload(
            db,
            patient=patient,
            filename=file.filename or "sans-nom",
            data=data,
            created_by_id=user.id,
        )
    except analysis_service.UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except analysis_service.PreprocessingFailedError as exc:
        # 422 : le fichier est du bon type mais son contenu est inexploitable.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    audit_service.record(
        db,
        AuditAction.ANALYSIS_CREATE,
        user_id=user.id,
        resource_type="analysis",
        resource_id=str(analysis.id),
        request=request,
    )
    return AnalysisRead.from_analysis(analysis)


@router.get("", response_model=Page[AnalysisRead], summary="Lister les analyses")
def list_analyses(
    db: DbSession,
    user: ClinicalUser,
    patient_id: Annotated[uuid.UUID | None, Query(description="Filtrer sur un dossier.")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AnalysisRead]:
    del user
    analyses = analysis_service.list_analyses(
        db, patient_id=patient_id, limit=limit, offset=offset
    )
    return Page[AnalysisRead](
        items=[AnalysisRead.from_analysis(analysis) for analysis in analyses],
        total=analysis_service.count_analyses(db, patient_id=patient_id),
        limit=limit,
        offset=offset,
    )


@router.get("/{analysis_id}", response_model=AnalysisRead, summary="Consulter une analyse")
def get_analysis(
    analysis_id: uuid.UUID, request: Request, db: DbSession, user: ClinicalUser
) -> AnalysisRead:
    analysis = _get_or_404(db, analysis_id)
    audit_service.record(
        db,
        AuditAction.ANALYSIS_VIEW,
        user_id=user.id,
        resource_type="analysis",
        resource_id=str(analysis.id),
        request=request,
    )
    return AnalysisRead.from_analysis(analysis)


@router.get(
    "/{analysis_id}/image",
    summary="Télécharger l'image d'une analyse",
    response_class=Response,
)
def get_analysis_image(
    analysis_id: uuid.UUID,
    db: DbSession,
    user: ClinicalUser,
    kind: Annotated[
        Literal["original", "processed", "gradcam"],
        Query(description="Image déposée, image prétraitée, ou superposition Grad-CAM."),
    ] = "processed",
) -> Response:
    """Sert l'image d'une analyse.

    Le fichier transite par l'API plutôt que par un service de fichiers statiques :
    une mammographie ne doit pas être accessible sans contrôle d'accès.
    """
    del user
    analysis = _get_or_404(db, analysis_id)

    paths = {
        "original": analysis.image_path,
        "processed": analysis.processed_image_path,
        "gradcam": analysis.gradcam_path,
    }
    relative_path = paths[kind]
    if not relative_path or not storage_service.exists(relative_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image indisponible."
        )

    media_type = "application/octet-stream" if kind == "original" else "image/png"
    return Response(
        content=storage_service.read_bytes(relative_path),
        media_type=media_type,
        headers={"Cache-Control": "private, no-store"},
    )


@router.post(
    "/{analysis_id}/infer",
    response_model=AnalysisRead,
    summary="Rejouer l'inférence",
)
def rerun_inference(
    analysis_id: uuid.UUID, request: Request, db: DbSession, user: ClinicalUser
) -> AnalysisRead:
    """Relance le modèle sur une analyse déjà déposée.

    Prévu pour le remplacement du modèle : les analyses existantes peuvent être
    réévaluées à partir du cliché archivé, sans redemander la mammographie.
    """
    analysis = _get_or_404(db, analysis_id)
    analysis = analysis_service.rerun_inference(db, analysis)

    audit_service.record(
        db,
        AuditAction.ANALYSIS_CREATE,
        user_id=user.id,
        resource_type="analysis",
        resource_id=str(analysis.id),
        request=request,
        detail="Inférence rejouée",
    )
    return AnalysisRead.from_analysis(analysis)


@router.patch(
    "/{analysis_id}/review", response_model=AnalysisRead, summary="Lecture du médecin"
)
def review_analysis(
    analysis_id: uuid.UUID,
    db: DbSession,
    user: ClinicalUser,
    payload: AnalysisReview,
) -> AnalysisRead:
    """Enregistre le commentaire et la validation du médecin.

    C'est cette lecture qui fait foi cliniquement, pas la sortie du modèle.
    """
    del user
    analysis = _get_or_404(db, analysis_id)
    analysis = analysis_service.set_doctor_review(
        db,
        analysis,
        comment=payload.doctor_comment,
        validated=payload.doctor_validated,
    )
    return AnalysisRead.from_analysis(analysis)
