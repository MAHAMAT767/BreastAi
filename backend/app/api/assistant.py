"""Assistant conversationnel adossé à une analyse.

Ce module n'utilise pas `from __future__ import annotations`, pour la même
raison que `app/api/auth.py` : le décorateur de limitation de débit enveloppe la
route avec `functools.wraps`, qui ne transporte pas `__globals__`, et FastAPI ne
saurait alors plus résoudre les annotations différées.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import ClinicalUser
from app.auth.rate_limit import limiter
from app.config import settings
from app.database.session import get_db
from app.models.analysis import Analysis
from app.models.audit_log import AuditAction
from app.models.schemas import AssistantAnswerRead, AssistantAsk, AssistantStatus
from app.services import analysis_service, assistant_service, audit_service
from app.services.assistant_service import AssistantMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])

DbSession = Annotated[Session, Depends(get_db)]

ENABLED_NOTICE = (
    "Les questions portent sur une analyse précise. Le contexte transmis au "
    "fournisseur contient les sorties du modèle, l'âge et le sexe — jamais le "
    "nom, le code dossier, la date de naissance, les coordonnées, ni le "
    "commentaire du médecin."
)

DISABLED_NOTICE = (
    "L'assistant n'est pas configuré sur ce serveur. L'analyse, les images et le "
    "rapport restent disponibles sans lui."
)


def _get_analysis_or_404(db: Session, analysis_id: uuid.UUID) -> Analysis:
    analysis = analysis_service.get_by_id(db, analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analyse introuvable."
        )
    return analysis


@router.get("/status", response_model=AssistantStatus, summary="État de l'assistant")
def assistant_status(user: ClinicalUser) -> AssistantStatus:
    """Permet à l'interface de masquer la conversation si elle est indisponible."""
    del user
    enabled = settings.assistant_enabled
    return AssistantStatus(
        enabled=enabled,
        model=settings.assistant_model if enabled else None,
        notice=ENABLED_NOTICE if enabled else DISABLED_NOTICE,
    )


@router.post(
    "/analyses/{analysis_id}",
    response_model=AssistantAnswerRead,
    summary="Poser une question sur une analyse",
)
@limiter.limit(settings.assistant_rate_limit)
def ask_about_analysis(
    analysis_id: uuid.UUID,
    request: Request,
    response: Response,
    db: DbSession,
    user: ClinicalUser,
    payload: AssistantAsk,
) -> AssistantAnswerRead:
    """Répond en langage naturel à une question portant sur l'analyse.

    Le serveur ne conserve aucune conversation : l'historique est renvoyé par le
    client à chaque question. Une trace d'audit est écrite, sans le texte de la
    question — elle peut contenir des éléments cliniques que le journal n'a pas
    vocation à retenir.

    `response` n'est pas utilisé ici : slowapi s'en sert pour les en-têtes de quota.
    """
    analysis = _get_analysis_or_404(db, analysis_id)

    history = [
        AssistantMessage(role=message.role, content=message.content)
        for message in payload.history
    ]

    try:
        answer = assistant_service.ask(
            analysis=analysis,
            patient=analysis.patient,
            question=payload.question,
            history=history,
        )
    except assistant_service.AssistantDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except assistant_service.AssistantQuotaError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except assistant_service.AssistantUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except assistant_service.AssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    audit_service.record(
        db,
        AuditAction.ASSISTANT_QUERY,
        user_id=user.id,
        resource_type="analysis",
        resource_id=str(analysis.id),
        request=request,
        detail=f"Assistant interrogé ({answer.model})",
    )

    return AssistantAnswerRead(
        answer=answer.answer,
        answer_body=answer.answer_body,
        model=answer.model,
        is_placeholder_model=answer.is_placeholder_model,
        model_warning=answer.model_warning,
        context_sent=answer.context_sent,
        usage=answer.usage,
    )
