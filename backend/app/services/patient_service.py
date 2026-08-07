"""Logique métier des dossiers patients."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.patient import Patient

logger = logging.getLogger(__name__)


class PatientCodeAlreadyUsedError(Exception):
    """Un dossier existe déjà pour ce code."""


def normalize_code(code: str) -> str:
    """Les codes patients sont comparés en majuscules, sans espaces superflus."""
    return code.strip().upper()


def get_by_id(
    db: Session, patient_id: uuid.UUID, *, include_deleted: bool = False
) -> Patient | None:
    patient = db.get(Patient, patient_id)
    if patient is None:
        return None
    if patient.is_deleted and not include_deleted:
        return None
    return patient


def get_by_code(db: Session, code: str) -> Patient | None:
    return db.scalar(select(Patient).where(Patient.code == normalize_code(code)))


def _base_query(include_deleted: bool) -> Select[tuple[Patient]]:
    statement = select(Patient)
    if not include_deleted:
        statement = statement.where(Patient.is_deleted.is_(False))
    return statement


def _apply_search(statement: Select[Any], search: str | None) -> Select[Any]:
    """Filtre sur le code, le prénom ou le nom, sans distinction de casse."""
    if not search or not search.strip():
        return statement

    pattern = f"%{search.strip()}%"
    return statement.where(
        or_(
            Patient.code.ilike(pattern),
            Patient.first_name.ilike(pattern),
            Patient.last_name.ilike(pattern),
        )
    )


def count_patients(db: Session, *, search: str | None = None, include_deleted: bool = False) -> int:
    statement = _apply_search(
        select(func.count()).select_from(Patient), search
    )
    if not include_deleted:
        statement = statement.where(Patient.is_deleted.is_(False))
    return db.scalar(statement) or 0


def list_patients(
    db: Session,
    *,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_deleted: bool = False,
) -> list[Patient]:
    """Liste paginée, la plus récente d'abord."""
    statement = _apply_search(_base_query(include_deleted), search)
    statement = statement.order_by(Patient.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement))


def create_patient(
    db: Session,
    *,
    code: str,
    first_name: str,
    last_name: str,
    created_by_id: uuid.UUID | None = None,
    **fields: Any,
) -> Patient:
    """Crée un dossier. Lève `PatientCodeAlreadyUsedError` si le code est pris."""
    code = normalize_code(code)
    if get_by_code(db, code) is not None:
        raise PatientCodeAlreadyUsedError(code)

    patient = Patient(
        code=code,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        created_by_id=created_by_id,
        **fields,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    logger.info("Dossier patient créé : %s", patient.code)
    return patient


def update_patient(db: Session, patient: Patient, changes: dict[str, Any]) -> Patient:
    """Applique les champs fournis. Le code reste modifiable mais doit rester unique."""
    if "code" in changes and changes["code"] is not None:
        new_code = normalize_code(changes["code"])
        existing = get_by_code(db, new_code)
        if existing is not None and existing.id != patient.id:
            raise PatientCodeAlreadyUsedError(new_code)
        changes["code"] = new_code

    for field, value in changes.items():
        if value is not None:
            setattr(patient, field, value)

    db.commit()
    db.refresh(patient)
    return patient


def soft_delete(db: Session, patient: Patient) -> Patient:
    """Marque le dossier comme supprimé sans effacer les données.

    Les analyses déjà rendues restent rattachées : un compte rendu remis à une
    patiente doit rester reconstituable même si son dossier est retiré des listes.
    """
    patient.is_deleted = True
    patient.deleted_at = datetime.now(UTC)
    db.commit()
    db.refresh(patient)
    logger.info("Dossier patient %s marqué comme supprimé.", patient.code)
    return patient


def restore(db: Session, patient: Patient) -> Patient:
    patient.is_deleted = False
    patient.deleted_at = None
    db.commit()
    db.refresh(patient)
    return patient
