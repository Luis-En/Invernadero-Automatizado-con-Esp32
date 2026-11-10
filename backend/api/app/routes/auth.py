from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    get_password_hash,
    verify_password,
    verify_password_and_update,
)
from app.audit import log_action
from app.config import settings
from app.database import get_db
from app.dependencies import get_admin_user, get_current_active_user
from app.models import Event, User
from app.rate_limit import limiter
from app.schemas import LoginRequest, Token, UserCreate, UserResponse
from app.security import (
    clear_failures,
    client_ip,
    get_active_lock,
    hash_ip,
    prune_old_attempts,
    register_failure,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "Usuario o contraseña incorrectos"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path="/",
    )


def _lockout_response(locked_until: datetime, now: datetime) -> HTTPException:
    retry_after = max(1, int((locked_until - now).total_seconds()))
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            "Demasiados intentos de inicio de sesión. "
            f"Inténtalo de nuevo en {max(1, retry_after // 60)} minuto(s)."
        ),
        headers={
            "Retry-After": str(retry_after),
            "WWW-Authenticate": "Bearer",
        },
    )


async def _record_lockout(
    db: AsyncSession,
    username: str,
    ip: str,
    scopes: List[str],
    locked_until: datetime,
) -> None:
    event = Event(
        timestamp=datetime.utcnow(),
        severity="warning",
        code="AUTH_LOCKOUT",
        message=(
            "Bloqueo temporal de inicio de sesión por intentos fallidos "
            f"({', '.join(scopes)})."
        ),
        details={
            "username": username[:50],
            "ip_hash": hash_ip(ip),
            "scopes": scopes,
            "locked_until": locked_until.isoformat(),
        },
    )
    db.add(event)
    await db.commit()
    try:
        from app.routes.config import manager

        await manager.broadcast(
            {
                "type": "event",
                "data": {
                    "id": event.id,
                    "severity": event.severity,
                    "code": event.code,
                    "message": event.message,
                    "timestamp": event.timestamp.isoformat(),
                },
            }
        )
    except Exception:
        pass


@router.post("/login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    form_data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    ip = client_ip(request)
    username = form_data.username.strip()
    user_key = username.lower() or "-"

    ip_locked_until = await get_active_lock(db, "ip", ip, now)
    user_locked_until = await get_active_lock(db, "user", user_key, now)
    active_locks = [value for value in (ip_locked_until, user_locked_until) if value]
    if active_locks:
        await log_action(
            db,
            "auth.login_blocked",
            "auth",
            username=username,
            request=request,
            details={"locked_until": max(active_locks).isoformat()},
        )
        raise _lockout_response(max(active_locks), now)

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    valid_password = False
    if user is None:
        # Equalise timing with a real bcrypt verification; never reveal that
        # the username does not exist.
        verify_password(form_data.password, DUMMY_PASSWORD_HASH)
    else:
        legacy_hash = not user.hashed_password.startswith("$2")
        valid_password, upgraded_hash = verify_password_and_update(
            form_data.password, user.hashed_password
        )
        if valid_password and upgraded_hash:
            user.hashed_password = upgraded_hash
            db.add(user)
            await db.commit()
        if legacy_hash:
            # Legacy sha256 hashes are much faster than bcrypt; pay the bcrypt
            # cost once more so response timing does not identify them.
            verify_password(form_data.password, DUMMY_PASSWORD_HASH)

    if user is None or not valid_password or not user.is_active:
        newly_locked = []
        locked_until = None
        for scope, key, max_failures, window_seconds, lockout_seconds in (
            (
                "ip",
                ip,
                settings.LOGIN_IP_MAX_FAILURES,
                settings.LOGIN_IP_WINDOW_SEC,
                settings.LOGIN_IP_LOCKOUT_SEC,
            ),
            (
                "user",
                user_key,
                settings.LOGIN_MAX_FAILURES,
                settings.LOGIN_WINDOW_SEC,
                settings.LOGIN_LOCKOUT_SEC,
            ),
        ):
            locked, until = await register_failure(
                db,
                scope,
                key,
                now,
                max_failures,
                window_seconds,
                lockout_seconds,
            )
            if locked:
                newly_locked.append(scope)
                locked_until = until if locked_until is None else max(locked_until, until)

        if newly_locked and locked_until is not None:
            await _record_lockout(db, username, ip, newly_locked, locked_until)

        await log_action(
            db,
            "auth.login_failed",
            "auth",
            username=username,
            request=request,
            details={"reason": "invalid_credentials"},
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_LOGIN_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        )

    await clear_failures(db, "ip", ip)
    await clear_failures(db, "user", user_key)
    await prune_old_attempts(db, now)

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    _set_session_cookie(response, access_token)
    await log_action(
        db,
        "auth.login_success",
        "auth",
        user=user,
        request=request,
    )
    return Token(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already registered")

    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await log_action(
        db,
        "user.create",
        f"user:{user.id}",
        user=admin,
        request=request,
        details={"username": user.username, "role": user.role},
    )
    return user


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db), admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()
