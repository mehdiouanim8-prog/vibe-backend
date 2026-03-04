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
    full_name: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    headline: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    cover_url: Optional[str]
    location: Optional[str]
    website: Optional[str]
    is_admin: bool = False
    is_verified_company: bool = False
    plan: str = "free"
    created_at: datetime
    followers_count: Optional[int] = 0
    following_count: Optional[int] = 0
    class Config:
        orm_mode = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None


# ─── Profile Sections ─────────────────────────────────────────

class ExperienceCreate(BaseModel):
    title: str
    company: str
    location: Optional[str] = ""
    start_date: str
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = ""

class ExperienceOut(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str]
    start_date: str
    end_date: Optional[str]
    is_current: bool
    description: Optional[str]
    created_at: datetime
    class Config:
        orm_mode = True

class EducationCreate(BaseModel):
    school: str
    degree: str
    field: Optional[str] = ""
    start_date: str
    end_date: Optional[str] = None
    description: Optional[str] = ""

class EducationOut(BaseModel):
    id: int
    school: str
    degree: str
    field: Optional[str]
    start_date: str
    end_date: Optional[str]
    description: Optional[str]
    created_at: datetime
    class Config:
        orm_mode = True

class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    url: Optional[str] = ""
    image_url: Optional[str] = ""

class ProjectOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    url: Optional[str]
    image_url: Optional[str]
    created_at: datetime
    class Config:
        orm_mode = True


# ─── Posts ───────────────────────────────────────────────────

class PostCreate(BaseModel):
    content: str
    image_url: Optional[str] = None
    community_id: Optional[int] = None

class PostOut(BaseModel):
    id: int
    content: str
    image_url: Optional[str]
    author_id: int
    author: UserOut
    community_id: Optional[int]
    created_at: datetime
    likes_count: Optional[int] = 0
    comments_count: Optional[int] = 0
    class Config:
        orm_mode = True

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

class FeedOut(BaseModel):
    posts: List[PostOut]
    total: int
    page: int
    per_page: int


# ─── Communities ─────────────────────────────────────────────

class CommunityCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = ""
    avatar_url: Optional[str] = ""
    cover_url: Optional[str] = ""
    is_private: bool = False

class CommunityOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    avatar_url: Optional[str]
    cover_url: Optional[str]
    is_private: bool
    created_at: datetime
    members_count: Optional[int] = 0
    class Config:
        orm_mode = True


# ─── Events ──────────────────────────────────────────────────

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    cover_url: Optional[str] = ""
    location: Optional[str] = ""
    is_online: bool = False
    online_url: Optional[str] = ""
    start_date: datetime
    end_date: datetime
    max_attendees: Optional[int] = None
    community_id: Optional[int] = None

class EventOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    cover_url: Optional[str]
    location: Optional[str]
    is_online: bool
    online_url: Optional[str]
    start_date: datetime
    end_date: datetime
    status: str
    max_attendees: Optional[int]
    created_by: int
    community_id: Optional[int]
    created_at: datetime
    attendees_count: Optional[int] = 0
    class Config:
        orm_mode = True


# ─── Jobs ────────────────────────────────────────────────────

class JobCreate(BaseModel):
    title: str
    description: str
    requirements: Optional[str] = ""
    location: Optional[str] = ""
    is_remote: bool = False
    job_type: str = "full_time"
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "USD"

class JobOut(BaseModel):
    id: int
    title: str
    description: str
    requirements: Optional[str]
    location: Optional[str]
    is_remote: bool
    job_type: str
    salary_min: Optional[float]
    salary_max: Optional[float]
    salary_currency: str
    company_id: int
    is_active: bool
    created_at: datetime
    applications_count: Optional[int] = 0
    class Config:
        orm_mode = True

class JobApplicationCreate(BaseModel):
    cover_letter: Optional[str] = ""
    resume_url: Optional[str] = ""

class JobApplicationOut(BaseModel):
    id: int
    job_id: int
    applicant_id: int
    cover_letter: Optional[str]
    resume_url: Optional[str]
    status: str
    created_at: datetime
    class Config:
        orm_mode = True


# ─── Messages ────────────────────────────────────────────────

class MessageCreate(BaseModel):
    content: str
    receiver_id: Optional[int] = None
    group_id: Optional[int] = None

class MessageOut(BaseModel):
    id: int
    sender_id: int
    receiver_id: Optional[int]
    group_id: Optional[int]
    content: str
    is_read: bool
    created_at: datetime
    class Config:
        orm_mode = True

class GroupCreate(BaseModel):
    name: str
    avatar_url: Optional[str] = ""
    member_ids: List[int] = []

class GroupOut(BaseModel):
    id: int
    name: str
    avatar_url: Optional[str]
    created_at: datetime
    members_count: Optional[int] = 0
    class Config:
        orm_mode = True


# ─── Admin ───────────────────────────────────────────────────

class AdminUserUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_verified_company: Optional[bool] = None
    plan: Optional[str] = None
