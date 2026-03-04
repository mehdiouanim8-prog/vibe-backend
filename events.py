from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Event, EventRSVP
from schemas import EventCreate, EventOut
from security import get_current_user
from typing import List

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("/", response_model=EventOut, status_code=201)
def create_event(data: EventCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    event = Event(**data.dict(), created_by=current_user.id)
    db.add(event)
    db.commit()
    db.refresh(event)
    event.attendees_count = len(event.rsvps)
    return event


@router.get("/", response_model=List[EventOut])
def list_events(db: Session = Depends(get_db)):
    events = db.query(Event).order_by(Event.start_date).all()
    for e in events:
        e.attendees_count = len(e.rsvps)
    return events


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.attendees_count = len(event.rsvps)
    return event


@router.post("/{event_id}/rsvp")
def rsvp_event(event_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.max_attendees and len(event.rsvps) >= event.max_attendees:
        raise HTTPException(status_code=400, detail="Event is full")
    existing = db.query(EventRSVP).filter(EventRSVP.event_id == event_id, EventRSVP.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already RSVPed")
    rsvp = EventRSVP(event_id=event_id, user_id=current_user.id)
    db.add(rsvp)
    db.commit()
    return {"message": "RSVP confirmed"}


@router.delete("/{event_id}/rsvp")
def cancel_rsvp(event_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rsvp = db.query(EventRSVP).filter(EventRSVP.event_id == event_id, EventRSVP.user_id == current_user.id).first()
    if not rsvp:
        raise HTTPException(status_code=404, detail="RSVP not found")
    db.delete(rsvp)
    db.commit()
    return {"message": "RSVP cancelled"}


@router.delete("/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(event)
    db.commit()
    return {"message": "Event deleted"}
