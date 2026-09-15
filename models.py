from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id                = Column(Integer, primary_key=True, index=True)
    username          = Column(String, unique=True, index=True, nullable=True)
    email             = Column(String, unique=True, index=True, nullable=True)
    hashed_password   = Column(String, nullable=True)
    full_name         = Column(String, nullable=True)
    headline          = Column(String, nullable=True)
    bio               = Column(Text, nullable=True)
    location          = Column(String, nullable=True)
    website           = Column(String, nullable=True)
    avatar_url        = Column(String, nullable=True)
    cover_url         = Column(String, nullable=True)
    is_admin          = Column(Boolean, default=False)
    is_premium        = Column(Boolean, default=False)
    is_verified       = Column(Boolean, default=False)
    profile_completed = Column(Boolean, default=False)

    # Verification / security state
    phone_number = Column(String(32), nullable=True)
    phone_verified = Column(Boolean, default=False, nullable=False)

    phone_verification_attempts = Column(
        Integer,
        default=0,
        nullable=False,
    )

    phone_verification_locked_until = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    phone_verification_last_sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    phone_verification_channel = Column(
        String(16),
        nullable=True,
    )

    email_verified = Column(Boolean, default=False, nullable=False)

    account_status = Column(String(32), default="pending", nullable=False)

    email_verification_code_hash = Column(String(128), nullable=True)
    email_verification_expires_at = Column(DateTime, nullable=True)
    email_verification_attempts = Column(Integer, default=0, nullable=False)

    identity_status = Column(
    String(32),
    default="not_started",
    nullable=False,
    )
    identity_submitted_at = Column(DateTime, nullable=True)
    identity_reviewed_at = Column(DateTime, nullable=True)

    liveness_status = Column(
    String(32),
    default="not_started",
    nullable=False,
    )
    liveness_submitted_at = Column(DateTime, nullable=True)
    liveness_reviewed_at = Column(DateTime, nullable=True)

    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    totp_secret_encrypted = Column(String(512), nullable=True)

    passkey_enabled = Column(Boolean, default=False, nullable=False)
    is_verified_company = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_on_hold = Column(Boolean, default=False)
    language = Column(String, default="English")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    posts = relationship(
    "Post",
    back_populates="author",
    cascade="all, delete"
    )

    likes = relationship(
    "Like",
    back_populates="user",
    cascade="all, delete"
    )

    comments = relationship(
    "Comment",
    back_populates="author",
    cascade="all, delete"
    )

    following = relationship(
    "Follow",
    foreign_keys="Follow.follower_id",
    back_populates="follower",
    cascade="all, delete"
    )

    followers = relationship(
    "Follow",
    foreign_keys="Follow.following_id",
    back_populates="following",
    cascade="all, delete"
    )

    saved_posts = relationship(
    "SavedPost",
    back_populates="user",
    cascade="all, delete"
    )

    notifications = relationship(
    "Notification",
    back_populates="user",
    cascade="all, delete"
    )

class KYCVerification(Base):
    __tablename__ = "kyc_verifications"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
    Integer,
    ForeignKey("users.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
    )

    # Verification attempt number
    attempt_number = Column(Integer, nullable=False, default=1)

    # Overall manual-review state
    review_status = Column(
    String(32),
    nullable=False,
    default="not_started",
    )

    # Identity verification state
    identity_status = Column(
    String(32),
    nullable=False,
    default="not_started",
    )

    # Liveness state
    liveness_status = Column(
    String(32),
    nullable=False,
    default="not_started",
    )

    # Technical checks
    document_quality_status = Column(
    String(32),
    nullable=False,
    default="not_started",
    )

    ocr_status = Column(
    String(32),
    nullable=False,
    default="not_started",
    )

    face_match_status = Column(
    String(32),
    nullable=False,
    default="not_started",
    )

    liveness_check_status = Column(
    String(32),
    nullable=False,
    default="not_started",
    )

    # Secure storage references.
    # These are REFERENCES/KEYS, not the actual document bytes.
    document_front_storage_key = Column(
    String(512),
    nullable=True,
    )

    document_back_storage_key = Column(
    String(512),
    nullable=True,
    )

    liveness_storage_key = Column(
    String(512),
    nullable=True,
    )

    # Review information
    reviewer_id = Column(
    Integer,
    nullable=True,
    index=True,
    )

    rejection_code = Column(
    String(64),
    nullable=True,
    )

    reviewer_note = Column(
    Text,
    nullable=True,
    )

    submitted_at = Column(
    DateTime,
    nullable=True,
    )

    reviewed_at = Column(
    DateTime,
    nullable=True,
    )

    created_at = Column(
    DateTime,
    default=datetime.utcnow,
    nullable=False,
    )

    updated_at = Column(
    DateTime,
    default=datetime.utcnow,
    onupdate=datetime.utcnow,
    nullable=False,
    )

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    tags = Column(String, nullable=True)
    feeling = Column(String, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=True)
    is_archived = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    author = relationship("User", back_populates="posts")
    likes = relationship("Like", back_populates="post", cascade="all, delete")
    comments = relationship("Comment", back_populates="post", cascade="all, delete")
    saves = relationship("SavedPost", back_populates="post", cascade="all, delete")

class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    reaction_type = Column(String, default="like")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="likes")
    post = relationship("Post", back_populates="likes")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    author = relationship("User", back_populates="comments")
    post = relationship("Post", back_populates="comments")
    replies = relationship(
    "Comment",
    backref="parent",
    remote_side=[id]
    )

class Follow(Base):
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    following_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    follower = relationship(
    "User",
    foreign_keys=[follower_id],
    back_populates="following"
    )

    following = relationship(
    "User",
    foreign_keys=[following_id],
    back_populates="followers"
    )

class SavedPost(Base):
    __tablename__ = "saved_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="saved_posts")
    post = relationship("Post", back_populates="saves")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)  # like, comment, follow, mention, system
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    from_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notifications")

class Community(Base):
    __tablename__ = "communities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship(
    "CommunityMember",
    back_populates="community",
    cascade="all, delete"
    )

class CommunityMember(Base):
    __tablename__ = "community_members"

    id = Column(Integer, primary_key=True, index=True)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, default="member")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    community = relationship("Community", back_populates="members")
    user = relationship("User")

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    image_url = Column(String, nullable=True)
    organizer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    salary_range = Column(String, nullable=True)
    job_type = Column(String, nullable=True)  # full-time, part-time, remote
    poster_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Experience(Base):
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    start_date = Column(String, nullable=True)   # e.g. "Jan 2022"
    end_date = Column(String, nullable=True)   # e.g. "Present"
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="experiences")

class Education(Base):
    __tablename__ = "educations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    school = Column(String, nullable=False)
    degree = Column(String, nullable=True)
    field = Column(String, nullable=True)
    start_year = Column(String, nullable=True)
    end_year = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="educations")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="projects")

class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)

    user = relationship("User", backref="skills")
