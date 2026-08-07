"""Tests des primitives de sécurité : hachage et jetons."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.auth.security import (
    MAX_PASSWORD_BYTES,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    TOKEN_TYPE_RESET,
    TokenError,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    to_utc_timestamp,
    verify_password,
)

NOW = datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Mots de passe
# --------------------------------------------------------------------------- #


def test_hash_then_verify_roundtrip() -> None:
    hashed = hash_password("un-mot-de-passe-solide")

    assert hashed != "un-mot-de-passe-solide"
    assert verify_password("un-mot-de-passe-solide", hashed)


def test_wrong_password_is_rejected() -> None:
    hashed = hash_password("un-mot-de-passe-solide")

    assert not verify_password("un-autre-mot-de-passe", hashed)


def test_same_password_yields_different_hashes() -> None:
    """Le sel doit être aléatoire, sinon deux comptes identiques se repèrent en base."""
    assert hash_password("identique-12345") != hash_password("identique-12345")


def test_password_longer_than_bcrypt_limit_is_refused() -> None:
    """bcrypt tronque au-delà de 72 octets ; on refuse plutôt que de tronquer en silence."""
    with pytest.raises(ValueError, match="72"):
        hash_password("a" * (MAX_PASSWORD_BYTES + 1))


def test_verify_returns_false_on_malformed_hash() -> None:
    """Un hash corrompu ne doit pas propager d'exception jusqu'à l'appelant."""
    assert not verify_password("peu importe", "ceci-n-est-pas-un-hash")


# --------------------------------------------------------------------------- #
# Jetons
# --------------------------------------------------------------------------- #


def test_access_token_carries_subject_and_role() -> None:
    token = create_access_token("user-1", "doctor", NOW)
    payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)

    assert payload.subject == "user-1"
    assert payload.role == "doctor"
    assert payload.token_type == TOKEN_TYPE_ACCESS


def test_refresh_token_carries_no_role() -> None:
    """Un refresh token ne doit porter aucune autorisation exploitable."""
    payload = decode_token(create_refresh_token("user-1"), expected_type=TOKEN_TYPE_REFRESH)

    assert payload.role is None


def test_refresh_token_cannot_pass_as_access_token() -> None:
    """Confusion de type : c'est la faille classique des implémentations JWT maison."""
    token = create_refresh_token("user-1")

    with pytest.raises(TokenError, match="Type de jeton inattendu"):
        decode_token(token, expected_type=TOKEN_TYPE_ACCESS)


def test_access_token_cannot_pass_as_reset_token() -> None:
    token = create_access_token("user-1", "admin", NOW)

    with pytest.raises(TokenError):
        decode_token(token, expected_type=TOKEN_TYPE_RESET)


def test_expired_token_is_rejected() -> None:
    token = create_access_token("user-1", "doctor", NOW, expires_delta=timedelta(seconds=-1))

    with pytest.raises(TokenError, match="expiré"):
        decode_token(token)


def test_tampered_token_is_rejected() -> None:
    token = create_access_token("user-1", "doctor", NOW)
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}AAAA"

    with pytest.raises(TokenError):
        decode_token(tampered)


def test_tokens_have_distinct_identifiers() -> None:
    """Le `jti` permettra une liste de révocation si le besoin apparaît."""
    first = decode_token(create_access_token("user-1", "doctor", NOW))
    second = decode_token(create_access_token("user-1", "doctor", NOW))

    assert first.jti is not None
    assert first.jti != second.jti


def test_reset_token_embeds_password_timestamp() -> None:
    changed_at = datetime.now(UTC)
    payload = decode_token(
        create_password_reset_token("user-1", changed_at), expected_type=TOKEN_TYPE_RESET
    )

    assert payload.password_changed_at == pytest.approx(changed_at.timestamp())


def test_naive_datetime_is_read_as_utc() -> None:
    """SQLite rend des dates sans fuseau : elles doivent être lues comme de l'UTC."""
    aware = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    naive = datetime(2026, 8, 7, 12, 0)

    assert to_utc_timestamp(naive) == to_utc_timestamp(aware)
