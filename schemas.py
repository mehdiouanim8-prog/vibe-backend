from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ─── User Schemas ───────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    created_at: datetime
    followers_count: Optional[int] = 0
    following_count: Optional[int] = 0

    class Config:
        orm_mode = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ─── Token Schemas ───────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None


# ─── Post Schemas ────────────────────────────────────────────

class PostCreate(BaseModel):
    content: str
    image_url: Optional[str] = None

class PostOut(BaseModel):
    id: int
    content: str
    image_url: Optional[str]
    author_id: int
    author: UserOut
    created_at: datetime
    likes_count: Optional[int] = 0
    comments_count: Optional[int] = 0

    class Config:
        orm_mode = True


# ─── Comment Schemas ─────────────────────────────────────────

class CommentCreate(BaseModel):
    content: str

class CommentOut(BaseModel):
    id: int
    content: str
    author: UserOut
    post_id: int
    created_at: datetime

    class Config:
        orm_mode = True


# ─── Feed Schema ─────────────────────────────────────────────

class FeedOut(BaseModel):
    posts: List[PostOut]
    total: int
    page: int
    per_page: int
