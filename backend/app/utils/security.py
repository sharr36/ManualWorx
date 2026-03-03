"""Password hashing and session token utilities."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password using argon2."""
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an argon2 hash."""
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def generate_session_token() -> str:
    """Generate a cryptographically secure session token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hash a session token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()
