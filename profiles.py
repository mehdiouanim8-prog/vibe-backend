from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Experience, Education, Project
from schemas import ExperienceCreate, ExperienceOut, EducationCreate, EducationOut, ProjectCreate, ProjectOut
from security import get_current_user
from typing import List

router = APIRouter(prefix="/profile", tags=["Profile"])


# ─── Experience ──────────────────────────────────────────────

@router.post("/experience", response_model=ExperienceOut, status_code=201)
def add_experience(data: ExperienceCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    exp = Experience(**data.dict(), user_id=current_user.id)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp

@router.get("/experience", response_model=List[ExperienceOut])
def get_my_experience(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(Experience).filter(Experience.user_id == current_user.id).all()

@router.delete("/experience/{exp_id}")
def delete_experience(exp_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    exp = db.query(Experience).filter(Experience.id == exp_id, Experience.user_id == current_user.id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    db.delete(exp)
    db.commit()
    return {"message": "Deleted"}


# ─── Education ───────────────────────────────────────────────

@router.post("/education", response_model=EducationOut, status_code=201)
def add_education(data: EducationCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    edu = Education(**data.dict(), user_id=current_user.id)
    db.add(edu)
    db.commit()
    db.refresh(edu)
    return edu

@router.get("/education", response_model=List[EducationOut])
def get_my_education(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(Education).filter(Education.user_id == current_user.id).all()

@router.delete("/education/{edu_id}")
def delete_education(edu_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    edu = db.query(Education).filter(Education.id == edu_id, Education.user_id == current_user.id).first()
    if not edu:
        raise HTTPException(status_code=404, detail="Education not found")
    db.delete(edu)
    db.commit()
    return {"message": "Deleted"}


# ─── Projects ────────────────────────────────────────────────

@router.post("/projects", response_model=ProjectOut, status_code=201)
def add_project(data: ProjectCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    project = Project(**data.dict(), user_id=current_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.get("/projects", response_model=List[ProjectOut])
def get_my_projects(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(Project).filter(Project.user_id == current_user.id).all()

@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"message": "Deleted"}
