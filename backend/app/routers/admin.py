from datetime import datetime
import os
import requests
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select, func
from ..database import get_session
from ..models import (
    User, Role, Status, Student, Faculty, Admin, Course,
    Enrollment, Notification, NotifType, AuditLog, UploadedFile, FileStatus
)
from ..auth import check_role, get_password_hash
from ..audit import log_action
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/admin", tags=["admin"])

# --- Schemas ---

class StudentCreate(BaseModel):
    usn: str
    name: str
    semester: int
    department: str
    branch: str
    course_id: Optional[int] = None # For initial enrollment
    status: Status = Status.ACTIVE
    email: EmailStr
    password: str = "student123" # Default

class FacultyCreate(BaseModel):
    employee_id: str
    name: str
    department: str
    status: Status = Status.ACTIVE
    email: EmailStr
    password: str = "faculty123" # Default

class CourseCreate(BaseModel):
    code: str
    name: str
    credits: float
    department: str

class NotificationCreate(BaseModel):
    title: str
    message: str
    priority: str = "Medium" # High / Medium / Low

# --- Routes ---

@router.get("/dashboard")
async def get_admin_dashboard(
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    admin = session.exec(select(Admin).where(Admin.user_id == current_user.id)).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin profile not found.")

    # 1. Students in HOD's department
    dept_students_count = session.exec(
        select(func.count(Student.id)).where(Student.department == admin.department)
    ).one()

    # 2. Total students across all departments
    total_students = session.exec(select(func.count(Student.id))).one()

    # 3. Total subjects (courses)
    total_subjects = session.exec(select(func.count(Course.id))).one()

    return {
        "success": True,
        "data": {
            "department": admin.department,
            "dept_students": dept_students_count,
            "total_students": total_students,
            "total_subjects": total_subjects
        }
    }

@router.get("/students")
async def list_students(
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    # Get active students with their user details
    statement = select(Student, User).join(User).where(User.status == Status.ACTIVE)
    results = session.exec(statement).all()
    
    students_list = []
    for s, u in results:
        students_list.append({
            "id": s.id,
            "usn": s.usn,
            "name": s.name,
            "email": u.email,
            "semester": s.semester,
            "department": s.department,
            "status": u.status
        })
    return {"success": True, "data": students_list}

@router.post("/students")
async def add_student(
    request: Request,
    data: StudentCreate,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    # 1. Create User
    new_user = User(
        email=data.email,
        password_hash=get_password_hash(data.password),
        role=Role.STUDENT,
        status=data.status
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    # 2. Create Student Profile
    new_student = Student(
        usn=data.usn,
        name=data.name,
        branch=data.branch,
        semester=data.semester,
        department=data.department,
        user_id=new_user.id
    )
    session.add(new_student)
    session.commit()
    session.refresh(new_student)

    # 3. Handle initial enrollment if course_id provided
    if data.course_id:
        enrollment = Enrollment(student_id=new_student.id, course_id=data.course_id)
        session.add(enrollment)
        session.commit()

    log_action(session, action="ADMIN_ADD_STUDENT", actor=current_user, 
               resource=f"student:{new_student.id}", request=request,
               detail=f"Added student {data.name} ({data.usn}) and enrolled in course {data.course_id}")

    return {"success": True, "message": "Student added successfully"}

@router.delete("/students/{student_id}")
async def remove_student(
    student_id: int,
    request: Request,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    user = session.get(User, student.user_id)
    if user:
        user.status = Status.SUSPENDED
        session.add(user)
        session.commit()
    
    log_action(session, action="ADMIN_REMOVE_STUDENT", actor=current_user, 
               resource=f"student:{student_id}", request=request,
               detail=f"Suspended student {student.name} ({student.usn})")

    return {"success": True, "message": "Student removed successfully"}

@router.get("/faculty")
async def list_faculty(
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    statement = select(Faculty, User).join(User)
    results = session.exec(statement).all()
    
    faculty_list = []
    for f, u in results:
        faculty_list.append({
            "id": f.id,
            "employee_id": f.employee_id,
            "name": f.name,
            "email": u.email,
            "department": f.department,
            "status": u.status
        })
    return {"success": True, "data": faculty_list}

@router.post("/faculty")
async def add_faculty(
    request: Request,
    data: FacultyCreate,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    # 1. Create User
    new_user = User(
        email=data.email,
        password_hash=get_password_hash(data.password),
        role=Role.FACULTY,
        status=data.status
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    # 2. Create Faculty Profile
    new_faculty = Faculty(
        employee_id=data.employee_id,
        name=data.name,
        department=data.department,
        user_id=new_user.id
    )
    session.add(new_faculty)
    session.commit()

    log_action(session, action="ADMIN_ADD_FACULTY", actor=current_user, 
               resource=f"faculty:{new_faculty.id}", request=request,
               detail=f"Added faculty {data.name} ({data.employee_id})")

    return {"success": True, "message": "Faculty added successfully"}

@router.delete("/faculty/{faculty_id}")
async def remove_faculty(
    faculty_id: int,
    request: Request,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    faculty = session.get(Faculty, faculty_id)
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty not found")
    
    user = session.get(User, faculty.user_id)
    if user:
        user.status = Status.SUSPENDED
        session.add(user)
        session.commit()
    
    log_action(session, action="ADMIN_REMOVE_FACULTY", actor=current_user, 
               resource=f"faculty:{faculty_id}", request=request,
               detail=f"Suspended faculty {faculty.name} ({faculty.employee_id})")

    return {"success": True, "message": "Faculty removed successfully"}

@router.get("/courses")
async def list_courses(
    current_user: User = Depends(check_role([Role.ADMIN, Role.FACULTY, Role.STUDENT])),
    session: Session = Depends(get_session)
):
    courses = session.exec(select(Course)).all()
    return {"success": True, "data": courses}

@router.post("/courses")
async def add_course(
    request: Request,
    data: CourseCreate,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    new_course = Course(
        code=data.code,
        name=data.name,
        credits=data.credits,
        department=data.department
    )
    session.add(new_course)
    session.commit()

    log_action(session, action="ADMIN_ADD_COURSE", actor=current_user, 
               resource=f"course:{new_course.id}", request=request,
               detail=f"Added course {data.name} ({data.code})")

    return {"success": True, "message": "Course added successfully"}

@router.delete("/courses/{course_id}")
async def remove_course(
    course_id: int,
    request: Request,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    session.delete(course)
    session.commit()
    
    log_action(session, action="ADMIN_REMOVE_COURSE", actor=current_user, 
               resource=f"course:{course_id}", request=request,
               detail=f"Deleted course {course.name} ({course.code})")

    return {"success": True, "message": "Course removed successfully"}

@router.get("/notifications")
async def list_all_notifications(
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    # Fetch all notifications sent by anyone
    statement = select(Notification).order_by(Notification.timestamp.desc())
    results = session.exec(statement).all()
    return {"success": True, "data": results}

@router.post("/notifications")
async def admin_send_notification(
    request: Request,
    data: NotificationCreate,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    # Determine if this admin has a faculty profile to associate with
    faculty = session.exec(select(Faculty).where(Faculty.user_id == current_user.id)).first()
    sender_id = faculty.id if faculty else None

    new_notif = Notification(
        title=data.title,
        message=data.message,
        priority=data.priority,
        notif_type=NotifType.SENT,
        sender_id=sender_id,
        timestamp=datetime.utcnow()
    )
    session.add(new_notif)
    session.commit()
    session.refresh(new_notif)

    log_action(session, action="ADMIN_SEND_NOTIFICATION", actor=current_user,
               resource=f"notification:{new_notif.id}", request=request,
               detail=f"Admin sent announcement: '{data.title}'")

    return {"success": True, "message": "Announcement sent successfully", "data": new_notif}
@router.post("/push-email")
async def admin_push_email(
    request: Request,
    data: NotificationCreate,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    # 1. Fetch all student emails
    students = session.exec(select(Student)).all()
    student_emails = [s.personal_email for s in students if s.personal_email]
    
    # 2. Fetch all faculty emails
    faculties = session.exec(select(Faculty)).all()
    # Faculty records might not have personal_email yet, using user email
    faculty_user_ids = [f.user_id for f in faculties]
    faculty_users = session.exec(select(User).where(User.id.in_(faculty_user_ids))).all()
    faculty_emails = [u.email for u in faculty_users]

    all_recipients = student_emails + faculty_emails

    # 3. Simulate sending
    print(f"--- GLOBAL EMAIL PUSH ---")
    print(f"SUBJECT: [System Announcement] {data.title}")
    print(f"MESSAGE: {data.message}")
    print(f"RECIPIENTS COUNT: {len(all_recipients)}")
    for email in all_recipients[:5]: # Show first 5 for logs
        print(f"Sent to: {email}")
    if len(all_recipients) > 5:
        print(f"... and {len(all_recipients)-5} more.")
    print(f"--------------------------")

    log_action(session, action="ADMIN_EMAIL_PUSH", actor=current_user,
               detail=f"Admin pushed mail announcement '{data.title}' to {len(all_recipients)} users",
               request=request)

    return {"success": True, "message": f"Announcement pushed to {len(all_recipients)} emails successfully (simulated)."}

@router.get("/pending-accounts")
async def pending_accounts(
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    statement = select(Student, User).join(User).where(User.status == Status.PENDING)
    results = session.exec(statement).all()
    accounts = []
    for s, u in results:
        accounts.append({
            "id": u.id,
            "name": s.name,
            "usn": s.usn,
            "email": u.email,
            "department": s.department,
            "status": u.status
        })
    return {"success": True, "data": accounts}

@router.post("/accounts/{user_id}/approve")
async def approve_account(
    user_id: int,
    request: Request,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.status = Status.ACTIVE
    session.add(user)
    session.commit()
    
    log_action(session, action="ADMIN_APPROVE_ACCOUNT", actor=current_user, 
               resource=f"user:{user_id}", request=request,
               detail=f"Approved new account for {user.email}")

    return {"success": True, "message": "Account approved safely."}

@router.post("/accounts/{user_id}/deny")
async def deny_account(
    user_id: int,
    request: Request,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.status = Status.DENIED
    session.add(user)
    session.commit()
    
    log_action(session, action="ADMIN_DENY_ACCOUNT", actor=current_user, 
               resource=f"user:{user_id}", request=request,
               detail=f"Denied new account for {user.email}")

    return {"success": True, "message": "Account denied."}

@router.get("/pending-files")
async def list_pending_files(
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    statement = select(UploadedFile, User).join(User).where(UploadedFile.status == FileStatus.PENDING)
    results = session.exec(statement).all()
    files = []
    for f, u in results:
        # Convert path separators properly for URLs
        formatted_path = str(f.file_path).replace("\\", "/") if f.file_path else ""
        if formatted_path and not formatted_path.startswith("uploads/"):
            formatted_path = f"uploads/{formatted_path.split('uploads/')[-1]}" if "uploads/" in formatted_path else formatted_path
            
        files.append({
            "id": f.id,
            "filename": f.filename,
            "filepath": f"/{formatted_path}",
            "subject": f.subject_code,
            "semester": f.semester,
            "unit": f.unit,
            "uploaded_by": u.email,
            "timestamp": f.timestamp.isoformat()
        })
    return {"success": True, "data": files}

@router.post("/files/{file_id}/approve")
async def approve_file(
    file_id: int,
    request: Request,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    f = session.get(UploadedFile, file_id)
    if not f: raise HTTPException(status_code=404, detail="File not found")
    
    # Send file to Smart Repository on 8001 so it's queryable by AI
    try:
        if f.file_path and os.path.exists(f.file_path):
            with open(f.file_path, "rb") as file_data:
                # We identify as "faculty" to bypass smart repo's AI check since it's already an admin approving it.
                files = {"file": (f.filename, file_data, "application/octet-stream")}
                data_payload = {
                    "role": "faculty", 
                    "owner_id": str(f.uploaded_by_id)
                }
                r = requests.post("http://localhost:8001/api/upload", files=files, data=data_payload)
                if not r.ok:
                    logging.error(f"Failed to ingest file into RAG server: {r.text}")
    except Exception as e:
        logging.error(f"Failed RAG Repo upload: {str(e)}")

    f.status = FileStatus.APPROVED
    session.add(f)
    session.commit()
    log_action(session, action="APPROVE_FILE", actor=current_user, resource=f"file:{f.id}", detail=f"Approved {f.filename}")
    return {"success": True}

@router.post("/files/{file_id}/deny")
async def deny_file(
    file_id: int,
    request: Request,
    current_user: User = Depends(check_role([Role.ADMIN])),
    session: Session = Depends(get_session)
):
    f = session.get(UploadedFile, file_id)
    if not f: raise HTTPException(status_code=404, detail="File not found")
    f.status = FileStatus.DENIED
    session.add(f)
    session.commit()
    log_action(session, action="DENY_FILE", actor=current_user, resource=f"file:{f.id}", detail=f"Denied {f.filename}")
    return {"success": True}
