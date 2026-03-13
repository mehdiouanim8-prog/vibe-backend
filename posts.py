from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from database import get_db
from models import User, Post, Like, Comment, Follow, SavedPost, Notification
from schemas import PostCreate, PostOut, CommentCreate, CommentOut, FeedOut
from security import get_current_user
from typing import List, Optional
from datetime import datetime, timedelta

router = APIRouter(prefix="/posts", tags=["Posts"])

# ─── All Posts (Global Feed) ─────────────────────────────────
# IMPORTANT: /all must come BEFORE /{post_id}

@router.get("/all", response_model=FeedOut)
def get_all_posts(
    page:       int = Query(1, ge=1),
    per_page:   int = Query(20, le=100),
    sort:       str = Query("new"),
    time_range: str = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Post).filter(
        Post.is_deleted  == False,
        Post.is_archived == False,
    )

    now = datetime.utcnow()
    if sort == "hot" or time_range == "today":
        query = query.filter(Post.created_at >= now - timedelta(days=1))
    elif time_range == "week":
        query = query.filter(Post.created_at >= now - timedelta(weeks=1))
    elif time_range == "month":
        query = query.filter(Post.created_at >= now - timedelta(days=30))
    elif time_range == "year":
        query = query.filter(Post.created_at >= now - timedelta(days=365))

    total = query.count()

    # For hot/top we fetch all then sort by likes in Python
    if sort in ("hot", "top"):
        posts_raw = load_posts(query, current_user.id)
        posts_raw.sort(key=lambda p: p["likes_count"], reverse=True)
        start = (page - 1) * per_page
        posts = posts_raw[start: start + per_page]
    else:
        # new — sort by date in SQL
        query = query.order_by(desc(Post.created_at))
        query = query.offset((page - 1) * per_page).limit(per_page)
        posts = load_posts(query, current_user.id)

    return {"posts": posts, "total": total, "page": page, "per_page": per_page}

# ───────────────────────────────────────────────────────────────────────────

def build_author(user) -> dict:
    """Build minimal author dict from ORM User — only real DB columns."""
    if not user:
        return None
    return {
        "id":                  user.id,
        "username":            user.username,
        "full_name":           user.full_name,
        "headline":            getattr(user, "headline", None),
        "avatar_url":          user.avatar_url,
        "is_verified":         getattr(user, "is_verified", False),
        "is_verified_company": getattr(user, "is_verified_company", False),
        "is_premium":          getattr(user, "is_premium", False),
    }

def build_post(post, current_user_id: int) -> dict:
    """Build full post dict with computed fields — safe for Pydantic."""
    likes        = post.likes or []
    comments     = post.comments or []
    likes_count  = len(likes)
    comments_count = len(comments)
    user_like    = next((l for l in likes if l.user_id == current_user_id), None)
    is_liked     = user_like is not None
    user_reaction = user_like.reaction_type if user_like else None

    return {
        "id":             post.id,
        "content":        post.content,
        "image_url":      post.image_url,
        "tags":           getattr(post, "tags", None),
        "feeling":        getattr(post, "feeling", None),
        "author_id":      post.author_id,
        "community_id":   post.community_id,
        "is_archived":    getattr(post, "is_archived", False),
        "created_at":     post.created_at,
        "likes_count":    likes_count,
        "comments_count": comments_count,
        "is_liked":       is_liked,
        "user_reaction":  user_reaction,
        "author":         build_author(post.author),
    }


def load_posts(query, current_user_id: int):
    """Eagerly load relationships and build safe dicts."""
    posts = query.options(
        joinedload(Post.author),
        joinedload(Post.likes),
        joinedload(Post.comments),
    ).all()
    return [build_post(p, current_user_id) for p in posts]


# ─── Create Post ─────────────────────────────────────────────

@router.post("/", response_model=PostOut, status_code=201)
def create_post(
    data: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = Post(
        content=data.content,
        image_url=data.image_url or None,
        author_id=current_user.id,
        community_id=data.community_id,
        tags=data.tags,
        feeling=data.feeling,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    # Reload with relationships
    post = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.likes),
        joinedload(Post.comments),
    ).filter(Post.id == post.id).first()

    return build_post(post, current_user.id)

# ─── Feed (Following only) ───────────────────────────────────

@router.get("/feed", response_model=FeedOut)
def get_feed(
    page:       int = Query(1, ge=1),
    per_page:   int = Query(20, le=50),
    sort:       str = Query("new"),
    time_range: str = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    following_ids = [f.following_id for f in current_user.following]
    following_ids.append(current_user.id)

    query = db.query(Post).filter(
        Post.author_id.in_(following_ids),
        Post.is_deleted  == False,
        Post.is_archived == False,
    )

    now = datetime.utcnow()
    if sort == "hot" or time_range == "today":
        query = query.filter(Post.created_at >= now - timedelta(days=1))
    elif time_range == "week":
        query = query.filter(Post.created_at >= now - timedelta(weeks=1))
    elif time_range == "month":
        query = query.filter(Post.created_at >= now - timedelta(days=30))
    elif time_range == "year":
        query = query.filter(Post.created_at >= now - timedelta(days=365))

    total = query.count()

    if sort in ("hot", "top"):
        posts_raw = load_posts(query, current_user.id)
        posts_raw.sort(key=lambda p: p["likes_count"], reverse=True)
        start = (page - 1) * per_page
        posts = posts_raw[start: start + per_page]
    else:
        query = query.order_by(desc(Post.created_at)).offset((page - 1) * per_page).limit(per_page)
        posts = load_posts(query, current_user.id)

    return {"posts": posts, "total": total, "page": page, "per_page": per_page}


# ─── Single Post ─────────────────────────────────────────────

@router.get("/{post_id}", response_model=PostOut)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.likes),
        joinedload(Post.comments),
    ).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return build_post(post, current_user.id)


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
    # Soft delete
    post.is_deleted = True
    db.commit()


# ─── Archive Post ────────────────────────────────────────────

@router.patch("/{post_id}/archive")
def archive_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    post.is_archived = True
    db.commit()
    return {"message": "archived"}


# ─── Save Post ───────────────────────────────────────────────

@router.post("/{post_id}/save")
def save_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = db.query(SavedPost).filter(
        SavedPost.user_id == current_user.id,
        SavedPost.post_id == post_id
    ).first()
    if existing:
        return {"message": "already saved"}
    saved = SavedPost(user_id=current_user.id, post_id=post_id)
    db.add(saved)
    db.commit()
    return {"message": "saved"}


# ─── Like / React ────────────────────────────────────────────

@router.post("/{post_id}/like")
def like_post(
    post_id: int,
    reaction_type: Optional[str] = "like",
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
        if existing.reaction_type == reaction_type:
            # Same reaction → unlike
            db.delete(existing)
            db.commit()
            return {"message": "unliked"}
        else:
            # Different reaction → update
            existing.reaction_type = reaction_type
            db.commit()
            return {"message": "reaction updated", "reaction": reaction_type}

    # New like
    like = Like(user_id=current_user.id, post_id=post_id, reaction_type=reaction_type)
    db.add(like)

    # Notify post author (not self)
    if post.author_id != current_user.id:
        notif = Notification(
            user_id=post.author_id,
            type="like",
            message=f"{current_user.full_name or current_user.username} reacted to your post",
            from_user_id=current_user.id,
            post_id=post_id,
        )
        db.add(notif)

    db.commit()
    return {"message": "liked", "reaction": reaction_type}


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

    comment = Comment(
        content=data.content,
        author_id=current_user.id,
        post_id=post_id,
        parent_id=data.parent_id,
    )
    db.add(comment)

    # Notify post author
    if post.author_id != current_user.id:
        notif = Notification(
            user_id=post.author_id,
            type="comment",
            message=f"{current_user.full_name or current_user.username} commented on your post",
            from_user_id=current_user.id,
            post_id=post_id,
        )
        db.add(notif)

    db.commit()
    db.refresh(comment)

    # Return with author
    comment = db.query(Comment).options(
        joinedload(Comment.author)
    ).filter(Comment.id == comment.id).first()
    return comment


@router.get("/{post_id}/comments", response_model=List[CommentOut])
def get_comments(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    comments = db.query(Comment).options(
        joinedload(Comment.author)
    ).filter(Comment.post_id == post_id).order_by(Comment.created_at.asc()).all()
    return comments


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
