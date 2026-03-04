from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from models.models import User, Follow
from schemas.schemas import UserOut, UserUpdate
from core.security import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
def get_my_profile(current_user: User = Depends(get_current_user)):
    current_user.followers_count = len(current_user.followers)
    current_user.following_count = len(current_user.following)
    return current_user


@router.put("/me", response_model=UserOut)
def update_profile(data: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    for field, value in data.dict(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/{username}", response_model=UserOut)
def get_user_profile(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.followers_count = len(user.followers)
    user.following_count = len(user.following)
    return user


@router.post("/{username}/follow")
def follow_user(username: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target = db.query(User).filter(User.username == username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot follow yourself")

    existing = db.query(Follow).filter(Follow.follower_id == current_user.id, Follow.following_id == target.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already following this user")

    follow = Follow(follower_id=current_user.id, following_id=target.id)
    db.add(follow)
    db.commit()
    return {"message": f"You are now following {username}"}


@router.delete("/{username}/follow")
def unfollow_user(username: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target = db.query(User).filter(User.username == username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    follow = db.query(Follow).filter(Follow.follower_id == current_user.id, Follow.following_id == target.id).first()
    if not follow:
        raise HTTPException(status_code=400, detail="You are not following this user")

    db.delete(follow)
    db.commit()
    return {"message": f"You unfollowed {username}"}


@router.get("/{username}/followers", response_model=list[UserOut])
def get_followers(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return [f.follower for f in user.followers]


@router.get("/{username}/following", response_model=list[UserOut])
def get_following(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return [f.following for f in user.following]
