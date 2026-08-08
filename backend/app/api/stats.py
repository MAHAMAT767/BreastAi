"""Indicateurs agrégés du tableau de bord."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.database.session import get_db
from app.models.schemas import DashboardStats
from app.services import stats_service

router = APIRouter(prefix="/stats", tags=["statistiques"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/dashboard", response_model=DashboardStats, summary="Tableau de bord")
def dashboard(db: DbSession, user: CurrentUser) -> DashboardStats:
    """Compteurs, répartition mensuelle et indicateurs du modèle.

    Ouvert à **tous les rôles**, y compris `researcher` : ces chiffres sont
    agrégés et ne désignent aucune patiente. C'est précisément le périmètre de
    ce rôle, à qui les dossiers nominatifs restent fermés.
    """
    del user
    return DashboardStats.model_validate(stats_service.build_dashboard(db))
