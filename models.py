from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


# ─── Enums ───────────────────────────────────────────────────

class PlanEnum(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"

class MemberRoleEnum(str, enum.Enum):
    member = "member"
    moderator = "moderator"
    admin = "admin"

class EventStatusEnum(str, enum.Enum):
    upcoming = "upcoming"
    ongoing = "ongoing"
    completed = "completed"
    cancelled = "cancelled"

class JobTypeEnum(str, enum.Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    remote = "remote"


# ─── User ────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    headline = Column(String(200), default="")
    bio = Column(Text, default="")
    avatar_url = Column(String(500), default="")
    cover_url = Column(String(500), default="")
    location = Column(String(100), default="")
    website = Column(String(255), default="")
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_verified_company = Column(Boolean, default=False)
    plan = Column(Enum(PlanEnum), default=PlanEnum.free)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    posts = relationship("Post", back_populates="author", cascade="all, delete")
    comments = relationship("Comment", back_populates="author", cascade="all, delete")
    likes = relationship("Like", back_populates="user", cascade="all, delete")
    following = relationship("Follow", foreign_keys="Follow.follower_id", back_populates="follower", cascade="all, delete")
    followers = relationship("Follow", foreign_keys="Follow.following_id", back_populates="following", cascade="all, delete")
    experiences = relationship("Experience", back_populates="user", cascade="all, delete")
    educations = relationship("Education", back_populates="user", cascade="all, delete")
    projects = relationship("Project", back_populates="user", cascade="all, delete")
    community_memberships = relationship("CommunityMember", back_populates="user", cascade="all, delete")
    event_rsvps = relationship("EventRSVP", back_populates="user", cascade="all, delete")
    job_applications = relationship("JobApplication", back_populates="applicant", cascade="all, delete")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender", cascade="all, delete")
    group_memberships = relationship("GroupMember", back_populates="user", cascade="all, delete")


# ─── Profile Sections ─────────────────────────────────────────

class Experience(Base):
    __tablename__ = "experiences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    company = Column(String(200), nullable=False)
    location = Column(String(100), default="")
    start_date = Column(String(20), nullable=False)
    end_date = Column(String(20), nullable=True)
    is_current = Column(Boolean, default=False)
    description = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="experiences")

class Education(Base):
    __tablename__ = "educations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    school = Column(String(200), nullable=False)
    degree = Column(String(200), nullable=False)
    field = Column(String(200), default="")
    start_date = Column(String(20), nullable=False)
    end_date = Column(String(20), nullable=True)
    description = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="educations")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    url = Column(String(500), default="")
    image_url = Column(String(500), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="projects")


# ─── Posts ───────────────────────────────────────────────────

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    image_url = Column(String(500), default="")
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    community_id = Column(Integer, ForeignKey("communities.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete")
    likes = relationship("Like", back_populates="post", cascade="all, delete")
    community = relationship("Community", back_populates="posts")

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    author = relationship("User", back_populates="comments")
    post = relationship("Post", back_populates="comments")

class Like(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="likes")
    post = relationship("Post", back_populates="likes")

class Follow(Base):
    __tablename__ = "follows"
    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    following_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    following = relationship("User", foreign_keys=[following_id], back_populates="followers")


# ─── Communities ─────────────────────────────────────────────

class Community(Base):
    __tablename__ = "communities"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text, default="")
    avatar_url = Column(String(500), default="")
    cover_url = Column(String(500), default="")
    is_private = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    members = relationship("CommunityMember", back_populates="community", cascade="all, delete")
    posts = relationship("Post", back_populates="community")

class CommunityMember(Base):
    __tablename__ = "community_members"
    id = Column(Integer, primary_key=True, index=True)
    community_id = Column(Integer, ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(MemberRoleEnum), default=MemberRoleEnum.member)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    community = relationship("Community", back_populates="members")
    user = relationship("User", back_populates="community_memberships")


# ─── Events ──────────────────────────────────────────────────

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    cover_url = Column(String(500), default="")
    location = Column(String(300), default="")
    is_online = Column(Boolean, default=False)
    online_url = Column(String(500), default="")
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(EventStatusEnum), default=EventStatusEnum.upcoming)
    max_attendees = Column(Integer, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    community_id = Column(Integer, ForeignKey("communities.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    rsvps = relationship("EventRSVP", back_populates="event", cascade="all, delete")

class EventRSVP(Base):
    __tablename__ = "event_rsvps"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    event = relationship("Event", back_populates="rsvps")
    user = relationship("User", back_populates="event_rsvps")


# ─── Jobs ────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    requirements = Column(Text, default="")
    location = Column(String(200), default="")
    is_remote = Column(Boolean, default=False)
    job_type = Column(Enum(JobTypeEnum), default=JobTypeEnum.full_time)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_currency = Column(String(10), default="USD")
    company_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    company = relationship("User")
    applications = relationship("JobApplication", back_populates="job", cascade="all, delete")

class JobApplication(Base):
    __tablename__ = "job_applications"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    applicant_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cover_letter = Column(Text, default="")
    resume_url = Column(String(500), default="")
    status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    job = relationship("Job", back_populates="applications")
    applicant = relationship("User", back_populates="job_applications")


# ─── Messages ────────────────────────────────────────────────

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    avatar_url = Column(String(500), default="")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    members = relationship("GroupMember", back_populates="group", cascade="all, delete")
    messages = relationship("Message", back_populates="group", cascade="all, delete")

class GroupMember(Base):
    __tablename__ = "group_members"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="group_memberships")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    group = relationship("Group", back_populates="messages")
