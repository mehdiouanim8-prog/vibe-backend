import hashlib
import hmac
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone

from email.mime.text import MIMEText
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from models import KYCVerification, User
from security import create_onboarding_token, get_current_onboarding_user
from phone import (
    normalize_phone_number,
    send_twilio_code,
    verify_twilio_code,
)


router = APIRouter(prefix="/verification", tags=["Verification"])

OTP_TTL_MINUTES = 10
MAX_VERIFY_ATTEMPTS = 5
MAX_RESENDS = 3
RESEND_WINDOW_MINUTES = 30
RESEND_COOLDOWN_SECONDS = 60


class RegistrationStart(BaseModel):
    identifier: str


class OTPCheck(BaseModel):
    code: str


class IdentifierStart(BaseModel):
    identifier: str


class EmailResend(BaseModel):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def detect_identifier(value: str) -> tuple[str, str]:
    value = str(value or "").strip()

    if not value:
        raise HTTPException(
            status_code=400,
            detail="Enter an email address or phone number.",
        )

    if "@" in value:
        normalized = value.lower()

        try:
            EmailStr(normalized)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="Enter a valid email address.",
            ) from exc

        return "email", normalized

    try:
        return "phone", normalize_phone_number(value)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Enter a valid phone number.",
        ) from exc


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_email_code(email: str, code: str) -> str:
    secret_key = os.getenv("SECRET_KEY", "").strip()

    if not secret_key:
        raise RuntimeError("SECRET_KEY must be configured.")

    material = (
        f"element-email-verification:{email.lower()}:{code}"
    ).encode("utf-8")

    return hmac.new(
        secret_key.encode("utf-8"),
        material,
        hashlib.sha256,
    ).hexdigest()


def _smtp_send(email: str, code: str) -> None:
    host = os.getenv("SMTP_HOST")
    port_raw = os.getenv("SMTP_PORT", "587")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("EMAIL_FROM") or username

    if not host or not sender:
        raise HTTPException(
            status_code=503,
            detail="Email verification service is not configured.",
        )

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="Email verification service is misconfigured.",
        ) from exc

    msg = MIMEText(
        f"Your Element verification code is: {code}\n\n"
        f"This code expires in {OTP_TTL_MINUTES} minutes.\n",
        "plain",
        "utf-8",
    )

    msg["Subject"] = "Your Element verification code"
    msg["From"] = sender
    msg["To"] = email

    use_ssl = os.getenv(
        "SMTP_USE_SSL",
        "false",
    ).lower() in {"1", "true", "yes", "on"}

    use_tls = os.getenv(
        "SMTP_USE_TLS",
        "true",
    ).lower() in {"1", "true", "yes", "on"}

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(
                host,
                port,
                timeout=20,
            ) as server:
                if username and password:
                    server.login(username, password)

                server.sendmail(
                    sender,
                    [email],
                    msg.as_string(),
                )

        else:
            with smtplib.SMTP(
                host,
                port,
                timeout=20,
            ) as server:
                server.ehlo()

                if use_tls:
                    server.starttls()
                    server.ehlo()

                if username and password:
                    server.login(username, password)

                server.sendmail(
                    sender,
                    [email],
                    msg.as_string(),
                )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not send the verification email.",
        ) from exc


def _check_resend_limit(user: User) -> None:
    now = _utc_now()
    started = user.verification_resend_window_started_at

    if (
        not started
        or now - started > timedelta(
            minutes=RESEND_WINDOW_MINUTES
        )
    ):
        user.verification_resend_window_started_at = now
        user.verification_resend_count = 0
        return

    last_send = user.verification_last_sent_at

    if last_send:
        elapsed = (
            now - last_send
        ).total_seconds()

        if elapsed < RESEND_COOLDOWN_SECONDS:
            wait = max(
                1,
                int(
                    RESEND_COOLDOWN_SECONDS
                    - elapsed
                ),
            )

            raise HTTPException(
                status_code=429,
                detail=(
                    f"Please wait {wait} seconds "
                    "before requesting another code."
                ),
            )

    if (
        user.verification_resend_count or 0
    ) >= MAX_RESENDS:
        raise HTTPException(
            status_code=429,
            detail=(
                "You have reached the maximum number "
                "of resend requests. Please try again later."
            ),
        )


def _record_send(
    user: User,
    *,
    count_as_resend: bool,
) -> None:
    now = _utc_now()

    if (
        not user.verification_resend_window_started_at
        or now
        - user.verification_resend_window_started_at
        > timedelta(minutes=RESEND_WINDOW_MINUTES)
    ):
        user.verification_resend_window_started_at = now
        user.verification_resend_count = 0

    if count_as_resend:
        user.verification_resend_count = (
            user.verification_resend_count or 0
        ) + 1

    user.verification_last_sent_at = now


def _send_for_user(
    user: User,
    identifier_type: str,
    identifier: str,
    db: Session,
    *,
    is_resend: bool,
) -> None:
    if is_resend:
        _check_resend_limit(user)

    if identifier_type == "email":
        code = _generate_code()

        user.email = identifier
        user.email_verification_code_hash = (
            _hash_email_code(identifier, code)
        )
        user.email_verification_expires_at = (
            _utc_now()
            + timedelta(minutes=OTP_TTL_MINUTES)
        )
        user.email_verification_attempts = 0

        _smtp_send(identifier, code)

    else:
        send_twilio_code(identifier)

        user.phone_number = identifier
        user.phone_verified = False

    _record_send(
        user,
        count_as_resend=is_resend,
    )

    db.commit()


def _get_latest_kyc(
    db: Session,
    user: User,
) -> Optional[KYCVerification]:
    return (
        db.query(KYCVerification)
        .filter(
            KYCVerification.user_id == user.id
        )
        .order_by(
            KYCVerification.attempt_number.desc(),
            KYCVerification.id.desc(),
        )
        .first()
    )


def _next_step(
    db: Session,
    user: User,
) -> str:

    # -------------------------------------------------
    # 1. FIRST IDENTIFIER
    # -------------------------------------------------

    if not user.email_verified and not user.phone_verified:
        return user.registration_first_identifier or "email"

    # -------------------------------------------------
    # 2. SECOND IDENTIFIER
    # -------------------------------------------------

    if not user.email_verified:
        return "email"

    if not user.phone_verified:
        return "phone"

    # -------------------------------------------------
    # 3. KYC
    # -------------------------------------------------

    verification = _get_latest_kyc(
        db,
        user,
    )

    if verification is None:
        return "identity"

    if verification.review_status in {
        "rejected",
        "needs_resubmission",
    }:
        return "identity"

    if (
        verification.identity_status
        not in {
            "submitted",
            "approved",
        }
    ):
        return "identity"

    # -------------------------------------------------
    # 4. LIVENESS
    # -------------------------------------------------

    if (
        verification.liveness_status
        not in {
            "submitted",
            "passed",
        }
    ):
        return "liveness"

    # -------------------------------------------------
    # 5. HUMAN REVIEW
    # -------------------------------------------------

    if verification.review_status != "approved":
        return "under_review"

    # -------------------------------------------------
    # 6. TWO FACTOR AUTHENTICATION
    # -------------------------------------------------

    if not user.two_factor_enabled:
        return "two_factor"

    # -------------------------------------------------
    # 7. PROFILE
    # -------------------------------------------------

    if not user.profile_completed:
        return "profile"

    # -------------------------------------------------
    # 8. ACTIVATION
    # -------------------------------------------------

    return "activation"


def _require_step(
    db: Session,
    user: User,
    expected_step: str,
) -> None:
    actual_step = _next_step(
        db,
        user,
    )

    if actual_step != expected_step:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This onboarding step is not available yet.",
                "current_step": actual_step,
            },
        )


@router.post("/register")
def start_registration(
    request: RegistrationStart,
    db: Session = Depends(get_db),
):
    identifier_type, identifier = detect_identifier(
        request.identifier
    )

    if identifier_type == "email":
        existing = (
            db.query(User)
            .filter(User.email == identifier)
            .first()
        )
    else:
        existing = (
            db.query(User)
            .filter(
                User.phone_number == identifier
            )
            .first()
        )

    if existing:
        raise HTTPException(
            status_code=400,
            detail=(
                "An account with this contact information "
                "already exists. Please sign in instead."
            ),
        )

    user = User(
        username=None,
        email=(
            identifier
            if identifier_type == "email"
            else None
        ),
        hashed_password=None,
        full_name=None,
        phone_number=(
            identifier
            if identifier_type == "phone"
            else None
        ),
        email_verified=False,
        phone_verified=False,
        account_status="pending",
        identity_status="not_started",
        liveness_status="not_started",
        is_verified=False,
        is_active=False,
        is_on_hold=False,
        two_factor_enabled=False,
        passkey_enabled=False,
        profile_completed=False,
        registration_first_identifier=identifier_type,
        verification_resend_count=0,
    )

    db.add(user)
    db.flush()

    try:
        _send_for_user(
            user,
            identifier_type,
            identifier,
            db,
            is_resend=False,
        )
    except HTTPException:
        db.rollback()
        raise

    token = create_onboarding_token(
        user.id
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "identifier_type": identifier_type,
        "identifier": identifier,
        "next_step": identifier_type,
    }


@router.get("/state")
def verification_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_onboarding_user
    ),
):
    verification = _get_latest_kyc(
        db,
        current_user,
    )

    review_status = (
        verification.review_status
        if verification
        else "not_started"
    )

    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "phone_number": current_user.phone_number,
        "email_verified": bool(
            current_user.email_verified
        ),
        "phone_verified": bool(
            current_user.phone_verified
        ),
        "identity_status": current_user.identity_status,
        "liveness_status": current_user.liveness_status,
        "account_status": current_user.account_status,
        "next_step": _next_step(
            db,
            current_user,
        ),
        "review_status": review_status,
        "two_factor_enabled": bool(
            current_user.two_factor_enabled
        ),
        "profile_completed": bool(
            current_user.profile_completed
        ),
    }


@router.post("/check")
def check_otp(
    request: OTPCheck,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_onboarding_user
    ),
):
    code = (
        str(request.code or "")
        .strip()
        .replace(" ", "")
    )

    if len(code) != 6 or not code.isdigit():
        raise HTTPException(
            status_code=400,
            detail="Enter the 6-digit verification code.",
        )

    current_step = _next_step(
        db,
        current_user,
    )

    if current_step not in {
        "email",
        "phone",
    }:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "There is no active OTP verification step.",
                "current_step": current_step,
            },
        )

    # ---------------------------------------------
    # EMAIL OTP
    # ---------------------------------------------

    if current_step == "email":
        if not current_user.email:
            raise HTTPException(
                status_code=400,
                detail="No email address is associated with this verification.",
            )

        expires = (
            current_user.email_verification_expires_at
        )

        if not expires or expires <= _utc_now():
            raise HTTPException(
                status_code=400,
                detail=(
                    "This code has expired. "
                    "Please request a new one."
                ),
            )

        attempts = (
            current_user.email_verification_attempts
            or 0
        )

        if attempts >= MAX_VERIFY_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many incorrect attempts. "
                    "Please request a new code."
                ),
            )

        expected = (
            current_user.email_verification_code_hash
        )

        provided = _hash_email_code(
            current_user.email,
            code,
        )

        if (
            not expected
            or not hmac.compare_digest(
                expected,
                provided,
            )
        ):
            current_user.email_verification_attempts = (
                attempts + 1
            )

            db.commit()

            remaining = (
                MAX_VERIFY_ATTEMPTS
                - current_user.email_verification_attempts
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    "Incorrect verification code. "
                    f"Attempts remaining: {remaining}."
                ),
            )

        current_user.email_verified = True
        current_user.email_verification_code_hash = None
        current_user.email_verification_expires_at = None
        current_user.email_verification_attempts = 0

        db.commit()

        return {
            "verified": True,
            "next_step": _next_step(
                db,
                current_user,
            ),
        }

    # ---------------------------------------------
    # PHONE OTP
    # ---------------------------------------------

    if not current_user.phone_number:
        raise HTTPException(
            status_code=400,
            detail="No phone number is associated with this verification.",
        )

    if not verify_twilio_code(
        current_user.phone_number,
        code,
    ):
        raise HTTPException(
            status_code=400,
            detail="Incorrect or expired verification code.",
        )

    current_user.phone_verified = True

    db.commit()

    return {
        "verified": True,
        "next_step": _next_step(
            db,
            current_user,
        ),
    }


@router.post("/start-next")
def start_next_identifier(
    request: IdentifierStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_onboarding_user
    ),
):
    current_step = _next_step(
        db,
        current_user,
    )

    # This endpoint is ONLY valid when the
    # first identifier has been verified.

    if current_step not in {
        "email",
        "phone",
    }:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "The second identifier cannot be started now.",
                "current_step": current_step,
            },
        )

    identifier_type, identifier = detect_identifier(
        request.identifier
    )

    if identifier_type == "email":
        if current_user.email_verified:
            raise HTTPException(
                status_code=400,
                detail="Email is already verified.",
            )

        existing = (
            db.query(User)
            .filter(
                User.email == identifier,
                User.id != current_user.id,
            )
            .first()
        )

    else:
        if current_user.phone_verified:
            raise HTTPException(
                status_code=400,
                detail="Phone number is already verified.",
            )

        existing = (
            db.query(User)
            .filter(
                User.phone_number == identifier,
                User.id != current_user.id,
            )
            .first()
        )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="That contact information is already registered.",
        )

    _send_for_user(
        current_user,
        identifier_type,
        identifier,
        db,
        is_resend=False,
    )

    return {
        "identifier_type": identifier_type,
        "identifier": identifier,
        "next_step": identifier_type,
    }


@router.post("/resend")
def resend_current_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_onboarding_user
    ),
):
    current_step = _next_step(
        db,
        current_user,
    )

    if current_step not in {
        "email",
        "phone",
    }:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "There is no active OTP to resend.",
                "current_step": current_step,
            },
        )

    if current_step == "email":
        if not current_user.email:
            raise HTTPException(
                status_code=400,
                detail="No email address is available.",
            )

        _send_for_user(
            current_user,
            "email",
            current_user.email,
            db,
            is_resend=True,
        )

    else:
        if not current_user.phone_number:
            raise HTTPException(
                status_code=400,
                detail="No phone number is available.",
            )

        _send_for_user(
            current_user,
            "phone",
            current_user.phone_number,
            db,
            is_resend=True,
        )

    return {
        "message": "A new verification code has been sent."
    }