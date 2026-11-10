from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditLog
from app.rate_limit import limiter
from app.schemas import AuditLogResponse

router = APIRouter(prefix="/logs", tags=["admin-logs"])


@router.get("", response_model=List[AuditLogResponse])
@limiter.limit("60/minute")
async def list_audit_logs(
    request: Request,
    action: Optional[str] = Query(None, max_length=64),
    username: Optional[str] = Query(None, max_length=50),
    user_id: Optional[int] = Query(None, ge=1),
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit).offset(offset)
    if action:
        query = query.where(AuditLog.action == action)
    if username:
        query = query.where(AuditLog.username == username)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if since:
        query = query.where(AuditLog.timestamp >= since)
    if until:
        query = query.where(AuditLog.timestamp <= until)

    result = await db.execute(query)
    return result.scalars().all()
