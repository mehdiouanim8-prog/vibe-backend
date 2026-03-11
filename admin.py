from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models import User, Post, Notification
from security import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])


# ─── Admin guard ──────────────────────────────────────────────

def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ─── Users ────────────────────────────────────────────────────

@router.get("/users")
def admin_list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id":         u.id,
            "username":   u.username,
            "email":      u.email,
            "full_name":  u.full_name,
            "is_admin":   u.is_admin,
            "is_active":  u.is_active,
            "is_on_hold": u.is_on_hold,
            "is_premium": u.is_premium,
            "is_verified":u.is_verified,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.patch("/users/{user_id}/hold")
def hold_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_on_hold = True
    user.is_active = False
    db.commit()
    return {"message": f"User {user.username} is now on hold"}


@router.patch("/users/{user_id}/restore")
def restore_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_on_hold = False
    user.is_active = True
    db.commit()
    return {"message": f"User {user.username} restored"}


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete admin users")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@router.patch("/users/{user_id}/verify")
def verify_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_verified = True
    db.commit()
    return {"message": f"User {user.username} verified"}


@router.patch("/users/{user_id}/premium")
def grant_premium(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_premium = not user.is_premium
    db.commit()
    return {"message": f"Premium toggled for {user.username}"}


# ─── Posts ────────────────────────────────────────────────────

@router.get("/posts")
def admin_list_posts(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    posts = db.query(Post).order_by(Post.created_at.desc()).limit(200).all()
    return posts


@router.delete("/posts/{post_id}")
def admin_delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    return {"message": "Post deleted"}


# ─── Push Notifications (broadcast) ──────────────────────────

class PushMessage(BaseModel):
    message: str
    type:    Optional[str] = "system"

@router.post("/push")
def broadcast_push(
    data: PushMessage,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Send a push notification to ALL users."""
    users = db.query(User).filter(User.is_active == True).all()
    notifs = [
        Notification(
            user_id=u.id,
            type=data.type,
            message=data.message,
        )
        for u in users
    ]
    db.bulk_save_objects(notifs)
    db.commit()
    return {"message": f"Broadcast sent to {len(notifs)} users"}


# ─── Stats ────────────────────────────────────────────────────

@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    total_users  = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_posts  = db.query(Post).count()
    premium_users= db.query(User).filter(User.is_premium == True).count()
    verified_users = db.query(User).filter(User.is_verified == True).count()
    return {
        "total_users":    total_users,
        "active_users":   active_users,
        "total_posts":    total_posts,
        "premium_users":  premium_users,
        "verified_users": verified_users,
    }
