import os
import re
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import get_current_user


router = APIRouter(
    prefix="/phone",
    tags=["Phone Verification"],
)


# ─────────────────────────────────────────────────────────────
# TWILIO CONFIGURATION
# ─────────────────────────────────────────────────────────────

TWILIO_VERIFY_BASE_URL = (
    "https://verify.twilio.com/v2"
)

TWILIO_API_KEY_SID = os.getenv(
    "TWILIO_API_KEY_SID"
)

TWILIO_API_KEY_SECRET = os.getenv(
    "TWILIO_API_KEY_SECRET"
)

TWILIO_VERIFY_SERVICE_SID = os.getenv(
    "TWILIO_VERIFY_SERVICE_SID"
)


# ─────────────────────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────────────────────

class PhoneVerificationSend(BaseModel):
    phone_number: str


class PhoneVerificationCheck(BaseModel):
    code: str


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

E164_PATTERN = re.compile(
    r"^\+[1-9]\d{7,14}$"
)


def _require_twilio_config() -> None:
    missing = []

    if not TWILIO_API_KEY_SID:
        missing.append(
            "TWILIO_API_KEY_SID"
        )

    if not TWILIO_API_KEY_SECRET:
        missing.append(
            "TWILIO_API_KEY_SECRET"
        )

    if not TWILIO_VERIFY_SERVICE_SID:
        missing.append(
            "TWILIO_VERIFY_SERVICE_SID"
        )

    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                "Phone verification service is not configured."
            ),
        )


def _normalize_phone(
    phone_number: str,
) -> str:

    value = (
        str(phone_number)
        .strip()
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if not E164_PATTERN.fullmatch(value):
        raise HTTPException(
            status_code=400,
            detail=(
                "Phone number must be in international "
                "E.164 format, for example +2126XXXXXXXX."
            ),
        )

    return value


def _twilio_error_message(
    response: httpx.Response,
) -> str:

    try:
        payload = response.json()
    except Exception:
        return (
            "Phone verification service returned an error."
        )

    # Do not return the provider's entire response
    # to the client.
    message = payload.get("message")

    if isinstance(message, str) and message.strip():
        return message.strip()

    return (
        "Phone verification service returned an error."
    )


def _twilio_request(
    method: str,
    path: str,
    data: Optional[dict] = None,
) -> dict:

    _require_twilio_config()

    url = (
        f"{TWILIO_VERIFY_BASE_URL}"
        f"{path}"
    )

    try:
        with httpx.Client(
            timeout=20.0,
            follow_redirects=True,
        ) as client:

            response = client.request(
                method=method,
                url=url,
                data=data,
                auth=(
                    TWILIO_API_KEY_SID,
                    TWILIO_API_KEY_SECRET,
                ),
            )

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Phone verification service is "
                "temporarily unavailable."
            ),
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=_twilio_error_message(
                response
            ),
        )

    try:
        return response.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Phone verification service returned "
                "an invalid response."
            ),
        ) from exc


# ─────────────────────────────────────────────────────────────
# POST /phone/send
# ─────────────────────────────────────────────────────────────

@router.post("/send")
def send_phone_verification(
    request: PhoneVerificationSend,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    phone_number = _normalize_phone(
        request.phone_number
    )

    # Do not permit one phone number to be attached
    # to multiple accounts.
    existing_user = (
        db.query(User)
        .filter(
            User.phone_number == phone_number,
            User.id != current_user.id,
        )
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="This phone number is already registered.",
        )

    if (
        current_user.phone_verified
        and current_user.phone_number
        == phone_number
    ):
        return {
            "message": "Phone number is already verified.",
            "phone_verified": True,
        }

    result = _twilio_request(
        "POST",
        (
            "/Services/"
            f"{TWILIO_VERIFY_SERVICE_SID}"
            "/Verifications"
        ),
        {
            "To": phone_number,
            "Channel": "sms",
        },
    )

    provider_status = result.get(
        "status"
    )

    if provider_status != "pending":
        raise HTTPException(
            status_code=502,
            detail=(
                "Phone verification could not be started."
            ),
        )

    # Store the claimed number, but do not mark it
    # verified until the OTP is successfully checked.
    current_user.phone_number = phone_number
    current_user.phone_verified = False

    db.commit()
    db.refresh(current_user)

    return {
        "message": (
            "A verification code has been sent."
        ),
        "phone_verified": False,
    }


# ─────────────────────────────────────────────────────────────
# POST /phone/check
# ─────────────────────────────────────────────────────────────

@router.post("/check")
def check_phone_verification(
    request: PhoneVerificationCheck,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_twilio_config()

    if not current_user.phone_number:
        raise HTTPException(
            status_code=400,
            detail=(
                "No phone number has been registered "
                "for this account."
            ),
        )

    if current_user.phone_verified:
        return {
            "message": "Phone number is already verified.",
            "phone_verified": True,
            "account_status": current_user.account_status,
        }

    code = (
        str(request.code)
        .strip()
        .replace(" ", "")
    )

    if (
        len(code) < 4
        or len(code) > 10
        or not code.isdigit()
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code.",
        )

    result = _twilio_request(
        "POST",
        (
            "/Services/"
            f"{TWILIO_VERIFY_SERVICE_SID}"
            "/VerificationCheck"
        ),
        {
            "To": current_user.phone_number,
            "Code": code,
        },
    )

    provider_status = result.get(
        "status"
    )

    if provider_status != "approved":
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code.",
        )

    # Only the trusted provider result can change
    # this state.
    current_user.phone_verified = True

    # Phone verification NEVER activates the account.
    #
    # KYC, liveness, security review, 2FA and all
    # other required account gates still remain.
    if current_user.account_status not in {
        "suspended",
        "rejected",
    }:
        current_user.account_status = "pending"

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Phone number verified successfully.",
        "phone_verified": True,
        "account_status": current_user.account_status,
        "next_step": "identity",
    }