from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import get_db
from models import Message, User
from security import get_current_user

router = APIRouter(prefix="/messages", tags=["Messages"])


# ─── Schemas ──────────────────────────────────────────────────

class MessageCreate(BaseModel):
    receiver_id: int
    content:     str

class MessageOut(BaseModel):
    id:          int
    sender_id:   int
    receiver_id: int
    content:     str
    is_read:     bool
    created_at:  datetime
    class Config: orm_mode = True

class ConversationOut(BaseModel):
    user_id:     int
    username:    Optional[str] = None
    full_name:   Optional[str] = None
    avatar_url:  Optional[str] = None
    last_message: Optional[str] = None
    unread_count: int = 0


# ─── Routes ───────────────────────────────────────────────────

@router.get("/conversations", response_model=List[ConversationOut])
def get_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all users current_user has talked to."""
    messages = db.query(Message).filter(
        or_(
            Message.sender_id == current_user.id,
            Message.receiver_id == current_user.id
        )
    ).order_by(Message.created_at.desc()).all()

    seen_users = {}
    for m in messages:
        other_id = m.receiver_id if m.sender_id == current_user.id else m.sender_id
        if other_id not in seen_users:
            other = db.query(User).filter(User.id == other_id).first()
            if other:
                unread = db.query(Message).filter(
                    Message.sender_id == other_id,
                    Message.receiver_id == current_user.id,
                    Message.is_read == False
                ).count()
                seen_users[other_id] = {
                    "user_id":     other.id,
                    "username":    other.username,
                    "full_name":   other.full_name,
                    "avatar_url":  other.avatar_url,
                    "last_message": m.content,
                    "unread_count": unread,
                }
    return list(seen_users.values())


@router.get("/{user_id}", response_model=List[MessageOut])
def get_conversation(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all messages between current_user and user_id."""
    messages = db.query(Message).filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == user_id),
            and_(Message.sender_id == user_id, Message.receiver_id == current_user.id)
        )
    ).order_by(Message.created_at.asc()).all()

    # Mark all received messages as read
    for m in messages:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    db.commit()

    return messages


@router.post("/", response_model=MessageOut, status_code=201)
def send_message(
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if data.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")
    receiver = db.query(User).filter(User.id == data.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")
    message = Message(
        sender_id=current_user.id,
        receiver_id=data.receiver_id,
        content=data.content
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.delete("/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(message)
    db.commit()
    return {"message": "deleted"}
