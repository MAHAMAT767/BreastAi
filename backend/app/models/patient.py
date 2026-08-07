"""Dossier patient."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.user import User

#: Sexe déclaré. Le cancer du sein masculin est rare mais réel : ne pas restreindre à « F ».
SEX_VALUES: tuple[str, ...] = ("F", "M", "O")


class Patient(Base, TimestampMixin):
    """Patient suivi sur la plateforme.

    La suppression est **logique** (`is_deleted`) et jamais physique : un dossier
    médical rattaché à des analyses déjà rendues doit rester reconstituable.
    """

    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint(
            "sex IN ('" + "', '".join(SEX_VALUES) + "')",
            name="ck_patients_sex",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    #: Identifiant lisible attribué par la structure de soins (ex. « TCD-2026-0142 »).
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(1), nullable=False, default="F")

    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(255))

    #: Antécédents, facteurs de risque, traitements en cours.
    medical_history: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[User | None] = relationship(back_populates="patients")

    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self) -> str:  # pragma: no cover - confort de débogage
        return f"<Patient {self.code}>"
