import hashlib
import hmac
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import UserCreate, UserOut, Token
from security import (
    SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ============================================================
# CONFIGURATION
# ============================================================

EMAIL_CODE_EXPIRE_MINUTES = 10

# Maximum number of incorrect code submissions.
MAX_EMAIL_VERIFICATION_ATTEMPTS = 5

# Maximum number of times a new code may be requested
# within the resend window.
MAX_EMAIL_RESENDS = 3

# Time window used for the resend limit.
EMAIL_RESEND_WINDOW_MINUTES = 30


# ============================================================
# REQUEST MODELS
# ============================================================

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class EmailVerificationRequest(BaseModel):
    email: EmailStr
    code: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# ============================================================
# HELPERS
# ============================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_verification_code() -> str:
    """
    Generate a cryptographically secure six-digit code.
    """
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_verification_code(
    email: str,
    code: str,
) -> str:
    """
    Store only an HMAC-derived value, never the plaintext
    verification code.
    """
    message = (
        f"element-email-verification:"
        f"{email.lower()}:"
        f"{code}"
    ).encode("utf-8")

    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _password_is_valid(password: str) -> bool:
    """
    bcrypt accepts at most 72 UTF-8 bytes.
    """
    if len(password.encode("utf-8")) > 72:
        return False

    if len(password) < 8:
        return False

    return True


def _send_verification_email(
    email: str,
    full_name: Optional[str],
    code: str,
) -> None:
    """
    Send the Element verification email using SMTP.
    """

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port_raw = os.getenv("SMTP_PORT", "587")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_from = os.getenv("EMAIL_FROM") or smtp_username

    use_tls = os.getenv(
        "SMTP_USE_TLS",
        "true",
    ).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    use_ssl = os.getenv(
        "SMTP_USE_SSL",
        "false",
    ).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if not smtp_host:
        raise RuntimeError(
            "SMTP_HOST is not configured."
        )

    if not email_from:
        raise RuntimeError(
            "EMAIL_FROM is not configured."
        )

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError as exc:
        raise RuntimeError(
            "SMTP_PORT must be a valid integer."
        ) from exc

    display_name = (
        full_name.strip()
        if full_name
        else "there"
    )

    subject = "Verify your Element email"

    body = f"""
Hello {display_name},

Welcome to Element.

Your email verification code is:

{code}

This code expires in {EMAIL_CODE_EXPIRE_MINUTES} minutes.

If you did not create an Element account, you can safely ignore this email.

Element
""".strip()

    message = MIMEText(
        body,
        "plain",
        "utf-8",
    )

    message["Subject"] = subject
    message["From"] = email_from
    message["To"] = email

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(
                smtp_host,
                smtp_port,
                timeout=20,
            ) as server:

                if smtp_username and smtp_password:
                    server.login(
                        smtp_username,
                        smtp_password,
                    )

                server.sendmail(
                    email_from,
                    [email],
                    message.as_string(),
                )

        else:
            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=20,
            ) as server:

                server.ehlo()

                if use_tls:
                    server.starttls()
                    server.ehlo()

                if smtp_username and smtp_password:
                    server.login(
                        smtp_username,
                        smtp_password,
                    )

                server.sendmail(
                    email_from,
                    [email],
                    message.as_string(),
                )

    except Exception as exc:
        raise RuntimeError(
            f"Email delivery failed: {exc}"
        ) from exc


def _check_hard_account_block(
    user: User,
) -> None:

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    if user.is_on_hold:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is currently on hold.",
        )

    if user.account_status in {
        "suspended",
        "rejected",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This account is not permitted "
                "to sign in."
            ),
        )


# ============================================================
# REGISTER
# ============================================================

@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):

    email = (
        user_data.email
        .strip()
        .lower()
    )

    username = (
        user_data.username
        .strip()
    )

    full_name = (
        user_data.full_name.strip()
        if user_data.full_name
        else None
    )

    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is required.",
        )

    if not _password_is_valid(
        user_data.password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Password must contain at least "
                "8 characters and be no more than "
                "72 UTF-8 bytes."
            ),
        )

    existing_email = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )

    existing_username = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken.",
        )

    phone_number = None

    if user_data.phone_number:
        phone_number = (
            user_data.phone_number.strip()
        )

        if not phone_number:
            phone_number = None

        if phone_number:

            existing_phone = (
                db.query(User)
                .filter(
                    User.phone_number
                    == phone_number
                )
                .first()
            )

            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Phone number already "
                        "registered."
                    ),
                )

    verification_code = (
        _generate_verification_code()
    )

    verification_code_hash = (
        _hash_verification_code(
            email,
            verification_code,
        )
    )

    now = _utc_now()

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(
            user_data.password
        ),
        full_name=full_name,
        phone_number=phone_number,

        email_verified=False,
        phone_verified=False,

        identity_status="not_started",
        liveness_status="not_started",

        account_status="pending",

        is_verified=False,
        is_active=True,
        is_on_hold=False,

        two_factor_enabled=False,
        passkey_enabled=False,

        profile_completed=False,

        email_verification_code_hash=(
            verification_code_hash
        ),

        email_verification_expires_at=(
            now
            + timedelta(
                minutes=EMAIL_CODE_EXPIRE_MINUTES
            )
        ),

        email_verification_attempts=0,
    )

    # The current User model does not contain a
    # dedicated resend counter/timestamp, so the
    # resend policy is intentionally kept separate
    # for now rather than silently adding database
    # fields here.

    try:

        db.add(user)

        db.flush()

        _send_verification_email(
            email=email,
            full_name=full_name,
            code=verification_code,
        )

        db.commit()

        db.refresh(user)

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Element could not send the "
                "verification email. "
                "Please try again later."
            ),
        ) from exc

    return user


# ============================================================
# LOGIN
# ============================================================

@router.post(
    "/login",
    response_model=Token,
)
def login(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):

    email = (
        credentials.email
        .strip()
        .lower()
    )

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if (
        not user
        or not verify_password(
            credentials.password,
            user.hashed_password,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    _check_hard_account_block(user)

    token = create_access_token(
        {
            "user_id": user.id,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


# ============================================================
# VERIFY EMAIL
# ============================================================

@router.post("/verify-email")
def verify_email(
    request: EmailVerificationRequest,
    db: Session = Depends(get_db),
):

    email = (
        request.email
        .strip()
        .lower()
    )

    code = request.code.strip()

    if (
        len(code) != 6
        or not code.isdigit()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )

    if user.email_verified:
        return {
            "message": "Email is already verified.",
            "email_verified": True,
            "account_status": user.account_status,
        }

    _check_hard_account_block(user)

    attempts = (
        user.email_verification_attempts
        or 0
    )

    if attempts >= MAX_EMAIL_VERIFICATION_ATTEMPTS:
        raise HTTPException(
            status_code=(
                status.HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=(
                "Too many incorrect verification "
                "attempts. Please request a new "
                "verification code."
            ),
        )

    expires_at = (
        user.email_verification_expires_at
    )

    if (
        not expires_at
        or expires_at <= _utc_now()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Verification code has expired. "
                "Please request a new code."
            ),
        )

    expected_hash = (
        user.email_verification_code_hash
    )

    if not expected_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Verification code is no "
                "longer valid."
            ),
        )

    provided_hash = (
        _hash_verification_code(
            email,
            code,
        )
    )

    if not hmac.compare_digest(
        expected_hash,
        provided_hash,
    ):

        user.email_verification_attempts = (
            attempts + 1
        )

        db.commit()

        remaining = max(
            0,
            MAX_EMAIL_VERIFICATION_ATTEMPTS
            - user.email_verification_attempts,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid verification code. "
                f"Attempts remaining: {remaining}."
            ),
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    user.email_verified = True

    user.email_verification_code_hash = None

    user.email_verification_expires_at = None

    user.email_verification_attempts = 0

    # Email verification alone does NOT activate
    # the account.
    user.account_status = "pending"

    db.commit()
    db.refresh(user)

    return {
        "message": (
            "Email verified successfully."
        ),
        "email_verified": True,
        "account_status": user.account_status,
        "next_step": "phone",
    }


# ============================================================
# RESEND EMAIL VERIFICATION
# ============================================================

@router.post("/resend-verification")
def resend_verification(
    request: ResendVerificationRequest,
    db: Session = Depends(get_db),
):

    email = (
        request.email
        .strip()
        .lower()
    )

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        return {
            "message": (
                "If the account exists and requires "
                "verification, a new verification "
                "email has been sent."
            )
        }

    if user.email_verified:
        return {
            "message": (
                "Your email is already verified."
            )
        }

    _check_hard_account_block(user)

    verification_code = (
        _generate_verification_code()
    )

    user.email_verification_code_hash = (
        _hash_verification_code(
            email,
            verification_code,
        )
    )

    user.email_verification_expires_at = (
        _utc_now()
        + timedelta(
            minutes=EMAIL_CODE_EXPIRE_MINUTES
        )
    )

    user.email_verification_attempts = 0

    try:

        _send_verification_email(
            email=email,
            full_name=user.full_name,
            code=verification_code,
        )

        db.commit()

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Element could not send the "
                "verification email. "
                "Please try again later."
            ),
        ) from exc

    return {
        "message": (
            "If the account exists and requires "
            "verification, a new verification "
            "email has been sent."
        )
    }
