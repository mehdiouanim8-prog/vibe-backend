from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
from models import User, Post, Like, Comment, Follow
from schemas import PostCreate, PostOut, CommentCreate, CommentOut, FeedOut
from security import get_current_user
from typing import List
from datetime import datetime, timedelta

router = APIRouter(prefix="/posts", tags=["Posts"])

# ─── Create Post ─────────────────────────────────────────────

@router.post("/", response_model=PostOut, status_code=201)
def create_post(
    data: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = Post(
        content=data.content,
        image_url=data.image_url or "",
        author_id=current_user.id,
        community_id=data.community_id,
        tags=data.tags,
        feeling=data.feeling,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    post.likes_count = 0
    post.comments_count = 0
    post.is_liked = False
    post.user_reaction = None
    return post

# ─── Get All Posts (Global Feed) ─────────────────────────────
# sort: "new" | "hot" | "top"
# time_range: "today" | "week" | "month" | "year" | "all"

@router.get("/all", response_model=FeedOut)
def get_all_posts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, le=100),
    sort: str = Query("new"),
    time_range: str = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Post)

    # Apply time range filter
    now = datetime.utcnow()
    if time_range == "today":
        query = query.filter(Post.created_at >= now - timedelta(days=1))
    elif time_range == "week":
        query = query.filter(Post.created_at >= now - timedelta(weeks=1))
    elif time_range == "month":
        query = query.filter(Post.created_at >= now - timedelta(days=30))
    elif time_range == "year":
        query = query.filter(Post.created_at >= now - timedelta(days=365))
    # "all" = no filter

    # For "hot": only last 24h
    if sort == "hot":
        query = query.filter(Post.created_at >= now - timedelta(days=1))

    total = query.count()

    # Always fetch enough to sort by likes if needed
    fetch_limit = per_page * page if sort in ("hot", "top") else per_page
    fetch_offset = 0 if sort in ("hot", "top") else (page - 1) * per_page

    posts = (
        query
        .order_by(desc(Post.created_at))
        .offset(fetch_offset)
        .limit(fetch_limit)
        .all()
    )

    # Compute counts and user reaction
    for post in posts:
        post.likes_count = len(post.likes)
        post.comments_count = len(post.comments)
        post.is_liked = any(like.user_id == current_user.id for like in post.likes)
        post.user_reaction = next(
            (like.reaction_type for like in post.likes if like.user_id == current_user.id),
            None
        )

    # Sort by engagement for hot/top
    if sort in ("hot", "top"):
        posts.sort(key=lambda p: (p.likes_count + p.comments_count), reverse=True)
        # Paginate after sorting
        start = (page - 1) * per_page
        posts = posts[start: start + per_page]

    return {"posts": posts, "total": total, "page": page, "per_page": per_page}

# ─── Get Feed (Following only) ───────────────────────────────

@router.get("/feed", response_model=FeedOut)
def get_feed(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, le=50),
    sort: str = Query("new"),
    time_range: str = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    following_ids = [f.following_id for f in current_user.following]
    following_ids.append(current_user.id)

    query = db.query(Post).filter(Post.author_id.in_(following_ids))

    now = datetime.utcnow()
    if time_range == "today":
        query = query.filter(Post.created_at >= now - timedelta(days=1))
    elif time_range == "week":
        query = query.filter(Post.created_at >= now - timedelta(weeks=1))
    elif time_range == "month":
        query = query.filter(Post.created_at >= now - timedelta(days=30))
    elif time_range == "year":
        query = query.filter(Post.created_at >= now - timedelta(days=365))
    if sort == "hot":
        query = query.filter(Post.created_at >= now - timedelta(days=1))

    total = query.count()
    posts = (
        query
        .order_by(desc(Post.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    for post in posts:
        post.likes_count = len(post.likes)
        post.comments_count = len(post.comments)
        post.is_liked = any(like.user_id == current_user.id for like in post.likes)
        post.user_reaction = next(
            (like.reaction_type for like in post.likes if like.user_id == current_user.id),
            None
        )
    if sort in ("hot", "top"):
        posts.sort(key=lambda p: (p.likes_count + p.comments_count), reverse=True)

    return {"posts": posts, "total": total, "page": page, "per_page": per_page}

# ─── Get Single Post ─────────────────────────────────────────

@router.get("/{post_id}", response_model=PostOut)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.likes_count = len(post.likes)
    post.comments_count = len(post.comments)
    post.is_liked = any(like.user_id == current_user.id for like in post.likes)
    post.user_reaction = next(
        (like.reaction_type for like in post.likes if like.user_id == current_user.id),
        None
    )
    return post

# ─── Delete Post ─────────────────────────────────────────────

@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(post)
    db.commit()

# ─── Like / React ────────────────────────────────────────────

@router.post("/{post_id}/like")
def like_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.post_id == post_id
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"message": "unliked"}
    like = Like(user_id=current_user.id, post_id=post_id, reaction_type="like")
    db.add(like)
    db.commit()
    return {"message": "liked"}

# ─── Comments ────────────────────────────────────────────────

@router.post("/{post_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    post_id: int,
    data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    comment = Comment(content=data.content, author_id=current_user.id, post_id=post_id)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment

@router.get("/{post_id}/comments", response_model=List[CommentOut])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post.comments

@router.delete("/{post_id}/comments/{comment_id}", status_code=204)
def delete_comment(
    post_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comment = db.query(Comment).filter(
        Comment.id == comment_id,
        Comment.post_id == post_id
    ).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(comment)
    db.commit()
