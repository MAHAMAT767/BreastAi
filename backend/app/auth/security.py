"""Primitives cryptographiques : hachage des mots de passe et jetons JWT."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import bcrypt
import jwt

from app.config import settings

#: bcrypt ignore silencieusement tout octet au-delà du 72e. Plutôt que de laisser
#: deux mots de passe distincts partager un hash, on refuse explicitement.
MAX_PASSWORD_BYTES: Final[int] = 72

MIN_PASSWORD_LENGTH: Final[int] = 12

#: Marge tolérée en comparant l'horodatage du mot de passe porté par un jeton à
#: celui stocké en base. Elle n'absorbe que le bruit de sérialisation JSON du
#: flottant : la garder large rouvrirait une fenêtre pendant laquelle un jeton de
#: réinitialisation déjà consommé resterait valable.
TIMESTAMP_TOLERANCE_SECONDS: Final[float] = 0.001

TOKEN_TYPE_ACCESS: Final[str] = "access"
TOKEN_TYPE_REFRESH: Final[str] = "refresh"
TOKEN_TYPE_RESET: Final[str] = "reset"


class TokenError(Exception):
    """Jeton absent, expiré, malformé ou de type inattendu."""


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Contenu utile d'un jeton validé."""

    subject: str
    token_type: str
    issued_at: datetime
    expires_at: datetime
    role: str | None = None
    password_changed_at: float | None = None
    jti: str | None = None


# --------------------------------------------------------------------------- #
# Mots de passe
# --------------------------------------------------------------------------- #


def _encode_password(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Le mot de passe dépasse {MAX_PASSWORD_BYTES} octets, limite de bcrypt."
        )
    return encoded


def hash_password(password: str) -> str:
    """Hache un mot de passe avec bcrypt (sel aléatoire inclus dans le résultat)."""
    return bcrypt.hashpw(_encode_password(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare un mot de passe en clair à son hash, en temps constant.

    Renvoie ``False`` plutôt que de lever si l'entrée est invalide : un appelant
    ne doit jamais pouvoir distinguer « hash corrompu » de « mauvais mot de passe ».
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# Jetons JWT
# --------------------------------------------------------------------------- #


def to_utc_timestamp(value: datetime) -> float:
    """Convertit une date en timestamp epoch, en supposant UTC si la tzinfo manque.

    PostgreSQL rend les `TIMESTAMPTZ` avec leur fuseau, SQLite les rend nus.
    Sans cette normalisation, la même donnée produirait deux timestamps
    différents selon le backend, et l'invalidation des jetons se déclencherait
    à tort ou pas du tout.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    **claims: Any,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
        **{key: value for key, value in claims.items() if value is not None},
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(
    subject: str,
    role: str,
    password_changed_at: datetime,
    expires_delta: timedelta | None = None,
) -> str:
    """Jeton d'accès court, porteur du rôle pour éviter un aller-retour en base.

    `password_changed_at` est embarqué afin qu'un changement de mot de passe
    invalide immédiatement tous les jetons émis auparavant.
    """
    return _create_token(
        subject,
        TOKEN_TYPE_ACCESS,
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes),
        role=role,
        pwd_at=to_utc_timestamp(password_changed_at),
    )


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Jeton de renouvellement long, sans rôle : il ne donne accès à aucune ressource."""
    return _create_token(
        subject,
        TOKEN_TYPE_REFRESH,
        expires_delta or timedelta(days=settings.refresh_token_expire_days),
    )


def create_password_reset_token(
    subject: str,
    password_changed_at: datetime,
    expires_delta: timedelta | None = None,
) -> str:
    """Jeton de réinitialisation, à usage unique de fait.

    Il embarque l'horodatage du dernier changement de mot de passe : dès que le
    mot de passe est modifié, le jeton ne correspond plus et devient inutilisable,
    ce qui évite d'avoir à stocker et purger une table de jetons.
    """
    return _create_token(
        subject,
        TOKEN_TYPE_RESET,
        expires_delta or timedelta(minutes=settings.password_reset_token_expire_minutes),
        pwd_at=to_utc_timestamp(password_changed_at),
    )


def decode_token(token: str, expected_type: str | None = None) -> TokenPayload:
    """Valide la signature et l'expiration d'un jeton, puis en extrait le contenu.

    Lève `TokenError` pour toute anomalie — y compris un type de jeton inattendu,
    afin qu'un refresh token ne puisse pas servir de jeton d'accès.
    """
    try:
        raw: dict[str, Any] = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Jeton expiré.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Jeton invalide.") from exc

    token_type = raw.get("type")
    if expected_type is not None and token_type != expected_type:
        raise TokenError(
            f"Type de jeton inattendu : {token_type!r} au lieu de {expected_type!r}."
        )

    subject = raw.get("sub")
    if not subject:
        raise TokenError("Jeton sans sujet.")

    return TokenPayload(
        subject=subject,
        token_type=str(token_type),
        issued_at=datetime.fromtimestamp(raw["iat"], tz=UTC),
        expires_at=datetime.fromtimestamp(raw["exp"], tz=UTC),
        role=raw.get("role"),
        password_changed_at=raw.get("pwd_at"),
        jti=raw.get("jti"),
    )
