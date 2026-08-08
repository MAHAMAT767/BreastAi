"""Analyse d'une mammographie par le modèle."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.ai import CLASS_NAMES
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class AnalysisStatus(StrEnum):
    """Cycle de vie d'une analyse."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


STATUS_VALUES: tuple[str, ...] = tuple(status.value for status in AnalysisStatus)


class Analysis(Base, TimestampMixin):
    """Résultat d'une analyse, du dépôt de l'image au rapport.

    Les champs de résultat sont nullables : une analyse existe dès l'upload, avant
    que l'inférence n'ait tourné. `model_version` est conservé pour pouvoir
    réinterpréter a posteriori un résultat rendu par un modèle antérieur.
    """

    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('" + "', '".join(STATUS_VALUES) + "')",
            name="ck_analyses_status",
        ),
        CheckConstraint(
            "prediction IS NULL OR prediction IN ('" + "', '".join(CLASS_NAMES) + "')",
            name="ck_analyses_prediction",
        ),
        CheckConstraint(
            "probability IS NULL OR (probability >= 0 AND probability <= 1)",
            name="ck_analyses_probability_range",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_analyses_confidence_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    patient: Mapped[Patient] = relationship(back_populates="analyses")

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[User | None] = relationship(back_populates="analyses")

    # ---------- Image ----------
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    processed_image_path: Mapped[str | None] = mapped_column(String(500))
    gradcam_path: Mapped[str | None] = mapped_column(String(500))
    report_path: Mapped[str | None] = mapped_column(String(500))
    #: Empreinte HMAC-SHA256 des faits du rapport, imprimée sur le document.
    #: Permet de détecter qu'un rapport présenté ne correspond plus à l'analyse
    #: enregistrée. Ce n'est pas une signature électronique qualifiée.
    report_signature: Mapped[str | None] = mapped_column(String(64))
    report_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    image_format: Mapped[str | None] = mapped_column(String(10))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)

    # ---------- Résultat du modèle ----------
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AnalysisStatus.PENDING.value, index=True
    )
    prediction: Mapped[str | None] = mapped_column(String(20), index=True)
    #: Probabilité de la classe maligne, dans [0, 1].
    probability: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    inference_time_ms: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str | None] = mapped_column(String(100))
    #: Version de la chaîne de prétraitement ayant produit les images stockées.
    #: Sans elle, impossible de savoir a posteriori si une analyse ancienne est
    #: comparable à une analyse récente.
    preprocessing_version: Mapped[str | None] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)

    # ---------- Zone saillante Grad-CAM ----------
    #: Rectangle englobant, en pixels dans l'image prétraitée. Il indique où le
    #: modèle a regardé, pas où se trouve une lésion.
    region_x: Mapped[int | None] = mapped_column(Integer)
    region_y: Mapped[int | None] = mapped_column(Integer)
    region_width: Mapped[int | None] = mapped_column(Integer)
    region_height: Mapped[int | None] = mapped_column(Integer)

    # ---------- Lecture médicale ----------
    #: Le médecin confirme ou infirme la sortie du modèle. C'est cette lecture,
    #: et non la prédiction, qui fait foi cliniquement.
    doctor_comment: Mapped[str | None] = mapped_column(Text)
    doctor_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover - confort de débogage
        return f"<Analysis {self.id} {self.status} {self.prediction}>"
