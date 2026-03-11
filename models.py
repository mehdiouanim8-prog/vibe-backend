from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True)
    username         = Column(String, unique=True, index=True, nullable=False)
    email            = Column(String, unique=True, index=True, nullable=False)
    hashed_password  = Column(String, nullable=False)
    full_name        = Column(String, nullable=True)
    headline         = Column(String, nullable=True)
    bio              = Column(Text, nullable=True)
    location         = Column(String, nullable=True)
    website          = Column(String, nullable=True)
    avatar_url       = Column(String, nullable=True)
    cover_url        = Column(String, nullable=True)
    is_admin         = Column(Boolean, default=False)
    is_premium       = Column(Boolean, default=False)
    is_verified      = Column(Boolean, default=False)
    is_verified_company = Column(Boolean, default=False)
    is_active        = Column(Boolean, default=True)
    is_on_hold       = Column(Boolean, default=False)
    language         = Column(String, default="English")
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    posts     = relationship("Post",    back_populates="author",  cascade="all, delete")
    likes     = relationship("Like",    back_populates="user",    cascade="all, delete")
    comments  = relationship("Comment", back_populates="author",  cascade="all, delete")
    following = relationship("Follow",  foreign_keys="Follow.follower_id",  back_populates="follower",  cascade="all, delete")
    followers = relationship("Follow",  foreign_keys="Follow.following_id", back_populates="following", cascade="all, delete")
    saved_posts = relationship("SavedPost", back_populates="user", cascade="all, delete")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete")


class Post(Base):
    __tablename__ = "posts"

    id           = Column(Integer, primary_key=True, index=True)
    content      = Column(Text, nullable=False)
    image_url    = Column(String, nullable=True)
    tags         = Column(String, nullable=True)
    feeling      = Column(String, nullable=True)
    author_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=True)
    is_archived  = Column(Boolean, default=False)
    is_deleted   = Column(Boolean, default=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())

    author    = relationship("User",    back_populates="posts")
    likes     = relationship("Like",    back_populates="post",    cascade="all, delete")
    comments  = relationship("Comment", back_populates="post",    cascade="all, delete")
    saves     = relationship("SavedPost", back_populates="post",  cascade="all, delete")


class Like(Base):
    __tablename__ = "likes"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id       = Column(Integer, ForeignKey("posts.id"), nullable=False)
    reaction_type = Column(String, default="like")
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="likes")
    post = relationship("Post", back_populates="likes")


class Comment(Base):
    __tablename__ = "comments"

    id        = Column(Integer, primary_key=True, index=True)
    content   = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id   = Column(Integer, ForeignKey("posts.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    author  = relationship("User",    back_populates="comments")
    post    = relationship("Post",    back_populates="comments")
    replies = relationship("Comment", backref="parent", remote_side=[id])


class Follow(Base):
    __tablename__ = "follows"

    id           = Column(Integer, primary_key=True, index=True)
    follower_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    following_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    follower  = relationship("User", foreign_keys=[follower_id],  back_populates="following")
    following = relationship("User", foreign_keys=[following_id], back_populates="followers")


class SavedPost(Base):
    __tablename__ = "saved_posts"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id    = Column(Integer, ForeignKey("posts.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="saved_posts")
    post = relationship("Post", back_populates="saves")


class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    type       = Column(String, nullable=False)  # like, comment, follow, mention, system
    message    = Column(Text, nullable=False)
    is_read    = Column(Boolean, default=False)
    post_id    = Column(Integer, ForeignKey("posts.id"), nullable=True)
    from_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notifications")


class Community(Base):
    __tablename__ = "communities"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    image_url   = Column(String, nullable=True)
    owner_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship("CommunityMember", back_populates="community", cascade="all, delete")


class CommunityMember(Base):
    __tablename__ = "community_members"

    id           = Column(Integer, primary_key=True, index=True)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=False)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    role         = Column(String, default="member")
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    community = relationship("Community", back_populates="members")
    user      = relationship("User")


class Event(Base):
    __tablename__ = "events"

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    location    = Column(String, nullable=True)
    start_date  = Column(DateTime(timezone=True), nullable=True)
    end_date    = Column(DateTime(timezone=True), nullable=True)
    image_url   = Column(String, nullable=True)
    organizer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id           = Column(Integer, primary_key=True, index=True)
    title        = Column(String, nullable=False)
    company      = Column(String, nullable=False)
    location     = Column(String, nullable=True)
    description  = Column(Text, nullable=True)
    salary_range = Column(String, nullable=True)
    job_type     = Column(String, nullable=True)  # full-time, part-time, remote
    poster_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id          = Column(Integer, primary_key=True, index=True)
    sender_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content     = Column(Text, nullable=False)
    is_read     = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class Experience(Base):
    __tablename__ = "experiences"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    title       = Column(String, nullable=False)
    company     = Column(String, nullable=False)
    location    = Column(String, nullable=True)
    start_date  = Column(String, nullable=True)   # e.g. "Jan 2022"
    end_date    = Column(String, nullable=True)   # e.g. "Present"
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="experiences")


class Education(Base):
    __tablename__ = "educations"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    school      = Column(String, nullable=False)
    degree      = Column(String, nullable=True)
    field       = Column(String, nullable=True)
    start_year  = Column(String, nullable=True)
    end_year    = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="educations")


class Project(Base):
    __tablename__ = "projects"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    title       = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    url         = Column(String, nullable=True)
    image_url   = Column(String, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="projects")


class Skill(Base):
    __tablename__ = "skills"

    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name    = Column(String, nullable=False)

    user = relationship("User", backref="skills")
