from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import get_db
from models import User, Follow, Notification, SavedPost, Post
from schemas import UserOut, UserUpdate
from security import get_current_user
from typing import List, Optional

router = APIRouter(prefix="/users", tags=["Users"])


def enrich_user(user: User, current_user: User, db: Session) -> dict:
    """Add computed fields to user object."""
    data = {
        "id":                  user.id,
        "username":            user.username,
        "email":               user.email,
        "full_name":           user.full_name,
        "headline":            user.headline,
        "bio":                 user.bio,
        "location":            user.location,
        "website":             user.website,
        "avatar_url":          user.avatar_url,
        "cover_url":           user.cover_url,
        "is_admin":            user.is_admin,
        "is_premium":          user.is_premium,
        "is_verified":         user.is_verified,
        "is_verified_company": user.is_verified_company,
        "is_active":           user.is_active,
        "language":            user.language,
        "created_at":          user.created_at,
        "followers_count":     len(user.followers),
        "following_count":     len(user.following),
        "is_followed":         any(f.follower_id == current_user.id for f in user.followers),
    }
    return data


# ─── Get current user ─────────────────────────────────────────

@router.get("/me", response_model=UserOut)
def get_me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return enrich_user(current_user, current_user, db)


# ─── Update current user ──────────────────────────────────────

@router.patch("/me", response_model=UserOut)
def update_me(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    for field, value in data.dict(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return enrich_user(current_user, current_user, db)


# ─── Search users ─────────────────────────────────────────────

@router.get("/", response_model=List[UserOut])
def search_users(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(User).filter(User.is_active == True)
    if search:
        q = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(q),
                User.full_name.ilike(q),
                User.headline.ilike(q),
            )
        )
    users = query.offset((page - 1) * per_page).limit(per_page).all()
    return [enrich_user(u, current_user, db) for u in users]


# ─── Get user by ID ───────────────────────────────────────────

@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return enrich_user(user, current_user, db)


# ─── Follow ───────────────────────────────────────────────────

@router.post("/{user_id}/follow")
def follow_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already following")
    follow = Follow(follower_id=current_user.id, following_id=user_id)
    db.add(follow)
    # Create notification for target
    notif = Notification(
        user_id=user_id,
        type="follow",
        message=f"{current_user.full_name or current_user.username} started following you",
        from_user_id=current_user.id,
    )
    db.add(notif)
    db.commit()
    return {"message": "following"}


@router.delete("/{user_id}/follow")
def unfollow_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    follow = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()
    if not follow:
        raise HTTPException(status_code=404, detail="Not following")
    db.delete(follow)
    db.commit()
    return {"message": "unfollowed"}


# ─── Saved posts ──────────────────────────────────────────────

@router.get("/me/saved")
def get_saved_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    saved = db.query(SavedPost).filter(SavedPost.user_id == current_user.id).all()
    post_ids = [s.post_id for s in saved]
    posts = db.query(Post).filter(Post.id.in_(post_ids)).all()
    return posts


# ─── Notifications ────────────────────────────────────────────

@router.get("/me/notifications")
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notifs = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    return notifs


@router.patch("/me/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"message": "all read"}
