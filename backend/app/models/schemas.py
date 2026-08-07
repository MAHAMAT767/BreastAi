"""Schémas Pydantic exposés par l'API (entrées et sorties HTTP).

Séparés des entités SQLAlchemy : ce qui entre et sort de l'API ne doit jamais
être dicté par la forme des tables. En particulier, `hashed_password` n'apparaît
dans aucun schéma de sortie.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.auth.roles import UserRole
from app.auth.security import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH


def _validate_password_strength(value: str) -> str:
    """Refuse les mots de passe trop courts ou trop longs pour bcrypt."""
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères."
        )
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Le mot de passe ne doit pas dépasser {MAX_PASSWORD_BYTES} octets."
        )
    return value


# --------------------------------------------------------------------------- #
# Utilisateurs
# --------------------------------------------------------------------------- #


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.DOCTOR


class UserCreate(UserBase):
    password: str

    _check_password = field_validator("password")(_validate_password_strength)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Authentification
# --------------------------------------------------------------------------- #


class TokenPair(BaseModel):
    """Réponse de connexion et de renouvellement."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Durée de vie du jeton d'accès, en secondes.")


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    _check_password = field_validator("new_password")(_validate_password_strength)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    _check_password = field_validator("new_password")(_validate_password_strength)


class MessageResponse(BaseModel):
    """Réponse générique, sans détail exploitable par un attaquant."""

    message: str
