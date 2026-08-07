"""Endpoints d'authentification.

Ce module n'utilise **pas** `from __future__ import annotations`, contrairement au
reste du backend, et il ne faut pas le rajouter.

Les décorateurs `@limiter.limit(...)` de slowapi enveloppent la fonction avec
`functools.wraps`, qui ne transporte pas `__globals__`. FastAPI résout les
annotations différées via le `__globals__` de la fonction appelée : sur une route
ainsi enveloppée, il chercherait `DbSession` dans les globales de slowapi, ne le
trouverait pas, et prendrait `db` et `form_data` pour de simples paramètres de
requête — d'où des 422 sur toutes les connexions. Avec des annotations évaluées
immédiatement, la question ne se pose pas.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.auth.rate_limit import limiter
from app.auth.security import (
    TIMESTAMP_TOLERANCE_SECONDS,
    TOKEN_TYPE_REFRESH,
    TOKEN_TYPE_RESET,
    TokenError,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    to_utc_timestamp,
    verify_password,
)
from app.config import settings
from app.database.session import get_db
from app.models.audit_log import AuditAction
from app.models.schemas import (
    MessageResponse,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TokenPair,
    UserRead,
)
from app.services import audit_service, user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentification"])

DbSession = Annotated[Session, Depends(get_db)]

#: Message unique renvoyé par la demande de réinitialisation, que l'adresse existe
#: ou non : répondre différemment permettrait d'énumérer les comptes.
RESET_GENERIC_MESSAGE = (
    "Si un compte existe pour cette adresse, un lien de réinitialisation a été envoyé."
)


def _issue_token_pair(user_id: uuid.UUID, role: str, password_changed_at) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user_id), role, password_changed_at),
        refresh_token=create_refresh_token(str(user_id)),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenPair, summary="Connexion")
@limiter.limit(settings.login_rate_limit)
def login(
    request: Request,
    response: Response,
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenPair:
    """Échange un couple identifiant/mot de passe contre une paire de jetons.

    Le champ `username` du formulaire OAuth2 reçoit l'adresse e-mail.

    `response` n'est pas utilisé ici : slowapi s'en sert pour poser les en-têtes
    `X-RateLimit-*`, qui indiquent au client le quota restant.
    """
    user = user_service.authenticate(db, form_data.username, form_data.password)

    if user is None:
        existing = user_service.get_by_email(db, form_data.username)
        audit_service.record(
            db,
            AuditAction.LOGIN_FAILURE,
            user_id=existing.id if existing else None,
            request=request,
            detail=f"Échec de connexion pour {user_service.normalize_email(form_data.username)}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Adresse e-mail ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_service.record_login(db, user)
    audit_service.record(
        db, AuditAction.LOGIN_SUCCESS, user_id=user.id, request=request
    )
    return _issue_token_pair(user.id, user.role, user.password_changed_at)


@router.post("/refresh", response_model=TokenPair, summary="Renouvellement des jetons")
def refresh(request: Request, db: DbSession, payload: RefreshRequest) -> TokenPair:
    """Émet une nouvelle paire de jetons à partir d'un jeton de renouvellement."""
    try:
        token = decode_token(payload.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
        user_id = uuid.UUID(token.subject)
    except (TokenError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton de renouvellement invalide ou expiré.",
        ) from exc

    user = user_service.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton de renouvellement invalide ou expiré.",
        )

    audit_service.record(db, AuditAction.TOKEN_REFRESH, user_id=user.id, request=request)
    return _issue_token_pair(user.id, user.role, user.password_changed_at)


@router.post("/logout", response_model=MessageResponse, summary="Déconnexion")
def logout(request: Request, db: DbSession, current_user: CurrentUser) -> MessageResponse:
    """Journalise la déconnexion.

    Les jetons JWT étant sans état, le serveur ne peut pas les révoquer
    individuellement : c'est au client de les effacer. Pour couper réellement
    toutes les sessions d'un compte, changer son mot de passe.
    """
    audit_service.record(db, AuditAction.LOGOUT, user_id=current_user.id, request=request)
    return MessageResponse(
        message="Déconnexion enregistrée. Effacez les jetons côté client."
    )


@router.get("/me", response_model=UserRead, summary="Profil courant")
def read_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post(
    "/password/change",
    response_model=MessageResponse,
    summary="Changement de mot de passe",
)
def change_password(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    payload: PasswordChange,
) -> MessageResponse:
    """Change le mot de passe du compte connecté et invalide les jetons existants."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect.",
        )

    user_service.set_password(db, current_user, payload.new_password)
    audit_service.record(
        db, AuditAction.PASSWORD_RESET_CONFIRM, user_id=current_user.id, request=request
    )
    return MessageResponse(
        message="Mot de passe modifié. Les jetons précédents ne sont plus valides."
    )


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    summary="Demande de réinitialisation",
)
@limiter.limit(settings.password_reset_rate_limit)
def request_password_reset(
    request: Request, response: Response, db: DbSession, payload: PasswordResetRequest
) -> MessageResponse:
    """Génère un jeton de réinitialisation pour l'adresse indiquée.

    L'envoi par e-mail n'est pas encore branché : le jeton est écrit dans les
    journaux du serveur. Il n'est **jamais** renvoyé dans la réponse HTTP, sans
    quoi n'importe qui pourrait réinitialiser le mot de passe d'autrui.
    """
    user = user_service.get_by_email(db, payload.email)

    if user is not None and user.is_active:
        token = create_password_reset_token(str(user.id), user.password_changed_at)
        # TODO(phase 8) : envoyer par e-mail au lieu de journaliser.
        logger.warning(
            "Jeton de réinitialisation généré pour %s (valable %s minutes) : %s",
            user.email,
            settings.password_reset_token_expire_minutes,
            token,
        )
        audit_service.record(
            db, AuditAction.PASSWORD_RESET_REQUEST, user_id=user.id, request=request
        )

    return MessageResponse(message=RESET_GENERIC_MESSAGE)


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    summary="Confirmation de réinitialisation",
)
def confirm_password_reset(
    request: Request, db: DbSession, payload: PasswordResetConfirm
) -> MessageResponse:
    """Applique un nouveau mot de passe à partir d'un jeton de réinitialisation."""
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Jeton de réinitialisation invalide ou expiré.",
    )

    try:
        token = decode_token(payload.token, expected_type=TOKEN_TYPE_RESET)
        user_id = uuid.UUID(token.subject)
    except (TokenError, ValueError) as exc:
        raise invalid from exc

    user = user_service.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise invalid

    # Usage unique : le jeton porte l'horodatage du mot de passe au moment de son
    # émission. Dès qu'un mot de passe est posé, l'horodatage bouge et le jeton
    # ne correspond plus.
    if (
        token.password_changed_at is None
        or to_utc_timestamp(user.password_changed_at)
        > token.password_changed_at + TIMESTAMP_TOLERANCE_SECONDS
    ):
        raise invalid

    user_service.set_password(db, user, payload.new_password)
    audit_service.record(
        db, AuditAction.PASSWORD_RESET_CONFIRM, user_id=user.id, request=request
    )
    return MessageResponse(message="Mot de passe réinitialisé. Vous pouvez vous connecter.")
