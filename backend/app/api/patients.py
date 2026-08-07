"""Endpoints de gestion des dossiers patients.

Réservés aux rôles cliniques (`admin`, `doctor`) : le rôle `researcher` n'a pas
vocation à accéder à des dossiers nominatifs.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import ClinicalUser
from app.database.session import get_db
from app.models.audit_log import AuditAction
from app.models.patient import Patient
from app.models.schemas import (
    MessageResponse,
    Page,
    PatientCreate,
    PatientRead,
    PatientUpdate,
)
from app.services import audit_service, patient_service

router = APIRouter(prefix="/patients", tags=["patients"])

DbSession = Annotated[Session, Depends(get_db)]


def _get_or_404(db: Session, patient_id: uuid.UUID) -> Patient:
    patient = patient_service.get_by_id(db, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dossier patient introuvable."
        )
    return patient


@router.post(
    "",
    response_model=PatientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un dossier patient",
)
def create_patient(
    request: Request, db: DbSession, user: ClinicalUser, payload: PatientCreate
) -> PatientRead:
    try:
        patient = patient_service.create_patient(
            db,
            created_by_id=user.id,
            **payload.model_dump(),
        )
    except patient_service.PatientCodeAlreadyUsedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un dossier existe déjà pour ce code patient.",
        ) from exc

    audit_service.record(
        db,
        AuditAction.PATIENT_CREATE,
        user_id=user.id,
        resource_type="patient",
        resource_id=str(patient.id),
        request=request,
    )
    return PatientRead.model_validate(patient)


@router.get("", response_model=Page[PatientRead], summary="Rechercher des patients")
def list_patients(
    db: DbSession,
    user: ClinicalUser,
    search: Annotated[
        str | None, Query(description="Recherche sur le code, le prénom ou le nom.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[PatientRead]:
    del user  # l'autorisation suffit
    patients = patient_service.list_patients(db, search=search, limit=limit, offset=offset)
    return Page[PatientRead](
        items=[PatientRead.model_validate(patient) for patient in patients],
        total=patient_service.count_patients(db, search=search),
        limit=limit,
        offset=offset,
    )


@router.get("/{patient_id}", response_model=PatientRead, summary="Consulter un dossier")
def get_patient(
    patient_id: uuid.UUID, request: Request, db: DbSession, user: ClinicalUser
) -> PatientRead:
    patient = _get_or_404(db, patient_id)

    # La consultation d'un dossier est elle-même une action tracée : savoir qui a
    # ouvert quel dossier fait partie de la protection des données de santé.
    audit_service.record(
        db,
        AuditAction.PATIENT_VIEW,
        user_id=user.id,
        resource_type="patient",
        resource_id=str(patient.id),
        request=request,
    )
    return PatientRead.model_validate(patient)


@router.patch("/{patient_id}", response_model=PatientRead, summary="Modifier un dossier")
def update_patient(
    patient_id: uuid.UUID,
    request: Request,
    db: DbSession,
    user: ClinicalUser,
    payload: PatientUpdate,
) -> PatientRead:
    patient = _get_or_404(db, patient_id)

    try:
        patient = patient_service.update_patient(
            db, patient, payload.model_dump(exclude_unset=True)
        )
    except patient_service.PatientCodeAlreadyUsedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un dossier existe déjà pour ce code patient.",
        ) from exc

    audit_service.record(
        db,
        AuditAction.PATIENT_UPDATE,
        user_id=user.id,
        resource_type="patient",
        resource_id=str(patient.id),
        request=request,
    )
    return PatientRead.model_validate(patient)


@router.delete(
    "/{patient_id}", response_model=MessageResponse, summary="Supprimer un dossier"
)
def delete_patient(
    patient_id: uuid.UUID, request: Request, db: DbSession, user: ClinicalUser
) -> MessageResponse:
    """Suppression **logique**.

    Les données restent en base et les analyses déjà rendues restent rattachées :
    un compte rendu remis à une patiente doit rester reconstituable.
    """
    patient = _get_or_404(db, patient_id)
    patient_service.soft_delete(db, patient)

    audit_service.record(
        db,
        AuditAction.PATIENT_DELETE,
        user_id=user.id,
        resource_type="patient",
        resource_id=str(patient.id),
        request=request,
    )
    return MessageResponse(message="Dossier patient supprimé.")
