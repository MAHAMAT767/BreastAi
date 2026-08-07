"""Agrégateur des routeurs de l'API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import analyses, auth, health, patients, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(patients.router)
api_router.include_router(analyses.router)

# Montages à venir :
#   api_router.include_router(reports.router)    # Phase 5
#   api_router.include_router(assistant.router)  # Phase 7
