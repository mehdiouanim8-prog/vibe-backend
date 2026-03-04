from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, Post, Community, Job, Event
from schemas import UserOut, AdminUserUpdate
from security import get_current_user
from typing import List

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(current_user=Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ─── Users ───────────────────────────────────────────────────

@router.get("/users", response_model=List[UserOut])
def list_all_users(db: Session = Depends(get_db), admin=Depends(require_admin)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    for u in users:
        u.followers_count = len(u.followers)
        u.following_count = len(u.following)
    return users


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: AdminUserUpdate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    user.followers_count = len(user.followers)
    user.following_count = len(user.following)
    return user


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


# ─── Stats ───────────────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return {
        "total_users": db.query(User).count(),
        "total_posts": db.query(Post).count(),
        "total_communities": db.query(Community).count(),
        "total_jobs": db.query(Job).count(),
        "total_events": db.query(Event).count(),
        "pro_users": db.query(User).filter(User.plan == "pro").count(),
        "enterprise_users": db.query(User).filter(User.plan == "enterprise").count(),
        "verified_companies": db.query(User).filter(User.is_verified_company == True).count(),
    }


# ─── Content Moderation ──────────────────────────────────────

@router.delete("/posts/{post_id}")
def admin_delete_post(post_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    return {"message": "Post deleted"}


@router.delete("/communities/{community_id}")
def admin_delete_community(community_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    db.delete(community)
    db.commit()
    return {"message": "Community deleted"}
