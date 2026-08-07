"""Journalisation des actions sensibles."""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction, AuditLog


def client_ip(request: Request | None) -> str | None:
    """Adresse IP de l'appelant, en tenant compte d'un éventuel reverse proxy."""
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Le premier élément est l'adresse d'origine ; les suivants sont les proxies.
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def record(
    db: Session,
    action: AuditAction,
    *,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request: Request | None = None,
    detail: str | None = None,
    commit: bool = True,
) -> AuditLog:
    """Écrit une entrée de journal.

    `detail` ne doit contenir aucune donnée patient identifiante : le journal est
    consultable par les administrateurs, qui n'ont pas nécessairement à connaître
    le contenu des dossiers.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action.value,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=client_ip(request),
        detail=detail,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry
