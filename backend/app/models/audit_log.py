"""Journal des actions sensibles."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AuditAction(StrEnum):
    """Actions tracées. À étendre au fil des phases."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_CONFIRM = "password_reset_confirm"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    PATIENT_CREATE = "patient_create"
    PATIENT_UPDATE = "patient_update"
    PATIENT_DELETE = "patient_delete"
    PATIENT_VIEW = "patient_view"
    ANALYSIS_CREATE = "analysis_create"
    ANALYSIS_VIEW = "analysis_view"
    REPORT_EXPORT = "report_export"
    #: Une question à l'assistant fait sortir du contexte clinique vers un
    #: fournisseur tiers : la trace importe, le texte de la question non.
    ASSISTANT_QUERY = "assistant_query"


class AuditLog(Base):
    """Trace immuable d'une action.

    `user_id` est nullable : une tentative de connexion échouée sur une adresse
    inconnue doit être journalisée alors qu'aucun utilisateur ne correspond.
    Aucune donnée patient identifiante ne doit être écrite dans `detail`.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    ip_address: Mapped[str | None] = mapped_column(String(45))  # IPv6 = 45 caractères
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - confort de débogage
        return f"<AuditLog {self.action} {self.created_at}>"
