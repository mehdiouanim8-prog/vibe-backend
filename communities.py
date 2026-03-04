from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Community, CommunityMember, MemberRoleEnum
from schemas import CommunityCreate, CommunityOut
from security import get_current_user
from typing import List

router = APIRouter(prefix="/communities", tags=["Communities"])


@router.post("/", response_model=CommunityOut, status_code=201)
def create_community(data: CommunityCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    existing = db.query(Community).filter(Community.slug == data.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug already taken")
    community = Community(**data.dict(), created_by=current_user.id)
    db.add(community)
    db.flush()
    member = CommunityMember(community_id=community.id, user_id=current_user.id, role=MemberRoleEnum.admin)
    db.add(member)
    db.commit()
    db.refresh(community)
    community.members_count = len(community.members)
    return community


@router.get("/", response_model=List[CommunityOut])
def list_communities(db: Session = Depends(get_db)):
    communities = db.query(Community).filter(Community.is_private == False).all()
    for c in communities:
        c.members_count = len(c.members)
    return communities


@router.get("/{slug}", response_model=CommunityOut)
def get_community(slug: str, db: Session = Depends(get_db)):
    community = db.query(Community).filter(Community.slug == slug).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    community.members_count = len(community.members)
    return community


@router.post("/{slug}/join")
def join_community(slug: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    community = db.query(Community).filter(Community.slug == slug).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    existing = db.query(CommunityMember).filter(
        CommunityMember.community_id == community.id,
        CommunityMember.user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already a member")
    member = CommunityMember(community_id=community.id, user_id=current_user.id)
    db.add(member)
    db.commit()
    return {"message": f"Joined {community.name}"}


@router.delete("/{slug}/leave")
def leave_community(slug: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    community = db.query(Community).filter(Community.slug == slug).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    member = db.query(CommunityMember).filter(
        CommunityMember.community_id == community.id,
        CommunityMember.user_id == current_user.id
    ).first()
    if not member:
        raise HTTPException(status_code=400, detail="Not a member")
    db.delete(member)
    db.commit()
    return {"message": f"Left {community.name}"}
