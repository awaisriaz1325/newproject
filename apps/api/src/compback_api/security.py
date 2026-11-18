"""Security primitives: password hashing, opaque tokens, TOTP, recovery codes (ADR-0004)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2id with library defaults (RFC 9106 recommended profile)
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256
_DUMMY_HASH = _hasher.hash("timing-equalizer-not-a-password")


class WeakPasswordError(ValueError):
    pass


def validate_password(password: str, email: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise WeakPasswordError("password is too long")
    if email and email.split("@", maxsplit=1)[0].lower() in password.lower():
        raise WeakPasswordError("password must not contain your email name")
    if len(set(password)) < 5:
        raise WeakPasswordError("password is too repetitive")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    """Constant-ish time: verifies against a dummy hash when the user has none."""
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def new_token() -> str:
    """256-bit URL-safe random token."""
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, account: str, issuer: str = "CompBack") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    code = code.strip().replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return False
    return bool(pyotp.TOTP(secret).verify(code, valid_window=1))


_RC_ALPHABET = string.ascii_lowercase + string.digits


def new_recovery_codes(n: int = 10) -> list[str]:
    return [
        "-".join("".join(secrets.choice(_RC_ALPHABET) for _ in range(5)) for _ in range(2))
        for _ in range(n)
    ]


def recovery_code_digest(code: str) -> str:
    return hashlib.sha256(code.strip().lower().encode()).hexdigest()


def new_invite_code() -> str:
    alphabet = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))
