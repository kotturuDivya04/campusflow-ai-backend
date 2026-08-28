"""
Security utilities: password hashing and JWT access tokens.

Seed users carry bcrypt ($2b$) hashes, so verification uses bcrypt via passlib
when it is installed (see requirements.txt). To keep this module importable in
minimal environments (CI without the web stack), both passlib and PyJWT are
imported lazily and a stdlib PBKDF2 scheme is used for any locally-created
password when passlib is absent. Verification transparently handles bcrypt,
PBKDF2, and (never in production) is extensible.
"""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import hmac
import os
from typing import Any

from app.core.config import settings

# --- password hashing -------------------------------------------------------
try:  # pragma: no cover - depends on optional dependency
    from passlib.context import CryptContext

    _pwd_context: Any = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _HAS_PASSLIB = True
except Exception:  # passlib/bcrypt not installed
    _pwd_context = None
    _HAS_PASSLIB = False


def hash_password(password: str) -> str:
    if _HAS_PASSLIB:
        return _pwd_context.hash(password)
    # Fallback PBKDF2 scheme, clearly namespaced so it is never confused with bcrypt.
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return "pbkdf2_sha256$200000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iters, salt_b64, dk_b64 = password_hash.split("$")
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(dk_b64)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
            return hmac.compare_digest(dk, expected)
        except Exception:
            return False
    # bcrypt (seed data) — requires passlib/bcrypt.
    if _HAS_PASSLIB:
        try:
            return _pwd_context.verify(password, password_hash)
        except Exception:
            return False
    # No verifier available for bcrypt in this environment.
    return False


# --- JWT --------------------------------------------------------------------
def create_access_token(*, subject: str, roles: list[str],
                        expires_minutes: int | None = None) -> str:
    import jwt  # PyJWT

    now = _dt.datetime.now(_dt.timezone.utc)
    exp = now + _dt.timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "roles": roles, "iat": now, "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    import jwt  # PyJWT

    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
