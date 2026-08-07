"""Dépendances FastAPI d'authentification et de contrôle des rôles."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.roles import UserRole
from app.auth.security import (
    TIMESTAMP_TOLERANCE_SECONDS,
    TOKEN_TYPE_ACCESS,
    TokenError,
    decode_token,
    to_utc_timestamp,
)
from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.services import user_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Identifiants invalides ou session expirée.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Résout l'utilisateur porteur du jeton d'accès.

    Le compte est relu en base à chaque requête : un jeton encore valide ne doit
    pas continuer à ouvrir l'accès si le compte a été désactivé entre-temps.
    """
    try:
        payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
        user_id = uuid.UUID(payload.subject)
    except (TokenError, ValueError) as exc:
        raise CREDENTIALS_EXCEPTION from exc

    user = user_service.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise CREDENTIALS_EXCEPTION

    # Un changement de mot de passe postérieur à l'émission invalide le jeton.
    if payload.password_changed_at is not None:
        stored = to_utc_timestamp(user.password_changed_at)
        if stored > payload.password_changed_at + TIMESTAMP_TOLERANCE_SECONDS:
            raise CREDENTIALS_EXCEPTION

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Fabrique une dépendance qui n'autorise que les rôles indiqués.

    Exemple :
        ``Depends(require_roles(UserRole.ADMIN))``
    """
    allowed = {role.value for role in roles}

    def dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Votre rôle ne permet pas d'accéder à cette ressource.",
            )
        return current_user

    return dependency


#: Raccourcis pour les cas les plus fréquents.
require_admin = require_roles(UserRole.ADMIN)
require_clinical = require_roles(UserRole.ADMIN, UserRole.DOCTOR)

AdminUser = Annotated[User, Depends(require_admin)]
ClinicalUser = Annotated[User, Depends(require_clinical)]
