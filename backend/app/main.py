"""Point d'entrée de l'API BreastAI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("breastai")

MEDICAL_DISCLAIMER = (
    "BreastAI est un outil d'aide à la décision. Ses résultats ne constituent pas "
    "un diagnostic et ne remplacent pas l'avis d'un professionnel de santé qualifié."
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Démarrage de %s v%s (%s)", settings.app_name, __version__, settings.environment)
    yield
    logger.info("Arrêt de %s", settings.app_name)


def create_app() -> FastAPI:
    """Construit et configure l'application FastAPI."""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "API d'aide au dépistage du cancer du sein par IA.\n\n"
            f"**Avertissement** : {MEDICAL_DISCLAIMER}"
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["meta"], summary="Racine de l'API")
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "disclaimer": MEDICAL_DISCLAIMER,
        }

    @app.get("/health", tags=["meta"], summary="Sonde de vivacité")
    async def health() -> dict[str, str]:
        """Utilisé par Docker et la plateforme d'hébergement."""
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
