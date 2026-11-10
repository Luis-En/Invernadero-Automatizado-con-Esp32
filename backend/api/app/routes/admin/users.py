from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user
from app.routes.auth import list_users, register
from app.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["admin-users"])


@router.get("", response_model=list[UserResponse])
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    return await list_users(db, admin)


@router.post("", response_model=UserResponse, status_code=201)
async def admin_create_user(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    return await register(payload, request, db, admin)
