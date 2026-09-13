from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from database import get_db
from models import User
from schemas import UserCreate, UserOut, Token
from security import hash_password, verify_password, create_access_token
from email_verification import _generate_code, _hash_code, _send_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


class UserLogin(BaseModel):
    email: str
    password: str


@router.post("/register", response_model=UserOut, status_code=201)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if len(user_data.password) > 72:
        raise HTTPException(status_code=400, detail="Password must be 72 characters or less")

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        phone_number=user_data.phone_number,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Send the first email verification code right away so the
    # user isn't stuck waiting on a separate frontend round-trip.
    # If sending fails (e.g. SMTP not configured yet), we don't
    # block account creation — the user can request a new code
    # from the verify-email screen instead.
    try:
        code = _generate_code()
        _send_email(user.email, code)
        user.email_verification_code_hash = _hash_code(code)
        user.email_verification_expires_at = datetime.utcnow() + timedelta(minutes=10)
        user.email_verification_attempts = 0
        db.commit()
    except HTTPException:
        pass

    return user


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"user_id": user.id})
    return {"access_token": token, "token_type": "bearer"}
