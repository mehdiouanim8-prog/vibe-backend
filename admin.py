from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models import User, Post, Notification, KYCVerification
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
# ─── KYC Review ──────────────────────────────────────────────

@router.get("/kyc/pending")
def admin_list_pending_kyc(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    applications = (
        db.query(KYCVerification)
        .filter(KYCVerification.review_status == "pending")
        .order_by(KYCVerification.submitted_at.asc())
        .all()
    )

    results = []

    for kyc in applications:
        user = db.query(User).filter(User.id == kyc.user_id).first()

        results.append({
            "kyc_id": kyc.id,
            "user_id": kyc.user_id,
            "email": user.email if user else None,
            "phone": user.phone if user else None,
            "attempt_number": kyc.attempt_number,
            "identity_status": kyc.identity_status,
            "liveness_status": kyc.liveness_status,
            "review_status": kyc.review_status,
            "submitted_at": kyc.submitted_at,
        })

    return results


@router.get("/kyc/{kyc_id}")
def admin_get_kyc(
    kyc_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    kyc = (
        db.query(KYCVerification)
        .filter(KYCVerification.id == kyc_id)
        .first()
    )

    if not kyc:
        raise HTTPException(
            status_code=404,
            detail="KYC application not found"
        )

    user = db.query(User).filter(User.id == kyc.user_id).first()

    return {
        "kyc_id": kyc.id,
        "user_id": kyc.user_id,
        "email": user.email if user else None,
        "phone": user.phone if user else None,
        "attempt_number": kyc.attempt_number,

        "identity_status": kyc.identity_status,
        "liveness_status": kyc.liveness_status,
        "document_quality_status": kyc.document_quality_status,
        "ocr_status": kyc.ocr_status,
        "face_match_status": kyc.face_match_status,
        "liveness_check_status": kyc.liveness_check_status,

        "review_status": kyc.review_status,
        "rejection_code": kyc.rejection_code,
        "reviewer_id": kyc.reviewer_id,
        "reviewer_note": kyc.reviewer_note,

        "submitted_at": kyc.submitted_at,
        "reviewed_at": kyc.reviewed_at,
        "created_at": kyc.created_at,
        "updated_at": kyc.updated_at,
    }


class KYCReviewDecision(BaseModel):
    note: Optional[str] = None
    rejection_code: Optional[str] = None


@router.patch("/kyc/{kyc_id}/approve")
def admin_approve_kyc(
    kyc_id: int,
    data: KYCReviewDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    kyc = (
        db.query(KYCVerification)
        .filter(KYCVerification.id == kyc_id)
        .first()
    )

    if not kyc:
        raise HTTPException(
            status_code=404,
            detail="KYC application not found"
        )

    if kyc.review_status != "pending":
        raise HTTPException(
            status_code=400,
            detail="KYC application is not pending review"
        )

    kyc.review_status = "approved"
    kyc.reviewer_id = admin.id
    kyc.reviewer_note = data.note
    kyc.reviewed_at = datetime.utcnow()

    # KYC approval does NOT activate the account.
    # The user must still complete 2FA, profile/password,
    # and payment before activation.

    db.commit()
    db.refresh(kyc)

    return {
        "message": "KYC approved",
        "kyc_id": kyc.id,
        "review_status": kyc.review_status,
        "next_step": "two_factor",
    }


@router.patch("/kyc/{kyc_id}/reject")
def admin_reject_kyc(
    kyc_id: int,
    data: KYCReviewDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    kyc = (
        db.query(KYCVerification)
        .filter(KYCVerification.id == kyc_id)
        .first()
    )

    if not kyc:
        raise HTTPException(
            status_code=404,
            detail="KYC application not found"
        )

    if kyc.review_status != "pending":
        raise HTTPException(
            status_code=400,
            detail="KYC application is not pending review"
        )

    kyc.review_status = "rejected"
    kyc.reviewer_id = admin.id
    kyc.reviewer_note = data.note
    kyc.rejection_code = data.rejection_code
    kyc.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(kyc)

    return {
        "message": "KYC rejected",
        "kyc_id": kyc.id,
        "review_status": kyc.review_status,
        "next_step": "identity",
    }
