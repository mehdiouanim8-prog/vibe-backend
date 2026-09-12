import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models import User, KYCVerification
from security import get_current_user


router = APIRouter(
    prefix="/kyc",
    tags=["KYC"],
)


# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

SUMSUB_API_BASE_URL = os.getenv(
    "SUMSUB_API_BASE_URL",
    "https://api.sumsub.com",
).rstrip("/")

SUMSUB_APP_TOKEN = os.getenv("SUMSUB_APP_TOKEN")
SUMSUB_SECRET_KEY = os.getenv("SUMSUB_SECRET_KEY")
SUMSUB_LEVEL_NAME = os.getenv("SUMSUB_LEVEL_NAME")

SUMSUB_WEBHOOK_SECRET = os.getenv("SUMSUB_WEBHOOK_SECRET")


# ─────────────────────────────────────────────────────────────
# INTERNAL EXCEPTION
# ─────────────────────────────────────────────────────────────

class SumsubAPIError(Exception):
    def __init__(
        self,
        status_code: int,
        payload: Any,
    ):
        self.status_code = status_code
        self.payload = payload
        super().__init__(
            f"Sumsub API error: HTTP {status_code}"
        )


# ─────────────────────────────────────────────────────────────
# CONFIG HELPERS
# ─────────────────────────────────────────────────────────────

def _require_sumsub_config(
    require_webhook_secret: bool = False,
) -> None:
    missing = []

    if not SUMSUB_APP_TOKEN:
        missing.append("SUMSUB_APP_TOKEN")

    if not SUMSUB_SECRET_KEY:
        missing.append("SUMSUB_SECRET_KEY")

    if not SUMSUB_LEVEL_NAME:
        missing.append("SUMSUB_LEVEL_NAME")

    if require_webhook_secret and not SUMSUB_WEBHOOK_SECRET:
        missing.append("SUMSUB_WEBHOOK_SECRET")

    if missing:
        raise HTTPException(
            status_code=503,
            detail="KYC provider is not configured.",
        )


# ─────────────────────────────────────────────────────────────
# SUMSUB SIGNED REQUEST
# ─────────────────────────────────────────────────────────────

def _sumsub_request(
    method: str,
    uri: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    _require_sumsub_config()

    method = method.upper()

    if payload is None:
        body = b""
    else:
        body = json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    timestamp = str(int(time.time()))

    signing_bytes = (
        timestamp
        + method
        + uri
    ).encode("utf-8") + body

    signature = hmac.new(
        SUMSUB_SECRET_KEY.encode("utf-8"),
        signing_bytes,
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "X-App-Token": SUMSUB_APP_TOKEN,
        "X-App-Access-Sig": signature,
        "X-App-Access-Ts": timestamp,
        "Accept": "application/json",
    }

    if body:
        headers["Content-Type"] = "application/json"

    url = f"{SUMSUB_API_BASE_URL}{uri}"

    try:
        with httpx.Client(
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            response = client.request(
                method=method,
                url=url,
                headers=headers,
                content=body if body else None,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail="KYC verification service is temporarily unavailable.",
        ) from exc

    if response.status_code >= 400:
        try:
            error_payload = response.json()
        except Exception:
            error_payload = {}

        raise SumsubAPIError(
            response.status_code,
            error_payload,
        )

    if not response.content:
        return {}

    try:
        return response.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="KYC provider returned an invalid response.",
        ) from exc


# ─────────────────────────────────────────────────────────────
# SUMSUB APPLICANT
# ─────────────────────────────────────────────────────────────

def _external_user_id(
    user_id: int,
    attempt_number: int,
) -> str:
    return f"element-{user_id}-{attempt_number}"


def _find_sumsub_applicant(
    external_user_id: str,
) -> Dict[str, Any]:

    encoded = quote(
        external_user_id,
        safe="",
    )

    uri = (
        "/resources/applicants/-;"
        f"externalUserId={encoded}/one"
    )

    return _sumsub_request(
        "GET",
        uri,
    )


def _create_or_get_sumsub_applicant(
    user: User,
    external_user_id: str,
) -> Dict[str, Any]:

    level_query = urlencode(
        {
            "levelName": SUMSUB_LEVEL_NAME,
        }
    )

    uri = (
        "/resources/applicants?"
        f"{level_query}"
    )

    payload: Dict[str, Any] = {
        "externalUserId": external_user_id,
        "type": "individual",
        "fixedInfo": {
            "email": user.email,
        },
    }

    if user.phone_number:
        payload["fixedInfo"]["phone"] = user.phone_number

    try:
        return _sumsub_request(
            "POST",
            uri,
            payload,
        )

    except SumsubAPIError as exc:
        # Applicant already exists.
        if exc.status_code == 409:
            return _find_sumsub_applicant(
                external_user_id
            )

        raise


def _generate_sumsub_websdk_link(
    user: User,
    external_user_id: str,
) -> str:

    query = urlencode(
        {
            "lang": "en",
            "source": "api",
        }
    )

    uri = (
        "/resources/sdkIntegrations/levels/-/websdkLink?"
        f"{query}"
    )

    identifiers: Dict[str, Any] = {
        "email": user.email,
    }

    if user.phone_number:
        identifiers["phone"] = user.phone_number

    payload = {
        "levelName": SUMSUB_LEVEL_NAME,
        "userId": external_user_id,
        "applicantIdentifiers": identifiers,
        "ttlInSecs": 1800,
    }

    result = _sumsub_request(
        "POST",
        uri,
        payload,
    )

    verification_url = result.get("url")

    if not verification_url:
        raise HTTPException(
            status_code=502,
            detail="KYC provider did not return a verification URL.",
        )

    return verification_url


# ─────────────────────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────────────────────

def get_latest_verification(
    db: Session,
    user_id: int,
) -> Optional[KYCVerification]:

    return (
        db.query(KYCVerification)
        .filter(
            KYCVerification.user_id == user_id
        )
        .order_by(
            KYCVerification.attempt_number.desc(),
            KYCVerification.id.desc(),
        )
        .first()
    )


def get_verification_by_provider(
    db: Session,
    external_user_id: Optional[str],
    applicant_id: Optional[str],
) -> Optional[KYCVerification]:

    if external_user_id:
        verification = (
            db.query(KYCVerification)
            .filter(
                KYCVerification.provider_external_user_id
                == external_user_id
            )
            .order_by(
                KYCVerification.id.desc()
            )
            .first()
        )

        if verification:
            return verification

    if applicant_id:
        return (
            db.query(KYCVerification)
            .filter(
                KYCVerification.provider_applicant_id
                == applicant_id
            )
            .order_by(
                KYCVerification.id.desc()
            )
            .first()
        )

    return None


def get_next_attempt_number(
    db: Session,
    user_id: int,
) -> int:

    latest = get_latest_verification(
        db,
        user_id,
    )

    if latest is None:
        return 1

    return latest.attempt_number + 1


# ─────────────────────────────────────────────────────────────
# STATE MACHINE
# ─────────────────────────────────────────────────────────────

def determine_next_step(
    user: User,
    verification: Optional[KYCVerification],
) -> str:

    # 1. Email
    if not bool(user.email_verified):
        return "email"

    # 2. Phone
    if not bool(user.phone_verified):
        return "phone"

    # 3. No KYC attempt
    if verification is None:
        return "identity"

    # 4. Previous attempt requires resubmission
    if verification.review_status in {
        "rejected",
        "needs_resubmission",
    }:
        return "identity"

    # 5. Submitted and waiting for provider review.
    # This MUST be checked before the individual verification
    # states so "pending" cannot accidentally return "identity".
    if verification.review_status == "pending":
        return "under_review"

    # 6. Identity not approved yet
    if verification.identity_status not in {
        "approved",
    }:
        return "identity"

    # 7. Liveness not passed yet
    if verification.liveness_status not in {
        "passed",
    }:
        return "liveness"

    # 8. Provider approved KYC
    if verification.review_status == "approved":

        if not bool(user.two_factor_enabled):
            return "two_factor"

        if not bool(user.profile_completed):
            return "profile"

        if user.account_status != "active":
            return "activation"

        return "complete"

    # Safe fallback
    return "identity"