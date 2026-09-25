from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from app.database import get_db
from app.models import Event, User
from app.schemas import EventCreate, EventResponse, EventSeverity
from app.dependencies import get_current_active_user, get_admin_user

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=List[EventResponse])
async def list_events(
    severity: Optional[EventSeverity] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_active_user)
):
    query = select(Event).order_by(desc(Event.timestamp)).limit(limit)
    if severity:
        query = query.where(Event.severity == severity.value)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/unacknowledged", response_model=List[EventResponse])
async def list_unacknowledged_events(db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(
        select(Event).where(Event.acknowledged == False).order_by(desc(Event.timestamp))
    )
    return result.scalars().all()


@router.post("/{event_id}/acknowledge", response_model=EventResponse)
async def acknowledge_event(event_id: int, db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.acknowledged = True
    event.acknowledged_by = admin.id
    from datetime import datetime
    event.acknowledged_at = datetime.utcnow()
    await db.commit()
    await db.refresh(event)
    return event


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(event_data: EventCreate, db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    event = Event(**event_data.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event