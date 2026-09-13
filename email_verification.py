import hashlib
import os
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import get_current_user


router = APIRouter(
    prefix="/email",
    tags=["Email Verification"],
)


# ─────────────────────────────────────────────────────────────
# SMTP CONFIGURATION (Gmail — free, real delivery)
# ─────────────────────────────────────────────────────────────
#
# Set these as environment variables on your host (Railway/Render/etc):
#   SMTP_EMAIL    = your-gmail-address@gmail.com
#   SMTP_PASSWORD = 16-character Gmail App Password
#     (create one at https://myaccount.google.com/apppasswords —
#      requires 2-Step Verification enabled on that Google account)
#
# Do NOT use your real Gmail password — App Passwords are required
# because Google blocks plain-password SMTP logins from apps.

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

OTP_LENGTH = 6
OTP_TTL_MINUTES = 10
MAX_VERIFY_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


# ─────────────────────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────────────────────

class EmailVerificationCheck(BaseModel):
    code: str


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _require_smtp_config() -> None:
    missing = []
    if not SMTP_EMAIL:
        missing.append("SMTP_EMAIL")
    if not SMTP_PASSWORD:
        missing.append("SMTP_PASSWORD")
    if missing:
        raise HTTPException(
            status_code=503,
            detail="Email verification service is not configured.",
        )


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _generate_code() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(OTP_LENGTH))


def _send_email(to_email: str, code: str) -> None:
    """
    Sends the OTP via real Gmail SMTP over SSL.
    Raises HTTPException if sending genuinely fails —
    callers should NOT silently pretend success on failure,
    since the user needs the code to proceed.
    """
    _require_smtp_config()

    subject = "Your Element verification code"
    text_body = (
        f"Your Element verification code is: {code}\n\n"
        f"This code expires in {OTP_TTL_MINUTES} minutes.\n"
        f"If you didn't request this, you can safely ignore this email."
    )
    html_body = f"""
    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #6c47ff;">Element</h2>
      <p>Your verification code is:</p>
      <div style="font-size: 32px; font-weight: 700; letter-spacing: 8px;
                  background: #f0f2f5; padding: 16px 24px; border-radius: 12px;
                  text-align: center; color: #0a0a0f;">
        {code}
      </div>
      <p style="color: #666; font-size: 13px; margin-top: 16px;">
        This code expires in {OTP_TTL_MINUTES} minutes. If you didn't request this, you can ignore this email.
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Email service authentication failed. Check server configuration.",
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not send verification email. Please try again shortly.",
        ) from exc


# ─────────────────────────────────────────────────────────────
# POST /email/send
# ─────────────────────────────────────────────────────────────

@router.post("/send")
def send_email_verification(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.email_verified:
        return {
            "message": "Email is already verified.",
            "email_verified": True,
        }

    # Rate-limit resends so the mailbox/provider isn't hammered
    if current_user.email_verification_expires_at:
        seconds_since_last_send = (
            OTP_TTL_MINUTES * 60
            - (
                current_user.email_verification_expires_at
                - datetime.utcnow()
            ).total_seconds()
        )
        if 0 < seconds_since_last_send < RESEND_COOLDOWN_SECONDS:
            wait = int(RESEND_COOLDOWN_SECONDS - seconds_since_last_send)
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {wait} seconds before requesting another code.",
            )

    code = _generate_code()

    _send_email(current_user.email, code)

    # Only store the hash — never the raw code — matching the
    # security posture already defined in models.py
    current_user.email_verification_code_hash = _hash_code(code)
    current_user.email_verification_expires_at = datetime.utcnow() + timedelta(
        minutes=OTP_TTL_MINUTES
    )
    current_user.email_verification_attempts = 0
    db.commit()

    return {
        "message": "A verification code has been sent to your email.",
        "email_verified": False,
    }


# ─────────────────────────────────────────────────────────────
# POST /email/check
# ─────────────────────────────────────────────────────────────

@router.post("/check")
def check_email_verification(
    request: EmailVerificationCheck,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.email_verified:
        return {
            "message": "Email is already verified.",
            "email_verified": True,
            "account_status": current_user.account_status,
        }

    if not current_user.email_verification_code_hash:
        raise HTTPException(
            status_code=400,
            detail="No verification code was requested. Please request a new code.",
        )

    if (
        current_user.email_verification_expires_at is None
        or datetime.utcnow() > current_user.email_verification_expires_at
    ):
        raise HTTPException(
            status_code=400,
            detail="This code has expired. Please request a new one.",
        )

    if current_user.email_verification_attempts >= MAX_VERIFY_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many incorrect attempts. Please request a new code.",
        )

    code = str(request.code).strip().replace(" ", "")
    if len(code) != OTP_LENGTH or not code.isdigit():
        raise HTTPException(status_code=400, detail="Invalid verification code.")

    if _hash_code(code) != current_user.email_verification_code_hash:
        current_user.email_verification_attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect verification code.")

    # Success — clear the OTP fields, they're single-use
    current_user.email_verified = True
    current_user.email_verification_code_hash = None
    current_user.email_verification_expires_at = None
    current_user.email_verification_attempts = 0

    if current_user.account_status not in {"suspended", "rejected"}:
        current_user.account_status = "pending"

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Email verified successfully.",
        "email_verified": True,
        "account_status": current_user.account_status,
        "next_step": "phone",
    }