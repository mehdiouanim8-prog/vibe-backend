from datetime import datetime, timedelta
from typing import Optional

import os

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import User


# ─────────────────────────────────────────────
# SECURITY CONFIG
# ─────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()

if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY must be configured and at least 32 characters long."
    )

ALGORITHM = "HS256"

# Normal authenticated sessions
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

# Onboarding sessions
ONBOARDING_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


# ─────────────────────────────────────────────
# PASSWORDS
# ─────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─────────────────────────────────────────────
# NORMAL AUTHENTICATED TOKEN
# ─────────────────────────────────────────────

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
):
    to_encode = data.copy()

    to_encode["token_type"] = "access"

    expire = datetime.utcnow() + (
        expires_delta
        or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode["exp"] = expire

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# ─────────────────────────────────────────────
# ONBOARDING TOKEN
# ─────────────────────────────────────────────

def create_onboarding_token(
    user_id: int,
    expires_delta: Optional[timedelta] = None,
):
    expire = datetime.utcnow() + (
        expires_delta
        or timedelta(minutes=ONBOARDING_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "user_id": user_id,
        "token_type": "onboarding",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# ─────────────────────────────────────────────
# NORMAL AUTHENTICATED USER
# ─────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("user_id")
        token_type = payload.get("token_type")

        if user_id is None:
            raise credentials_exception

        # An onboarding token can NEVER be used as
        # a normal authenticated session.
        if token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None or not user.is_active:
        raise credentials_exception

    return user


# ─────────────────────────────────────────────
# ONBOARDING USER
# ─────────────────────────────────────────────

def get_current_onboarding_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired onboarding session",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("user_id")
        token_type = payload.get("token_type")

        if user_id is None:
            raise credentials_exception

        # Only onboarding tokens are accepted here.
        if token_type != "onboarding":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user
