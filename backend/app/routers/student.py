from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from ..database import get_session
from ..models import User, Role, Course, Enrollment, Assignment, Attendance, Student, Notification, NotifType, Faculty, StudentPin, UploadedFile, FileStatus
from ..auth import check_role
from ..audit import log_action
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
import shutil
import os
import requests
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/student", tags=["student"])

@router.get("/dashboard")
async def get_student_dashboard(
    request: Request,
    current_user: User = Depends(check_role([Role.STUDENT, Role.ADMIN])),
    session: Session = Depends(get_session)
):
    student = session.exec(select(Student).where(Student.user_id == current_user.id)).first()
    if not student:
        if current_user.role == Role.ADMIN:
            notifs_query = select(Notification, Faculty).outerjoin(Faculty, Notification.sender_id == Faculty.id).where(Notification.notif_type == NotifType.SENT).order_by(Notification.timestamp.desc())
            notifs_results = session.exec(notifs_query).all()
            notifications_data = []
            now = datetime.utcnow()
            for n, f in notifs_results:
                notifications_data.append({
                    "id": n.id, "title": n.title, "message": n.message, "priority": n.priority,
                    "faculty": f.name if f else "System Admin", "timestamp": n.timestamp.strftime("%d %b, %H:%M"),
                    "is_new": (now - n.timestamp).total_seconds() <= 86400
                })
            return {
                "success": True,
                "data": {
                    "profile": { "id": "ADMIN-001", "name": "Admin Tester", "branch": "Administration", "semester": 1, "avg_attendance": 100 },
                    "subjects": [], "deadlines": [], "pins": [], "notifications": notifications_data, "email": current_user.email
                }
            }
        raise HTTPException(status_code=404, detail="Student profile not found.")

    courses = session.exec(select(Course).join(Enrollment).where(Enrollment.student_id == student.id)).all()

    subjects_data = []
    total_attendance_pct = 0

    for c in courses:
        enrollment = session.exec(select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.course_id == c.id
        )).first()

        atts = session.exec(select(Attendance).where(
            Attendance.student_id == student.id,
            Attendance.course_id == c.id
        )).all()
        att_total = len(atts)
        att_present = len([a for a in atts if a.present])
        att_pct = round(att_present / att_total * 100) if att_total > 0 else 100
        total_attendance_pct += att_pct

        subjects_data.append({
            "id": c.id,
            "name": c.name,
            "code": c.code,
            "attendance": att_pct,
            "attendance_count": att_present,
            "mse1": enrollment.mse1 if enrollment else 0,
            "mse2": enrollment.mse2 if enrollment else 0,
            "assignment1": enrollment.assignment1 if enrollment else 0,
            "assignment2": enrollment.assignment2 if enrollment else 0
        })

    avg_attendance = round(total_attendance_pct / len(courses)) if courses else 100

    course_ids = [c.id for c in courses]
    all_assignments = []
    for cid in course_ids:
        c = session.get(Course, cid)
        assigns = session.exec(select(Assignment).where(Assignment.course_id == cid)).all()
        for a in assigns:
            all_assignments.append({
                "id": a.id,
                "title": a.title,
                "type": c.name,
                "due": a.due_date.strftime("%A, %d %b %Y"),
                "due_date": a.due_date.isoformat()
            })

    notifs_query = select(Notification, Faculty).outerjoin(Faculty, Notification.sender_id == Faculty.id).where(Notification.notif_type == NotifType.SENT).order_by(Notification.timestamp.desc())
    notifs_results = session.exec(notifs_query).all()
    
    notifications_data = []
    now = datetime.utcnow()
    for n, f in notifs_results:
        notifications_data.append({
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "priority": n.priority,
            "faculty": f.name if f else "System Admin",
            "timestamp": n.timestamp.strftime("%d %b, %H:%M"),
            "is_new": (now - n.timestamp).total_seconds() <= 86400
        })

    pins = session.exec(select(StudentPin).where(StudentPin.student_id == student.id)).all()
    pins_data = [{"id": p.id, "title": p.title, "description": p.description, "due_date": p.due_date.isoformat()} for p in pins]

    log_action(session, action="VIEW_DASHBOARD", actor=current_user,
               resource=f"student:{student.id}", request=request,
               detail=f"Student {student.name} loaded dashboard")

    return {
        "success": True,
        "data": {
            "profile": {
                "id": student.usn,
                "name": student.name,
                "branch": student.branch,
                "semester": student.semester,
                "avg_attendance": avg_attendance
            },
            "subjects": subjects_data,
            "deadlines": all_assignments,
            "pins": pins_data,
            "notifications": notifications_data,
            "email": current_user.email
        }
    }

@router.post("/pins")
async def create_pin(
    request: Request,
    data: dict,
    current_user: User = Depends(check_role([Role.STUDENT])),
    session: Session = Depends(get_session)
):
    student = session.exec(select(Student).where(Student.user_id == current_user.id)).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found.")
    
    title = data.get("title")
    description = data.get("description")
    date_str = data.get("due_date") 
    
    try:
        if "T" in date_str:
            due_date = datetime.fromisoformat(date_str)
        else:
            due_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
        
    new_pin = StudentPin(student_id=student.id, title=title, description=description, due_date=due_date)
    session.add(new_pin)
    session.commit()

    log_action(session, action="CREATE_PIN", actor=current_user,
               resource=f"student:{student.id}", request=request,
               detail=f"Pin created: '{title}' due {due_date}")

    return {"success": True, "message": "Personal pin added"}

@router.delete("/pins/{pin_id}")
async def delete_pin(
    pin_id: int,
    request: Request,
    current_user: User = Depends(check_role([Role.STUDENT])),
    session: Session = Depends(get_session)
):
    pin = session.get(StudentPin, pin_id)
    if not pin:
        raise HTTPException(status_code=404, detail="Pin not found")
    student = session.exec(select(Student).where(Student.user_id == current_user.id)).first()
    if pin.student_id != student.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    log_action(session, action="DELETE_PIN", actor=current_user,
               resource=f"pin:{pin_id}", request=request,
               detail=f"Deleted pin: '{pin.title}'")

    session.delete(pin)
    session.commit()
    return {"success": True}

@router.post("/upload-file")
async def student_upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(check_role([Role.STUDENT, Role.ADMIN])),
    session: Session = Depends(get_session)
):
    student = session.exec(select(Student).where(Student.user_id == current_user.id)).first()
    if not student and current_user.role == Role.STUDENT:
        raise HTTPException(status_code=404, detail="Student profile not found.")

    # 1. Save file temporarily
    temp_path = f"uploads/temp_st_{file.filename}"
    os.makedirs("uploads", exist_ok=True)
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    subject_code, semester, unit = "UNKNOWN", "6", "1"

    # 2. Automatically classify via Smart Repository
    try:
        with open(temp_path, "rb") as f_data:
            files = {"file": (file.filename, f_data, "application/octet-stream")}
            r = requests.post("http://localhost:8001/api/classify-only", files=files)
            if r.ok:
                meta = r.json()
                subject_code = meta.get("subject_code", subject_code)
                semester = str(meta.get("semester", semester))
                unit = str(meta.get("unit", unit))
    except Exception as e:
        print("Classifier failed:", e)

    # 3. Move file to auto-sorted directory
    upload_dir = os.path.join("uploads", semester, subject_code, f"unit_{unit}")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    os.replace(temp_path, file_path)

    new_up = UploadedFile(
        filename=file.filename,
        file_path=file_path,
        subject_code=subject_code,
        unit=unit,
        semester=semester,
        uploaded_by_id=current_user.id,
        uploaded_by_role=Role.STUDENT,
        status=FileStatus.PENDING
    )
    session.add(new_up)
    session.commit()

    course = session.exec(select(Course).where(Course.code == subject_code)).first()
    if course and course.faculty_id:
        new_notif = Notification(
            title=f"Pending Approval: {file.filename}",
            message=f"Student {student.name} ({student.usn}) uploaded '{file.filename}' for {subject_code}. HOD review required.",
            priority="Medium",
            notif_type=NotifType.HOD,
            sender_id=course.faculty_id,
            timestamp=datetime.utcnow()
        )
        session.add(new_notif)
        session.commit()

    log_action(session, action="UPLOAD_FILE_PENDING", actor=current_user,
               resource=f"file:{file.filename}", request=request,
               detail=f"Student uploaded '{file.filename}' (PENDING)")

    return {"success": True, "message": f"File '{file.filename}' uploaded successfully. It is now pending HOD approval."}

@router.get("/files")
async def list_files(
    subject_code: str,
    unit: str = "1",
    semester: str = "6",
    current_user: User = Depends(check_role([Role.STUDENT, Role.ADMIN, Role.FACULTY])),
    session: Session = Depends(get_session)
):
    upload_dir = os.path.join("uploads", semester, subject_code, f"unit_{unit}")
    if not os.path.exists(upload_dir):
        return {"files": []}
    
    files = []
    for filename in os.listdir(upload_dir):
        file_path = os.path.join(upload_dir, filename)
        if os.path.isfile(file_path):
            files.append({
                "id": filename,
                "filename": filename,
                "file_type": filename.split('.')[-1] if '.' in filename else 'file',
                "unit": unit,
                "semester": semester
            })
    return {"files": files}

@router.get("/download")
async def download_file(
    subject_code: str,
    filename: str,
    request: Request,
    unit: str = "1",
    semester: str = "6",
    current_user: User = Depends(check_role([Role.STUDENT, Role.ADMIN, Role.FACULTY])),
    session: Session = Depends(get_session)
):
    upload_dir = os.path.join("uploads", semester, subject_code, f"unit_{unit}")
    file_path = os.path.join(upload_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    log_action(session, action="DOWNLOAD_FILE", actor=current_user,
               resource=f"course:{subject_code}", request=request,
               detail=f"Downloaded '{filename}' from {subject_code}/unit_{unit}")

    return FileResponse(file_path, filename=filename)
