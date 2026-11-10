from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext
from app.config import settings

# bcrypt is the default scheme for new hashes. sha256_crypt is kept only so
# existing deployments can still log in; it is deprecated and gets rehashed on
# the next login (verify_and_update) once a new password is set.
pwd_context = CryptContext(
    schemes=["bcrypt", "sha256_crypt"],
    deprecated=["sha256_crypt"],
    bcrypt__rounds=12,
)

# A real bcrypt hash of a throwaway value. Verifying an unknown username
# against it keeps response timing close to a wrong password, so an attacker
# cannot enumerate accounts by measuring the login latency.
DUMMY_PASSWORD_HASH = pwd_context.hash("timing-defense-not-a-real-password")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def verify_password_and_update(
    plain_password: str, hashed_password: str
) -> Tuple[bool, Optional[str]]:
    """Verify a password and return a stronger hash when the stored one is old."""
    try:
        return pwd_context.verify_and_update(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False, None


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {
        **data,
        "iat": now,
        "nbf": now,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "iat"]},
        )
        if payload.get("type") != "access":
            return None
        return payload
    except (InvalidTokenError, ValueError, TypeError):
        return None
