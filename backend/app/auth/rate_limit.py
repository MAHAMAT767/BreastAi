"""Limitation de débit sur les endpoints sensibles.

Le stockage est **en mémoire, par processus**. C'est suffisant pour un
déploiement mono-instance, mais chaque réplique compterait ses propres
tentatives : avec N répliques, un attaquant obtient N fois le quota. Avant tout
déploiement multi-instance, basculer `storage_uri` sur un backend partagé
(Redis, Memcached) — voir docs/API.md.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)


def client_key(request: Request) -> str:
    """Clé de comptage : l'adresse d'origine, en tenant compte du reverse proxy.

    `get_remote_address` ne lit pas `X-Forwarded-For` : derrière un proxy, toutes
    les requêtes partageraient l'IP du proxy et le quota serait épuisé pour tout
    le monde par un seul attaquant.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=client_key,
    enabled=settings.rate_limit_enabled,
    storage_uri="memory://",
    headers_enabled=True,
)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Réponse 429 en français, sans révéler le quota exact restant."""
    logger.warning(
        "Quota dépassé sur %s depuis %s (%s)", request.url.path, client_key(request), exc.detail
    )
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": (
                "Trop de tentatives. Patientez quelques instants avant de réessayer."
            )
        },
    )


def install_rate_limiting(app: FastAPI) -> None:
    """Branche le limiteur sur l'application.

    `app.state.limiter` est la convention attendue par slowapi : les décorateurs
    `@limiter.limit(...)` posés sur les routes le retrouvent par là.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


def reset() -> None:
    """Vide les compteurs. Utilisé par les tests, jamais en production."""
    limiter.reset()
