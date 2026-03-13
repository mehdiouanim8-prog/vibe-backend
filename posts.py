from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import get_db
from models import Post, User, Like, Comment
from security import get_current_user

router = APIRouter(prefix="/posts", tags=["Posts"])

# ─── Schemas ──────────────────────────────────────────────────

class PostCreate(BaseModel):
    content:   str
    tags:      Optional[str] = None
    feeling:   Optional[str] = None
    image_url: Optional[str] = None

class AuthorOut(BaseModel):
    id:                   int
    username:             str
    full_name:            Optional[str]  = None
    avatar_url:           Optional[str]  = None
    headline:             Optional[str]  = None
    is_verified_company:  Optional[bool] = False

    class Config: orm_mode = True

class PostOut(BaseModel):
    id:             int
    content:        str
    tags:           Optional[str]      = None
    feeling:        Optional[str]      = None
    image_url:      Optional[str]      = None
    author_id:      Optional[int]      = None
    author:         Optional[AuthorOut]= None
    likes_count:    int                = 0
    comments_count: int                = 0
    created_at:     datetime
    is_archived:    Optional[bool]     = False
    is_deleted:     Optional[bool]     = False

    class Config: orm_mode = True

class CommentCreate(BaseModel):
    content: str

class CommentOut(BaseModel):
    id:         int
    content:    str
    author_id:  Optional[int]      = None
    author:     Optional[AuthorOut]= None
    created_at: datetime

    class Config: orm_mode = True

# ─── Routes ───────────────────────────────────────────────────

@router.get("/", response_model=List[PostOut])
def list_posts(
    page:     int             = Query(1, ge=1),
    per_page: int             = Query(20, ge=1, le=100),
    db:       Session         = Depends(get_db),
    current_user: User        = Depends(get_current_user),
):
    offset = (page - 1) * per_page
    posts = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(Post.is_deleted == False)
        .filter(Post.is_archived == False)
        .order_by(desc(Post.created_at))
        .offset(offset)
        .limit(per_page)
        .all()
    )
    return posts


@router.post("/", response_model=PostOut, status_code=201)
def create_post(
    data:         PostCreate,
    db:           Session    = Depends(get_db),
    current_user: User       = Depends(get_current_user),
):
    post = Post(
        content=data.content,
        tags=data.tags,
        feeling=data.feeling,
        image_url=data.image_url,
        author_id=current_user.id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.get("/{post_id}", response_model=PostOut)
def get_post(
    post_id: int,
    db:      Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).options(joinedload(Post.author)).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.delete("/{post_id}")
def delete_post(
    post_id:      int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    post.is_deleted = True
    db.commit()
    return {"message": "deleted"}


@router.patch("/{post_id}/archive")
def archive_post(
    post_id:      int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    post.is_archived = not post.is_archived
    db.commit()
    return {"message": "archived" if post.is_archived else "unarchived"}


@router.post("/{post_id}/like")
def toggle_like(
    post_id:      int,
    reaction_type: Optional[str] = "like",
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = db.query(Like).filter(
        Like.post_id == post_id,
        Like.user_id == current_user.id,
    ).first()

    if existing:
        db.delete(existing)
        post.likes_count = max(0, (post.likes_count or 0) - 1)
        db.commit()
        return {"liked": False, "likes_count": post.likes_count}
    else:
        like = Like(post_id=post_id, user_id=current_user.id, reaction_type=reaction_type)
        db.add(like)
        post.likes_count = (post.likes_count or 0) + 1
        db.commit()
        return {"liked": True, "likes_count": post.likes_count}


@router.post("/{post_id}/save")
def save_post(
    post_id:      int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "saved"}


@router.get("/{post_id}/comments", response_model=List[CommentOut])
def get_comments(
    post_id: int,
    db:      Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comments = (
        db.query(Comment)
        .options(joinedload(Comment.author))
        .filter(Comment.post_id == post_id)
        .order_by(Comment.created_at)
        .all()
    )
    return comments


@router.post("/{post_id}/comments", response_model=CommentOut, status_code=201)
def create_comment(
    post_id:      int,
    data:         CommentCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comment = Comment(
        post_id=post_id,
        author_id=current_user.id,
        content=data.content,
    )
    db.add(comment)
    post.comments_count = (post.comments_count or 0) + 1
    db.commit()
    db.refresh(comment)
    return comment
