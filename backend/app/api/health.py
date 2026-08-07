"""Endpoints de diagnostic de l'API."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.config import settings

router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    app_name: str


@router.get("/health", response_model=HealthResponse, summary="État de l'API v1")
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.environment,
        app_name=settings.app_name,
    )
