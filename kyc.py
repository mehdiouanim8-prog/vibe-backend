import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models import KYCVerification, User
from security import get_current_onboarding_user
from storage import (
    MAX_DOCUMENT_BYTES,
    MAX_LIVENESS_BYTES,
    save_upload,
)


router = APIRouter(
    prefix="/kyc",
    tags=["KYC"],
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_verification(
    db: Session,
    user_id: int,
) -> Optional[KYCVerification]:
    return (
        db.query(KYCVerification)
        .filter(KYCVerification.user_id == user_id)
        .order_by(
            KYCVerification.attempt_number.desc(),
            KYCVerification.id.desc(),
        )
        .first()
    )


def _next_attempt_number(
    db: Session,
    user_id: int,
) -> int:
    latest = _latest_verification(db, user_id)

    if latest is None:
        return 1

    return latest.attempt_number + 1


def _require_identifiers_verified(user: User) -> None:
    if not user.email_verified or not user.phone_verified:
        raise HTTPException(
            status_code=409,
            detail="Email and phone verification must be completed first.",
        )


def _require_identity_step(
    db: Session,
    user: User,
) -> None:
    _require_identifiers_verified(user)

    verification = _latest_verification(
        db,
        user.id,
    )

    if verification is not None:
        if verification.review_status == "pending":
            raise HTTPException(
                status_code=409,
                detail="Your KYC application is already under review.",
            )

        if verification.review_status == "approved":
            raise HTTPException(
                status_code=409,
                detail="Identity verification has already been approved.",
            )

        if (
            verification.identity_status
            in {"submitted", "approved"}
            and verification.review_status
            not in {"rejected", "needs_resubmission"}
        ):
            raise HTTPException(
                status_code=409,
                detail="Identity documents have already been submitted.",
            )


def _require_liveness_step(
    db: Session,
    user: User,
) -> KYCVerification:
    _require_identifiers_verified(user)

    verification = _latest_verification(
        db,
        user.id,
    )

    if verification is None:
        raise HTTPException(
            status_code=409,
            detail="Identity verification must be submitted first.",
        )

    if verification.identity_status not in {
        "submitted",
        "approved",
    }:
        raise HTTPException(
            status_code=409,
            detail="Identity documents must be submitted before liveness.",
        )

    if verification.liveness_status in {
        "submitted",
        "passed",
    }:
        raise HTTPException(
            status_code=409,
            detail="Liveness has already been submitted.",
        )

    if verification.review_status == "pending":
        raise HTTPException(
            status_code=409,
            detail="Your KYC application is already under review.",
        )

    return verification


@router.post("/identity/upload")
async def upload_identity_documents(
    front: UploadFile = File(...),
    back: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_onboarding_user
    ),
):
    """
    Submit identity documents.

    This endpoint is only available after both
    email and phone verification.
    """

    _require_identity_step(
        db,
        current_user,
    )

    attempt_number = _next_attempt_number(
        db,
        current_user.id,
    )

    # Create the KYC attempt first so the
    # storage paths are tied to this attempt.
    verification = KYCVerification(
        user_id=current_user.id,
        attempt_number=attempt_number,
        review_status="not_started",
        identity_status="not_started",
        liveness_status="not_started",
        document_quality_status="not_started",
        ocr_status="not_started",
        face_match_status="not_started",
        liveness_check_status="not_started",
    )

    db.add(verification)
    db.flush()

    try:
        front_key, front_size = await save_upload(
            front,
            user_id=current_user.id,
            attempt_number=attempt_number,
            kind="document-front",
            max_bytes=MAX_DOCUMENT_BYTES,
            allowed_types={
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
            },
        )

        back_key, back_size = await save_upload(
            back,
            user_id=current_user.id,
            attempt_number=attempt_number,
            kind="document-back",
            max_bytes=MAX_DOCUMENT_BYTES,
            allowed_types={
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
            },
        )

    except Exception:
        db.rollback()
        raise

    verification.document_front_storage_key = front_key
    verification.document_back_storage_key = back_key

    verification.identity_status = "submitted"
    verification.document_quality_status = "not_started"
    verification.ocr_status = "not_started"
    verification.face_match_status = "not_started"

    current_user.identity_status = "submitted"
    current_user.identity_submitted_at = _utc_now()

    db.commit()

    return {
        "success": True,
        "identity_status": "submitted",
        "next_step": "liveness",
        "front_size": front_size,
        "back_size": back_size,
    }


@router.post("/liveness/upload")
async def upload_liveness_video(
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_onboarding_user
    ),
):
    """
    Submit the liveness recording.

    IMPORTANT:
    Uploading the video does NOT itself mean that
    liveness has passed. It is submitted for the
    verification/review process.
    """

    verification = _require_liveness_step(
        db,
        current_user,
    )

    try:
        video_key, video_size = await save_upload(
            video,
            user_id=current_user.id,
            attempt_number=verification.attempt_number,
            kind="liveness",
            max_bytes=MAX_LIVENESS_BYTES,
            allowed_types={
                "video/mp4": ".mp4",
                "video/quicktime": ".mov",
                "video/webm": ".webm",
            },
        )
    except Exception:
        db.rollback()
        raise

    verification.liveness_storage_key = video_key
    verification.liveness_status = "submitted"
    verification.liveness_check_status = "not_started"

    # Once both parts are submitted, the account
    # enters manual/verification review.
    verification.review_status = "pending"
    verification.submitted_at = _utc_now()

    current_user.liveness_status = "submitted"
    current_user.liveness_submitted_at = _utc_now()
    current_user.account_status = "pending"

    db.commit()

    return {
        "success": True,
        "liveness_status": "submitted",
        "review_status": "pending",
        "next_step": "under_review",
        "video_size": video_size,
    }


@router.get("/status")
def kyc_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_onboarding_user
    ),
):
    verification = _latest_verification(
        db,
        current_user.id,
    )

    if verification is None:
        return {
            "exists": False,
            "identity_status": "not_started",
            "liveness_status": "not_started",
            "review_status": "not_started",
        }

    return {
        "exists": True,
        "attempt_number": verification.attempt_number,
        "identity_status": verification.identity_status,
        "liveness_status": verification.liveness_status,
        "review_status": verification.review_status,
        "submitted_at": verification.submitted_at,
    }
