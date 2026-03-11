from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models import User, Experience, Education, Project, Skill
from security import get_current_user

router = APIRouter(prefix="/profiles", tags=["Profiles"])


# ─── Schemas ──────────────────────────────────────────────────

class ExperienceCreate(BaseModel):
    title:       str
    company:     str
    location:    Optional[str] = None
    start_date:  Optional[str] = None
    end_date:    Optional[str] = None
    description: Optional[str] = None

class ExperienceOut(ExperienceCreate):
    id:      int
    user_id: int
    class Config: orm_mode = True


class EducationCreate(BaseModel):
    school:     str
    degree:     Optional[str] = None
    field:      Optional[str] = None
    start_year: Optional[str] = None
    end_year:   Optional[str] = None
    description:Optional[str] = None

class EducationOut(EducationCreate):
    id:      int
    user_id: int
    class Config: orm_mode = True


class ProjectCreate(BaseModel):
    title:       str
    description: Optional[str] = None
    url:         Optional[str] = None
    image_url:   Optional[str] = None

class ProjectOut(ProjectCreate):
    id:      int
    user_id: int
    class Config: orm_mode = True


class SkillCreate(BaseModel):
    name: str

class SkillOut(SkillCreate):
    id:      int
    user_id: int
    class Config: orm_mode = True


# ─── Experience ───────────────────────────────────────────────

@router.get("/me/experience", response_model=List[ExperienceOut])
def get_my_experience(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Experience).filter(Experience.user_id == current_user.id).all()

@router.post("/me/experience", response_model=ExperienceOut)
def add_experience(data: ExperienceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exp = Experience(**data.dict(), user_id=current_user.id)
    db.add(exp); db.commit(); db.refresh(exp)
    return exp

@router.patch("/me/experience/{exp_id}", response_model=ExperienceOut)
def update_experience(exp_id: int, data: ExperienceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exp = db.query(Experience).filter(Experience.id == exp_id, Experience.user_id == current_user.id).first()
    if not exp: raise HTTPException(404, "Not found")
    for k, v in data.dict(exclude_unset=True).items(): setattr(exp, k, v)
    db.commit(); db.refresh(exp)
    return exp

@router.delete("/me/experience/{exp_id}")
def delete_experience(exp_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exp = db.query(Experience).filter(Experience.id == exp_id, Experience.user_id == current_user.id).first()
    if not exp: raise HTTPException(404, "Not found")
    db.delete(exp); db.commit()
    return {"message": "deleted"}


# ─── Education ────────────────────────────────────────────────

@router.get("/me/education", response_model=List[EducationOut])
def get_my_education(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Education).filter(Education.user_id == current_user.id).all()

@router.post("/me/education", response_model=EducationOut)
def add_education(data: EducationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    edu = Education(**data.dict(), user_id=current_user.id)
    db.add(edu); db.commit(); db.refresh(edu)
    return edu

@router.patch("/me/education/{edu_id}", response_model=EducationOut)
def update_education(edu_id: int, data: EducationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    edu = db.query(Education).filter(Education.id == edu_id, Education.user_id == current_user.id).first()
    if not edu: raise HTTPException(404, "Not found")
    for k, v in data.dict(exclude_unset=True).items(): setattr(edu, k, v)
    db.commit(); db.refresh(edu)
    return edu

@router.delete("/me/education/{edu_id}")
def delete_education(edu_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    edu = db.query(Education).filter(Education.id == edu_id, Education.user_id == current_user.id).first()
    if not edu: raise HTTPException(404, "Not found")
    db.delete(edu); db.commit()
    return {"message": "deleted"}


# ─── Projects ─────────────────────────────────────────────────

@router.get("/me/projects", response_model=List[ProjectOut])
def get_my_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Project).filter(Project.user_id == current_user.id).all()

@router.post("/me/projects", response_model=ProjectOut)
def add_project(data: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    proj = Project(**data.dict(), user_id=current_user.id)
    db.add(proj); db.commit(); db.refresh(proj)
    return proj

@router.delete("/me/projects/{proj_id}")
def delete_project(proj_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    proj = db.query(Project).filter(Project.id == proj_id, Project.user_id == current_user.id).first()
    if not proj: raise HTTPException(404, "Not found")
    db.delete(proj); db.commit()
    return {"message": "deleted"}


# ─── Skills ───────────────────────────────────────────────────

@router.get("/me/skills", response_model=List[SkillOut])
def get_my_skills(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Skill).filter(Skill.user_id == current_user.id).all()

@router.post("/me/skills", response_model=SkillOut)
def add_skill(data: SkillCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    skill = Skill(**data.dict(), user_id=current_user.id)
    db.add(skill); db.commit(); db.refresh(skill)
    return skill

@router.delete("/me/skills/{skill_id}")
def delete_skill(skill_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.user_id == current_user.id).first()
    if not skill: raise HTTPException(404, "Not found")
    db.delete(skill); db.commit()
    return {"message": "deleted"}


# ─── Public profile by user ID ────────────────────────────────

@router.get("/{user_id}")
def get_public_profile(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    return {
        "experience": db.query(Experience).filter(Experience.user_id == user_id).all(),
        "education":  db.query(Education).filter(Education.user_id == user_id).all(),
        "projects":   db.query(Project).filter(Project.user_id == user_id).all(),
        "skills":     db.query(Skill).filter(Skill.user_id == user_id).all(),
    }
