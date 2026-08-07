"""Gestion des comptes utilisateurs — réservée aux administrateurs."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AdminUser
from app.database.session import get_db
from app.models.audit_log import AuditAction
from app.models.schemas import UserCreate, UserRead, UserUpdate
from app.services import audit_service, user_service

router = APIRouter(prefix="/users", tags=["utilisateurs"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
)
def create_user(
    request: Request, db: DbSession, admin: AdminUser, payload: UserCreate
) -> UserRead:
    try:
        user = user_service.create_user(
            db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            role=payload.role,
        )
    except user_service.EmailAlreadyUsedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà pour cette adresse e-mail.",
        ) from exc

    audit_service.record(
        db,
        AuditAction.USER_CREATE,
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        request=request,
    )
    return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead], summary="Lister les comptes")
def list_users(db: DbSession, admin: AdminUser) -> list[UserRead]:
    del admin  # l'autorisation suffit ici
    return [UserRead.model_validate(user) for user in user_service.list_users(db)]


@router.get("/{user_id}", response_model=UserRead, summary="Consulter un compte")
def get_user(user_id: uuid.UUID, db: DbSession, admin: AdminUser) -> UserRead:
    del admin
    user = user_service.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable.")
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead, summary="Modifier un compte")
def update_user(
    user_id: uuid.UUID,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    payload: UserUpdate,
) -> UserRead:
    user = user_service.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable.")

    # Un administrateur ne peut pas se retirer lui-même ses droits ou se désactiver :
    # la plateforme se retrouverait sans administrateur actif.
    if user.id == admin.id:
        if payload.is_active is False or (payload.role is not None and payload.role != user.role):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un administrateur ne peut pas modifier son propre rôle ni se désactiver.",
            )

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.role is not None:
        user.role = payload.role.value
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)

    audit_service.record(
        db,
        AuditAction.USER_UPDATE,
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        request=request,
    )
    return UserRead.model_validate(user)
