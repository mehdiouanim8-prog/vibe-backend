from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models import Community, CommunityMember, User
from security import get_current_user

router = APIRouter(prefix="/communities", tags=["Communities"])


# ─── Schemas ──────────────────────────────────────────────────

class CommunityCreate(BaseModel):
    name:        str
    description: Optional[str] = None
    image_url:   Optional[str] = None

class CommunityOut(BaseModel):
    id:          int
    name:        str
    description: Optional[str] = None
    image_url:   Optional[str] = None
    owner_id:    Optional[int] = None
    member_count: Optional[int] = 0
    is_member:   Optional[bool] = False
    class Config: orm_mode = True


# ─── Routes ───────────────────────────────────────────────────

@router.get("/", response_model=List[CommunityOut])
def list_communities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    communities = db.query(Community).all()
    result = []
    for c in communities:
        member_count = db.query(CommunityMember).filter(CommunityMember.community_id == c.id).count()
        is_member = db.query(CommunityMember).filter(
            CommunityMember.community_id == c.id,
            CommunityMember.user_id == current_user.id
        ).first() is not None
        result.append({
            **c.__dict__,
            "member_count": member_count,
            "is_member": is_member,
        })
    return result


@router.post("/", response_model=CommunityOut, status_code=201)
def create_community(
    data: CommunityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    community = Community(**data.dict(), owner_id=current_user.id)
    db.add(community)
    db.commit()
    db.refresh(community)
    # Auto-join as member
    member = CommunityMember(community_id=community.id, user_id=current_user.id, role="admin")
    db.add(member)
    db.commit()
    return {**community.__dict__, "member_count": 1, "is_member": True}


@router.get("/{community_id}", response_model=CommunityOut)
def get_community(
    community_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    c = db.query(Community).filter(Community.id == community_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Community not found")
    member_count = db.query(CommunityMember).filter(CommunityMember.community_id == c.id).count()
    is_member = db.query(CommunityMember).filter(
        CommunityMember.community_id == c.id,
        CommunityMember.user_id == current_user.id
    ).first() is not None
    return {**c.__dict__, "member_count": member_count, "is_member": is_member}


@router.post("/{community_id}/join")
def join_community(
    community_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    c = db.query(Community).filter(Community.id == community_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Community not found")
    existing = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already a member")
    member = CommunityMember(community_id=community_id, user_id=current_user.id, role="member")
    db.add(member)
    db.commit()
    return {"message": "joined"}


@router.delete("/{community_id}/leave")
def leave_community(
    community_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    member = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == current_user.id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Not a member")
    db.delete(member)
    db.commit()
    return {"message": "left"}
