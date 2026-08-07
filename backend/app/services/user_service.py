"""Logique métier des comptes utilisateurs."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.roles import UserRole
from app.auth.security import hash_password, verify_password
from app.models.user import User

logger = logging.getLogger(__name__)

#: Hash valide et jetable, vérifié quand aucun compte ne correspond à l'adresse.
#: Il doit être réel : un hash malformé échouerait immédiatement, ce qui rendrait
#: une adresse inconnue mesurable au chronomètre.
_DUMMY_HASH = hash_password("mot-de-passe-factice-anti-timing")


class EmailAlreadyUsedError(Exception):
    """Un compte existe déjà pour cette adresse."""


def normalize_email(email: str) -> str:
    """Les adresses sont comparées en minuscules : la casse ne distingue pas un compte."""
    return email.strip().lower()


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session, *, include_inactive: bool = True) -> list[User]:
    statement = select(User).order_by(User.created_at.desc())
    if not include_inactive:
        statement = statement.where(User.is_active.is_(True))
    return list(db.scalars(statement))


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    role: UserRole = UserRole.DOCTOR,
    is_active: bool = True,
) -> User:
    """Crée un compte. Lève `EmailAlreadyUsedError` si l'adresse est déjà prise."""
    email = normalize_email(email)
    if get_by_email(db, email) is not None:
        raise EmailAlreadyUsedError(email)

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name.strip(),
        role=role.value,
        is_active=is_active,
        password_changed_at=datetime.now(UTC),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Compte créé : %s (%s)", user.email, user.role)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Vérifie les identifiants.

    Renvoie `None` aussi bien pour une adresse inconnue que pour un mot de passe
    faux ou un compte désactivé : l'appelant ne doit pas pouvoir déterminer
    laquelle des trois situations s'applique.
    """
    user = get_by_email(db, email)
    if user is None:
        # Vérification factice : égalise le temps de réponse pour qu'une adresse
        # inconnue ne se distingue pas d'un mot de passe faux.
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def record_login(db: Session, user: User) -> None:
    user.last_login_at = datetime.now(UTC)
    db.commit()


def set_password(db: Session, user: User, new_password: str) -> User:
    """Change le mot de passe et invalide tous les jetons émis auparavant."""
    user.hashed_password = hash_password(new_password)
    user.password_changed_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    logger.info("Mot de passe modifié pour %s", user.email)
    return user


def set_active(db: Session, user: User, is_active: bool) -> User:
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user
