"""Schémas Pydantic exposés par l'API (entrées et sorties HTTP).

Séparés des entités SQLAlchemy : ce qui entre et sort de l'API ne doit jamais
être dicté par la forme des tables. En particulier, `hashed_password` n'apparaît
dans aucun schéma de sortie.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.auth.roles import UserRole
from app.auth.security import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH
from app.disclaimer import MEDICAL_DISCLAIMER

ItemT = TypeVar("ItemT")


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


# --------------------------------------------------------------------------- #
# Patients
# --------------------------------------------------------------------------- #


class PatientBase(BaseModel):
    code: str = Field(min_length=1, max_length=50, description="Identifiant du dossier.")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: date | None = None
    sex: Literal["F", "M", "O"] = "F"
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)
    medical_history: str | None = None
    notes: str | None = None

    @field_validator("birth_date")
    @classmethod
    def _refuse_future_birth_date(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("La date de naissance ne peut pas être dans le futur.")
        return value


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    """Mise à jour partielle : seuls les champs fournis sont modifiés."""

    code: str | None = Field(default=None, min_length=1, max_length=50)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    birth_date: date | None = None
    sex: Literal["F", "M", "O"] | None = None
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)
    medical_history: str | None = None
    notes: str | None = None


class PatientRead(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Analyses
# --------------------------------------------------------------------------- #


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    original_filename: str
    image_format: str | None = None
    file_size_bytes: int | None = None
    status: str

    #: Renseignés à partir de la Phase 4 seulement.
    prediction: str | None = None
    probability: float | None = None
    confidence: float | None = None
    inference_time_ms: float | None = None
    model_version: str | None = None
    error_message: str | None = None

    doctor_comment: str | None = None
    doctor_validated: bool
    created_at: datetime

    #: Rappelé sur chaque analyse : le résultat ne vaut pas diagnostic.
    disclaimer: str = MEDICAL_DISCLAIMER


class AnalysisReview(BaseModel):
    """Lecture du médecin, qui prime sur la sortie du modèle."""

    doctor_comment: str | None = None
    doctor_validated: bool | None = None


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #


class Page(BaseModel, Generic[ItemT]):
    """Enveloppe de pagination commune aux listes."""

    items: list[ItemT]
    total: int = Field(description="Nombre total d'éléments, tous filtres appliqués.")
    limit: int
    offset: int
