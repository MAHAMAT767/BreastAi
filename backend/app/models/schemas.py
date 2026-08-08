"""Schémas Pydantic exposés par l'API (entrées et sorties HTTP).

Séparés des entités SQLAlchemy : ce qui entre et sort de l'API ne doit jamais
être dicté par la forme des tables. En particulier, `hashed_password` n'apparaît
dans aucun schéma de sortie.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Final, Generic, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.ai.inference.loader import is_placeholder_version
from app.auth.roles import UserRole
from app.auth.security import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH
from app.disclaimer import (
    GRADCAM_DISCLAIMER,
    MEDICAL_DISCLAIMER,
    PLACEHOLDER_MODEL_WARNING,
)
from app.models.email_address import EmailAddress

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
    email: EmailAddress
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.DOCTOR


class UserCreate(UserBase):
    password: str

    _check_password = field_validator("password")(_validate_password_strength)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    """Profil renvoyé par l'API.

    Ne dérive **pas** de `UserBase` et déclare `email: str` et non `EmailStr` :
    revalider une adresse en sortie ne protège de rien — la donnée est déjà en
    base — mais transforme le moindre écart en erreur 500. Concrètement, un
    compte créé sur un domaine interne (`.local`, ce qu'utilise typiquement le
    réseau d'un établissement de soins) faisait planter `GET /auth/me` : le
    compte pouvait se connecter mais son profil était illisible.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
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
    email: EmailAddress


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
    email: EmailAddress | None = None
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
    email: EmailAddress | None = None
    address: str | None = Field(default=None, max_length=255)
    medical_history: str | None = None
    notes: str | None = None


class PatientRead(BaseModel):
    """Dossier renvoyé par l'API.

    Comme `UserRead`, ne dérive pas du schéma d'entrée : `email` est un `str`
    en sortie, pour qu'une adresse déjà enregistrée ne puisse pas rendre un
    dossier patient impossible à afficher.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    first_name: str
    last_name: str
    full_name: str
    birth_date: date | None = None
    sex: Literal["F", "M", "O"]
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    medical_history: str | None = None
    notes: str | None = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Analyses
# --------------------------------------------------------------------------- #


class SuspiciousRegionRead(BaseModel):
    """Rectangle Grad-CAM, en pixels dans l'image prétraitée (384×384)."""

    x: int
    y: int
    width: int
    height: int


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    original_filename: str
    image_format: str | None = None
    file_size_bytes: int | None = None
    status: str

    prediction: str | None = None
    #: Probabilité de la classe **maligne**, quelle que soit la classe prédite.
    probability: float | None = None
    confidence: float | None = None
    inference_time_ms: float | None = None
    model_version: str | None = None
    preprocessing_version: str | None = None
    error_message: str | None = None

    doctor_comment: str | None = None
    doctor_validated: bool
    created_at: datetime

    # ---------- Champs calculés ----------
    #: Vrai tant qu'aucun modèle entraîné sur mammographies n'est déployé.
    is_placeholder_model: bool = False
    #: Renseigné uniquement dans ce cas, avec un texte sans ambiguïté.
    model_warning: str | None = None
    has_gradcam: bool = False
    gradcam_disclaimer: str | None = None
    suspicious_region: SuspiciousRegionRead | None = None
    has_report: bool = False
    report_generated_at: datetime | None = None
    report_signature: str | None = None

    #: Rappelé sur chaque analyse : le résultat ne vaut pas diagnostic.
    disclaimer: str = MEDICAL_DISCLAIMER

    @model_validator(mode="after")
    def _annotate_model_provenance(self) -> AnalysisRead:
        """Dérive les avertissements du `model_version` enregistré.

        La provenance est déduite de la valeur stockée, et non d'un état courant :
        une analyse produite par le placeholder reste signalée comme telle même
        après le déploiement d'un vrai modèle.
        """
        self.is_placeholder_model = is_placeholder_version(self.model_version)
        if self.is_placeholder_model:
            self.model_warning = PLACEHOLDER_MODEL_WARNING
        if self.has_gradcam:
            self.gradcam_disclaimer = GRADCAM_DISCLAIMER
        return self

    @classmethod
    def from_analysis(cls, analysis: object) -> AnalysisRead:
        """Construit la réponse en assemblant les champs dérivés de l'entité."""
        read = cls.model_validate(analysis)
        read.has_gradcam = bool(getattr(analysis, "gradcam_path", None))
        read.has_report = bool(getattr(analysis, "report_path", None))

        if getattr(analysis, "region_width", None):
            read.suspicious_region = SuspiciousRegionRead(
                x=analysis.region_x,
                y=analysis.region_y,
                width=analysis.region_width,
                height=analysis.region_height,
            )

        return cls._annotate_model_provenance(read)


class AnalysisReview(BaseModel):
    """Lecture du médecin, qui prime sur la sortie du modèle."""

    doctor_comment: str | None = None
    doctor_validated: bool | None = None


# --------------------------------------------------------------------------- #
# Rapports
# --------------------------------------------------------------------------- #


class ReportInfo(BaseModel):
    """Métadonnées d'un rapport produit."""

    analysis_id: uuid.UUID
    signature: str = Field(description="Empreinte HMAC-SHA256 imprimée sur le document.")
    generated_at: datetime
    size_bytes: int
    is_placeholder_model: bool
    model_warning: str | None = None


class ReportVerification(BaseModel):
    """Résultat du contrôle d'intégrité d'un rapport."""

    analysis_id: uuid.UUID
    has_report: bool
    signature_valid: bool
    generated_at: datetime | None = None
    detail: str


# --------------------------------------------------------------------------- #
# Tableau de bord
# --------------------------------------------------------------------------- #

#: Pourquoi aucune « précision du modèle » n'est publiée.
ACCURACY_UNAVAILABLE_NOTE: Final[str] = (
    "Aucun taux d'exactitude n'est calculable : il faudrait un diagnostic de "
    "référence par cas (biopsie, suivi), qui n'est pas enregistré. Le taux "
    "affiché est celui des analyses relues et validées par un médecin — il "
    "mesure l'activité de relecture, pas la justesse du modèle."
)


class MonthlyCount(BaseModel):
    # `from_attributes` ne se propage pas aux modèles imbriqués : sans cette
    # ligne, la liste de dataclasses du service est refusée à la validation.
    model_config = ConfigDict(from_attributes=True)

    month: str = Field(description="Mois au format AAAA-MM.")
    total: int
    benign: int
    malignant: int


class DashboardStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_patients: int
    total_analyses: int
    completed_analyses: int
    pending_analyses: int
    failed_analyses: int
    benign_count: int
    malignant_count: int
    average_inference_time_ms: float | None = None
    doctor_validated_count: int
    doctor_validation_rate: float | None = None
    monthly: list[MonthlyCount]
    model_versions: list[str]

    is_placeholder_model: bool
    model_warning: str | None = None

    #: Toujours faux en l'état — voir `accuracy_note`.
    accuracy_available: bool = False
    accuracy_note: str = ACCURACY_UNAVAILABLE_NOTE

    @model_validator(mode="after")
    def _attach_model_warning(self) -> DashboardStats:
        if self.is_placeholder_model and self.model_warning is None:
            self.model_warning = PLACEHOLDER_MODEL_WARNING
        return self


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #


class Page(BaseModel, Generic[ItemT]):
    """Enveloppe de pagination commune aux listes."""

    items: list[ItemT]
    total: int = Field(description="Nombre total d'éléments, tous filtres appliqués.")
    limit: int
    offset: int
