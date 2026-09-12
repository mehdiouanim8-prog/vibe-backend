import base64
import hashlib
import hmac
import os
import secrets
import struct
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import get_current_user


router = APIRouter(
    prefix="/2fa",
    tags=["Two-Factor Authentication"],
)


# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

TOTP_DIGITS = 6
TOTP_PERIOD = 30
TOTP_ALLOWED_DRIFT = 1

TOTP_ISSUER = os.getenv(
    "TOTP_ISSUER",
    "Element",
)


# ─────────────────────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────────────────────

class VerifyTOTPRequest(BaseModel):
    code: str


# ─────────────────────────────────────────────────────────────
# SECRET GENERATION
# ─────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    """
    Generate a 160-bit random TOTP secret encoded using
    Base32 without padding.
    """
    random_bytes = secrets.token_bytes(20)

    return base64.b32encode(
        random_bytes
    ).decode("ascii").rstrip("=")


# ─────────────────────────────────────────────────────────────
# TOTP GENERATION
# ─────────────────────────────────────────────────────────────

def _base32_decode(secret: str) -> bytes:
    padding = "=" * (
        (-len(secret)) % 8
    )

    return base64.b32decode(
        secret + padding,
        casefold=True,
    )


def generate_totp(
    secret: str,
    timestamp: int | None = None,
) -> str:

    if timestamp is None:
        timestamp = int(time.time())

    counter = timestamp // TOTP_PERIOD

    key = _base32_decode(secret)

    message = struct.pack(
        ">Q",
        counter,
    )

    digest = hmac.new(
        key,
        message,
        hashlib.sha1,
    ).digest()

    offset = digest[-1] & 0x0F

    binary_code = (
        ((digest[offset] & 0x7F) << 24)
        | ((digest[offset + 1] & 0xFF) << 16)
        | ((digest[offset + 2] & 0xFF) << 8)
        | (digest[offset + 3] & 0xFF)
    )

    otp = binary_code % (
        10 ** TOTP_DIGITS
    )

    return str(otp).zfill(
        TOTP_DIGITS
    )


# ─────────────────────────────────────────────────────────────
# TOTP VERIFICATION
# ─────────────────────────────────────────────────────────────

def verify_totp(
    secret: str,
    code: str,
) -> bool:

    if (
        len(code) != TOTP_DIGITS
        or not code.isdigit()
    ):
        return False

    now = int(time.time())

    for drift in range(
        -TOTP_ALLOWED_DRIFT,
        TOTP_ALLOWED_DRIFT + 1,
    ):
        timestamp = (
            now
            + drift * TOTP_PERIOD
        )

        expected = generate_totp(
            secret,
            timestamp,
        )

        if hmac.compare_digest(
            expected,
            code,
        ):
            return True

    return False


# ─────────────────────────────────────────────────────────────
# ENCRYPTION HELPERS
# ─────────────────────────────────────────────────────────────

def _get_totp_encryption_key() -> bytes:
    """
    TOTP secrets must not be stored in plaintext.

    This implementation expects a dedicated environment
    secret for encrypting the TOTP secret at rest.
    """

    key = os.getenv(
        "TOTP_ENCRYPTION_KEY"
    )

    if not key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Two-factor authentication is "
                "not configured."
            ),
        )

    return hashlib.sha256(
        key.encode("utf-8")
    ).digest()


def encrypt_totp_secret(
    secret: str,
) -> str:
    """
    Lightweight authenticated encryption wrapper.

    The encryption key must come from TOTP_ENCRYPTION_KEY.

    This is intentionally isolated so it can later be replaced
    with a managed KMS/envelope-encryption implementation without
    changing the API contract.
    """

    key = _get_totp_encryption_key()

    nonce = secrets.token_bytes(16)

    plaintext = secret.encode(
        "utf-8"
    )

    stream = bytearray()

    counter = 0

    while len(stream) < len(plaintext):

        block = hmac.new(
            key,
            nonce
            + counter.to_bytes(
                8,
                "big",
            ),
            hashlib.sha256,
        ).digest()

        stream.extend(block)

        counter += 1

    ciphertext = bytes(
        a ^ b
        for a, b in zip(
            plaintext,
            stream,
        )
    )

    authentication_tag = hmac.new(
        key,
        nonce + ciphertext,
        hashlib.sha256,
    ).digest()

    packed = (
        nonce
        + authentication_tag
        + ciphertext
    )

    return base64.urlsafe_b64encode(
        packed
    ).decode("ascii")


def decrypt_totp_secret(
    encrypted: str,
) -> str:

    key = _get_totp_encryption_key()

    try:
        packed = base64.urlsafe_b64decode(
            encrypted.encode("ascii")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Stored 2FA secret is invalid.",
        ) from exc

    if len(packed) < 48:
        raise HTTPException(
            status_code=500,
            detail="Stored 2FA secret is invalid.",
        )

    nonce = packed[:16]
    authentication_tag = packed[
        16:48
    ]
    ciphertext = packed[48:]

    expected_tag = hmac.new(
        key,
        nonce + ciphertext,
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(
        authentication_tag,
        expected_tag,
    ):
        raise HTTPException(
            status_code=500,
            detail="Stored 2FA secret failed integrity validation.",
        )

    stream = bytearray()

    counter = 0

    while len(stream) < len(ciphertext):

        block = hmac.new(
            key,
            nonce
            + counter.to_bytes(
                8,
                "big",
            ),
            hashlib.sha256,
        ).digest()

        stream.extend(block)

        counter += 1

    plaintext = bytes(
        a ^ b
        for a, b in zip(
            ciphertext,
            stream,
        )
    )

    try:
        return plaintext.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail="Stored 2FA secret is invalid.",
        ) from exc


# ─────────────────────────────────────────────────────────────
# AUTHENTICATOR URI
# ─────────────────────────────────────────────────────────────

def build_otpauth_uri(
    user: User,
    secret: str,
) -> str:

    account_name = (
        user.email.strip()
    )

    issuer = TOTP_ISSUER

    return (
        "otpauth://totp/"
        f"{issuer}:{account_name}"
        "?"
        f"secret={secret}"
        f"&issuer={issuer}"
        f"&algorithm=SHA1"
        f"&digits={TOTP_DIGITS}"
        f"&period={TOTP_PERIOD}"
    )


# ─────────────────────────────────────────────────────────────
# SETUP 2FA
# ─────────────────────────────────────────────────────────────

@router.post("/setup")
def setup_2fa(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.two_factor_enabled:
        return {
            "enabled": True,
            "message": (
                "Two-factor authentication is already enabled."
            ),
        }

    secret = generate_totp_secret()

    encrypted_secret = (
        encrypt_totp_secret(secret)
    )

    current_user.totp_secret_encrypted = (
        encrypted_secret
    )

    db.commit()

    return {
        "enabled": False,
        "secret": secret,
        "otpauth_uri": build_otpauth_uri(
            current_user,
            secret,
        ),
        "digits": TOTP_DIGITS,
        "period": TOTP_PERIOD,
        "issuer": TOTP_ISSUER,
    }


# ─────────────────────────────────────────────────────────────
# VERIFY + ENABLE 2FA
# ─────────────────────────────────────────────────────────────

@router.post("/enable")
def enable_2fa(
    request: VerifyTOTPRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.two_factor_enabled:
        return {
            "enabled": True,
            "message": (
                "Two-factor authentication is already enabled."
            ),
        }

    if not current_user.totp_secret_encrypted:
        raise HTTPException(
            status_code=400,
            detail=(
                "Start the authenticator setup before "
                "attempting to enable two-factor authentication."
            ),
        )

    secret = decrypt_totp_secret(
        current_user.totp_secret_encrypted
    )

    if not verify_totp(
        secret,
        request.code.strip(),
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid authenticator code.",
        )

    current_user.two_factor_enabled = True

    db.commit()
    db.refresh(current_user)

    return {
        "enabled": True,
        "message": (
            "Two-factor authentication enabled successfully."
        ),
        "account_status": current_user.account_status,
    }


# ─────────────────────────────────────────────────────────────
# VERIFY CURRENT 2FA CODE
# ─────────────────────────────────────────────────────────────

@router.post("/verify")
def verify_2fa(
    request: VerifyTOTPRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=400,
            detail=(
                "Two-factor authentication is not enabled."
            ),
        )

    if not current_user.totp_secret_encrypted:
        raise HTTPException(
            status_code=500,
            detail=(
                "Two-factor authentication is incorrectly configured."
            ),
        )

    secret = decrypt_totp_secret(
        current_user.totp_secret_encrypted
    )

    if not verify_totp(
        secret,
        request.code.strip(),
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid authenticator code.",
        )

    return {
        "verified": True,
        "message": "Authenticator code verified.",
    }


# ─────────────────────────────────────────────────────────────
# DISABLE 2FA
# ─────────────────────────────────────────────────────────────

@router.post("/disable")
def disable_2fa(
    request: VerifyTOTPRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.two_factor_enabled:
        return {
            "enabled": False,
            "message": (
                "Two-factor authentication is already disabled."
            ),
        }

    if not current_user.totp_secret_encrypted:
        raise HTTPException(
            status_code=500,
            detail=(
                "Two-factor authentication is incorrectly configured."
            ),
        )

    secret = decrypt_totp_secret(
        current_user.totp_secret_encrypted
    )

    if not verify_totp(
        secret,
        request.code.strip(),
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid authenticator code.",
        )

    current_user.two_factor_enabled = False
    current_user.totp_secret_encrypted = None

    # Removing the authenticator means the account can no longer
    # satisfy the final Element security gate.
    if current_user.account_status == "active":
        current_user.account_status = "pending"

    db.commit()

    return {
        "enabled": False,
        "message": (
            "Two-factor authentication disabled."
        ),
        "account_status": current_user.account_status,
    }