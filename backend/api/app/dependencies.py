import secrets
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.auth import decode_access_token
from app.schemas import TokenData
from app.models import User
from app.schemas import UserRole

oauth2_scheme = HTTPBearer(auto_error=False)


async def _resolve_user(token: str, db: AsyncSession) -> Optional[User]:
    payload = decode_access_token(token)
    if payload is None:
        return None
    username: Optional[str] = payload.get("sub")
    if username is None:
        return None
    token_data = TokenData(username=username, role=payload.get("role"))
    result = await db.execute(select(User).where(User.username == token_data.username))
    return result.scalar_one_or_none()


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Browsers use the HttpOnly cookie; API clients and devices keep using
    # the Authorization header.
    token = credentials.credentials if credentials is not None else None
    if not token:
        token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not token:
        raise credentials_exception
    user = await _resolve_user(token, db)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


def require_role(role: str):
    """FastAPI dependency factory: require_role("admin").

    Kept generic for future roles; the existing get_admin_user is an alias.
    """
    required = role.strip().lower()

    async def dependency(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if (current_user.role or "").lower() != required:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{required}' required",
            )
        return current_user

    return dependency


def _device_token_matches(token: Optional[str]) -> bool:
    configured = (settings.DEVICE_API_TOKEN or "").strip()
    if not configured or not token:
        return False
    return secrets.compare_digest(token.strip(), configured)


async def require_device_token(
    x_device_token: Optional[str] = Header(default=None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
) -> str:
    """Authenticate a field/gateway device.

    Devices present a shared token either as ``X-Device-Token`` or as a Bearer
    token. When the server has no DEVICE_API_TOKEN configured the route fails
    closed with 503 instead of accepting anonymous writes.
    """
    if not (settings.DEVICE_API_TOKEN or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Device ingestion is disabled: DEVICE_API_TOKEN is not configured",
        )
    bearer = credentials.credentials if credentials is not None else None
    if _device_token_matches(x_device_token) or _device_token_matches(bearer):
        return "device"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid device token",
        headers={"WWW-Authenticate": "Bearer"},
    )