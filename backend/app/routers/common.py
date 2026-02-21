from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
from typing import Optional, List
from ..database import get_session
from ..models import User, Role, UploadedFile, FileStatus, Course, Faculty

router = APIRouter(prefix="/resources", tags=["resources"])

@router.get("/search")
async def search_files(
    subject_code: Optional[str] = None,
    semester: Optional[str] = None,
    faculty_name: Optional[str] = None,
    session: Session = Depends(get_session)
):
    # Only approved files are searchable
    statement = select(UploadedFile, User).join(User).where(UploadedFile.status == FileStatus.APPROVED)
    
    if subject_code:
        statement = statement.where(UploadedFile.subject_code == subject_code)
    if semester:
        # User might pass "4th Sem" or just "4"
        sem_val = semester.replace("th Sem", "").replace("st Sem", "").replace("nd Sem", "").replace("rd Sem", "").strip()
        statement = statement.where(UploadedFile.semester == sem_val)
    
    results = session.exec(statement).all()
    
    files = []
    for f, u in results:
        # Get faculty name if it was a faculty upload
        uploader_name = "Student"
        if f.uploaded_by_role == Role.FACULTY:
            fac = session.exec(select(Faculty).where(Faculty.user_id == u.id)).first()
            uploader_name = fac.name if fac else u.email
        
        # Filter by faculty name if requested
        if faculty_name and faculty_name.lower() not in uploader_name.lower():
            continue
            
        files.append({
            "id": f.id,
            "filename": f.filename,
            "subject": f.subject_code,
            "semester": f.semester,
            "unit": f.unit,
            "uploader": uploader_name,
            "uploader_role": f.uploaded_by_role,
            "timestamp": f.timestamp.isoformat()
        })
        
    return {"success": True, "data": files}

@router.get("/filters")
async def get_filter_options(session: Session = Depends(get_session)):
    subjects = session.exec(select(Course.code, Course.name)).all()
    faculties = session.exec(select(Faculty.name)).all()
    return {
        "subjects": [{"code": s[0], "name": s[1]} for s in subjects],
        "faculties": faculties,
        "semesters": ["1", "2", "3", "4", "5", "6", "7", "8"]
    }
