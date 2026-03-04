from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Message, Group, GroupMember, User
from schemas import MessageCreate, MessageOut, GroupCreate, GroupOut
from security import get_current_user
from typing import List

router = APIRouter(prefix="/messages", tags=["Messages"])


# ─── Direct Messages ─────────────────────────────────────────

@router.post("/", response_model=MessageOut, status_code=201)
def send_message(data: MessageCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not data.receiver_id and not data.group_id:
        raise HTTPException(status_code=400, detail="Must provide receiver_id or group_id")
    if data.receiver_id:
        receiver = db.query(User).filter(User.id == data.receiver_id).first()
        if not receiver:
            raise HTTPException(status_code=404, detail="Receiver not found")
    if data.group_id:
        membership = db.query(GroupMember).filter(
            GroupMember.group_id == data.group_id,
            GroupMember.user_id == current_user.id
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="You are not a member of this group")
    message = Message(
        sender_id=current_user.id,
        receiver_id=data.receiver_id,
        group_id=data.group_id,
        content=data.content
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/dm/{user_id}", response_model=List[MessageOut])
def get_dm_conversation(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    messages = db.query(Message).filter(
        Message.group_id == None,
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at).all()
    return messages


@router.get("/inbox", response_model=List[MessageOut])
def get_inbox(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    messages = db.query(Message).filter(
        Message.receiver_id == current_user.id,
        Message.group_id == None
    ).order_by(Message.created_at.desc()).all()
    return messages


# ─── Group Messages ───────────────────────────────────────────

@router.post("/groups", response_model=GroupOut, status_code=201)
def create_group(data: GroupCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    group = Group(name=data.name, avatar_url=data.avatar_url, created_by=current_user.id)
    db.add(group)
    db.flush()
    db.add(GroupMember(group_id=group.id, user_id=current_user.id))
    for uid in data.member_ids:
        if uid != current_user.id:
            user = db.query(User).filter(User.id == uid).first()
            if user:
                db.add(GroupMember(group_id=group.id, user_id=uid))
    db.commit()
    db.refresh(group)
    group.members_count = len(group.members)
    return group


@router.get("/groups", response_model=List[GroupOut])
def get_my_groups(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    memberships = db.query(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    groups = [m.group for m in memberships]
    for g in groups:
        g.members_count = len(g.members)
    return groups


@router.get("/groups/{group_id}", response_model=List[MessageOut])
def get_group_messages(group_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    messages = db.query(Message).filter(Message.group_id == group_id).order_by(Message.created_at).all()
    return messages
