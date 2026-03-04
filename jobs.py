from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Job, JobApplication
from schemas import JobCreate, JobOut, JobApplicationCreate, JobApplicationOut
from security import get_current_user
from typing import List

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/", response_model=JobOut, status_code=201)
def create_job(data: JobCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not current_user.is_verified_company and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only verified companies can post jobs")
    job = Job(**data.dict(), company_id=current_user.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    job.applications_count = 0
    return job


@router.get("/", response_model=List[JobOut])
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.is_active == True).order_by(Job.created_at.desc()).all()
    for j in jobs:
        j.applications_count = len(j.applications)
    return jobs


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.applications_count = len(job.applications)
    return job


@router.post("/{job_id}/apply", response_model=JobApplicationOut, status_code=201)
def apply_to_job(job_id: int, data: JobApplicationCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id, Job.is_active == True).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or no longer active")
    existing = db.query(JobApplication).filter(
        JobApplication.job_id == job_id,
        JobApplication.applicant_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already applied to this job")
    application = JobApplication(**data.dict(), job_id=job_id, applicant_id=current_user.id)
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@router.get("/{job_id}/applications", response_model=List[JobApplicationOut])
def get_applications(job_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.company_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return job.applications


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.company_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(job)
    db.commit()
    return {"message": "Job deleted"}
