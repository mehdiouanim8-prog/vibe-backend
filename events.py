from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import get_db
from models import Event, User
from security import get_current_user

router = APIRouter(prefix="/events", tags=["Events"])


# ─── Schemas ──────────────────────────────────────────────────

class EventCreate(BaseModel):
    title:       str
    description: Optional[str] = None
    location:    Optional[str] = None
    start_date:  Optional[datetime] = None
    end_date:    Optional[datetime] = None
    image_url:   Optional[str] = None

class EventOut(BaseModel):
    id:           int
    title:        str
    description:  Optional[str]      = None
    location:     Optional[str]      = None
    start_date:   Optional[datetime] = None
    end_date:     Optional[datetime] = None
    image_url:    Optional[str]      = None
    organizer_id: Optional[int]      = None
    created_at:   datetime
    class Config: orm_mode = True


# ─── Routes ───────────────────────────────────────────────────

@router.get("/", response_model=List[EventOut])
def list_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Event).order_by(Event.start_date).all()


@router.post("/", response_model=EventOut, status_code=201)
def create_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = Event(**data.dict(), organizer_id=current_user.id)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.organizer_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(event)
    db.commit()
    return {"message": "deleted"}
