"""Compte utilisateur de la plateforme."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.roles import ROLE_VALUES, UserRole
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.patient import Patient


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base, TimestampMixin):
    """Utilisateur authentifié : administrateur, médecin/radiologue ou chercheur."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('" + "', '".join(ROLE_VALUES) + "')",
            name="ck_users_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.DOCTOR.value)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    #: Date du dernier changement de mot de passe. Embarquée dans les jetons :
    #: la modifier invalide tous les jetons émis auparavant.
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patients: Mapped[list[Patient]] = relationship(back_populates="created_by")
    analyses: Mapped[list[Analysis]] = relationship(back_populates="created_by")

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def __repr__(self) -> str:  # pragma: no cover - confort de débogage
        return f"<User {self.email} ({self.role})>"
