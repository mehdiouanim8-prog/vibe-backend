from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import get_db
from models import Job, User
from security import get_current_user

router = APIRouter(prefix="/jobs", tags=["Jobs"])


# ─── Schemas ──────────────────────────────────────────────────

class JobCreate(BaseModel):
    title:        str
    company:      str
    location:     Optional[str] = None
    description:  Optional[str] = None
    salary_range: Optional[str] = None
    job_type:     Optional[str] = None  # full-time, part-time, remote, internship

class JobOut(BaseModel):
    id:           int
    title:        str
    company:      str
    location:     Optional[str]  = None
    description:  Optional[str]  = None
    salary_range: Optional[str]  = None
    job_type:     Optional[str]  = None
    poster_id:    Optional[int]  = None
    created_at:   datetime
    class Config: orm_mode = True


# ─── Routes ───────────────────────────────────────────────────

@router.get("/", response_model=List[JobOut])
def list_jobs(
    search:   Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Job)
    if search:
        q = f"%{search}%"
        query = query.filter(
            or_(Job.title.ilike(q), Job.company.ilike(q), Job.description.ilike(q))
        )
    if job_type:
        query = query.filter(Job.job_type == job_type)
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    return query.order_by(Job.created_at.desc()).all()


@router.post("/", response_model=JobOut, status_code=201)
def create_job(
    data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = Job(**data.dict(), poster_id=current_user.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.poster_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(job)
    db.commit()
    return {"message": "deleted"}
