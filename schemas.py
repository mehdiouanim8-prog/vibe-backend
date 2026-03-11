from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ─── User ────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    full_name:  Optional[str] = None
    headline:   Optional[str] = None
    bio:        Optional[str] = None
    location:   Optional[str] = None
    website:    Optional[str] = None
    avatar_url: Optional[str] = None
    cover_url:  Optional[str] = None
    language:   Optional[str] = None


class UserOut(BaseModel):
    id:                  int
    username:            str
    email:               str
    full_name:           Optional[str]   = None
    headline:            Optional[str]   = None
    bio:                 Optional[str]   = None
    location:            Optional[str]   = None
    website:             Optional[str]   = None
    avatar_url:          Optional[str]   = None
    cover_url:           Optional[str]   = None
    is_admin:            bool            = False
    is_premium:          bool            = False
    is_verified:         bool            = False
    is_verified_company: bool            = False
    is_active:           bool            = True
    language:            Optional[str]   = "English"
    followers_count:     Optional[int]   = 0
    following_count:     Optional[int]   = 0
    is_followed:         Optional[bool]  = False
    created_at:          Optional[datetime] = None

    class Config:
        orm_mode = True


# ─── Post ────────────────────────────────────────────────────

class PostCreate(BaseModel):
    content:      str
    image_url:    Optional[str] = None
    community_id: Optional[int] = None
    tags:         Optional[str] = None
    feeling:      Optional[str] = None


class PostOut(BaseModel):
    id:            int
    content:       str
    image_url:     Optional[str]  = None
    tags:          Optional[str]  = None
    feeling:       Optional[str]  = None
    author_id:     int
    community_id:  Optional[int]  = None
    is_archived:   bool           = False
    created_at:    datetime
    likes_count:   int            = 0
    comments_count:int            = 0
    is_liked:      bool           = False
    user_reaction: Optional[str]  = None
    author:        Optional[UserOut] = None

    class Config:
        orm_mode = True


class FeedOut(BaseModel):
    posts:    List[PostOut]
    total:    int
    page:     int
    per_page: int


# ─── Comment ─────────────────────────────────────────────────

class CommentCreate(BaseModel):
    content:   str
    parent_id: Optional[int] = None


class CommentOut(BaseModel):
    id:         int
    content:    str
    author_id:  int
    post_id:    int
    parent_id:  Optional[int] = None
    created_at: datetime
    author:     Optional[UserOut] = None

    class Config:
        orm_mode = True


# ─── Follow ───────────────────────────────────────────────────

class FollowOut(BaseModel):
    id:           int
    follower_id:  int
    following_id: int
    created_at:   datetime

    class Config:
        orm_mode = True


# ─── Notification ─────────────────────────────────────────────

class NotificationOut(BaseModel):
    id:           int
    user_id:      int
    type:         str
    message:      str
    is_read:      bool
    post_id:      Optional[int]  = None
    from_user_id: Optional[int]  = None
    created_at:   datetime

    class Config:
        orm_mode = True


# ─── Token ───────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type:   str


class TokenData(BaseModel):
    username: Optional[str] = None


# ─── Job ─────────────────────────────────────────────────────

class JobCreate(BaseModel):
    title:        str
    company:      str
    location:     Optional[str] = None
    description:  Optional[str] = None
    salary_range: Optional[str] = None
    job_type:     Optional[str] = None


class JobOut(BaseModel):
    id:           int
    title:        str
    company:      str
    location:     Optional[str] = None
    description:  Optional[str] = None
    salary_range: Optional[str] = None
    job_type:     Optional[str] = None
    poster_id:    Optional[int] = None
    created_at:   datetime

    class Config:
        orm_mode = True


# ─── Message ─────────────────────────────────────────────────

class MessageCreate(BaseModel):
    receiver_id: int
    content:     str


class MessageOut(BaseModel):
    id:          int
    sender_id:   int
    receiver_id: int
    content:     str
    is_read:     bool
    created_at:  datetime

    class Config:
        orm_mode = True


# ─── Event ───────────────────────────────────────────────────

class EventCreate(BaseModel):
    title:       str
    description: Optional[str] = None
    location:    Optional[str] = None
    start_date:  Optional[datetime] = None
    end_date:    Optional[datetime] = None
    image_url:   Optional[str] = None


class EventOut(BaseModel):
    id:           int
    title:        str
    description:  Optional[str]      = None
    location:     Optional[str]      = None
    start_date:   Optional[datetime] = None
    end_date:     Optional[datetime] = None
    image_url:    Optional[str]      = None
    organizer_id: Optional[int]      = None
    created_at:   datetime

    class Config:
        orm_mode = True
