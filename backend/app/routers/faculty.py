from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlmodel import Session, select
from ..database import get_session
from ..models import (
    User, Role, Course, Enrollment, Faculty, Assignment,
    FacultyTimetable, StudentTimetable, Notification, NotifType, Student, UploadedFile, FileStatus
)
from ..auth import check_role
from ..audit import log_action
import shutil
import os

router = APIRouter(prefix="/faculty", tags=["faculty"])


@router.get("/dashboard")
async def get_faculty_dashboard(
    request: Request,
    current_user: User = Depends(check_role([Role.FACULTY, Role.ADMIN])),
    session: Session = Depends(get_session)
):
    faculty = session.exec(select(Faculty).where(Faculty.user_id == current_user.id)).first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found.")

    courses = session.exec(select(Course).where(Course.faculty_id == faculty.id)).all()

    course_data = []
    all_assignments = []
    strength_data = []
    total_students = 0

    for c in courses:
        enrollments = session.exec(select(Enrollment).where(Enrollment.course_id == c.id)).all()
        s_count = len(enrollments)
        total_students += s_count

        course_data.append({"id": c.id, "code": c.code, "name": c.name, "students_count": s_count})
        male_approx = round(s_count * 0.6)
        female_approx = s_count - male_approx
        strength_data.append({"name": c.code, "full": c.name, "total": s_count, "male": male_approx, "female": female_approx})

        assigns = session.exec(select(Assignment).where(Assignment.course_id == c.id)).all()
        for a in assigns:
            all_assignments.append({
                "id": a.id, "title": a.title, "course": c.code, "course_name": c.name,
                "date": a.due_date.strftime("%Y-%m-%d"), "time": a.due_date.strftime("%I:%M %p"),
                "description": a.description or f"Deadline for {c.name}",
                "raw_due": a.due_date.isoformat(),
            })

    ft_rows = session.exec(select(FacultyTimetable).where(FacultyTimetable.faculty_id == faculty.id)).all()
    faculty_tt = [{"day": r.day, "time": r.time_slot, "course": r.course_name, "classroom": r.classroom, "semester": r.semester} for r in ft_rows]

    st_rows = session.exec(select(StudentTimetable)).all()
    student_tt: dict = {}
    for r in st_rows:
        student_tt.setdefault(r.semester, {}).setdefault(r.section, []).append({"day": r.day, "time": r.time_slot, "subject": r.subject, "faculty": r.faculty_name, "room": r.room})

    hod_notifs = session.exec(select(Notification).where(Notification.notif_type == NotifType.HOD)).all()
    # Included sender_id is None for Admin announcements
    sent_notifs = session.exec(select(Notification).where(
        Notification.notif_type == NotifType.SENT, 
        (Notification.sender_id == faculty.id) | (Notification.sender_id == None)
    )).all()

    now = datetime.utcnow()
    def fmt_notif(n):
        return {
            "id": n.id, 
            "title": n.title, 
            "message": n.message, 
            "priority": n.priority, 
            "timestamp": n.timestamp.strftime("%Y-%m-%d %H:%M"),
            "is_new": (now - n.timestamp).total_seconds() <= 86400
        }

    log_action(session, action="VIEW_DASHBOARD", actor=current_user,
               resource=f"faculty:{faculty.id}", request=request,
               detail=f"Faculty {faculty.name} loaded dashboard")

    return {
        "success": True,
        "data": {
            "profile": {
                "id": faculty.employee_id, "name": faculty.name, "department": faculty.department,
                "email": current_user.email, "total_courses": len(courses), "total_students": total_students,
            },
            "courses": course_data,
            "strength": strength_data,
            "deadlines": all_assignments,
            "faculty_tt": faculty_tt,
            "student_tt": student_tt,
            "notifications": {"hod": [fmt_notif(n) for n in hod_notifs], "sent": [fmt_notif(n) for n in sent_notifs]},
        }
    }


@router.post("/notifications")
async def send_notification(
    request: Request,
    data: dict,
    current_user: User = Depends(check_role([Role.FACULTY, Role.ADMIN])),
    session: Session = Depends(get_session)
):
    faculty = session.exec(select(Faculty).where(Faculty.user_id == current_user.id)).first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found.")
    
    new_notif = Notification(
        title=data.get("title"),
        message=data.get("message"),
        priority=data.get("priority", "Medium"),
        notif_type=NotifType.SENT,
        sender_id=faculty.id,
        timestamp=datetime.utcnow()
    )
    session.add(new_notif)
    session.commit()
    session.refresh(new_notif)

    log_action(session, action="SEND_NOTIFICATION", actor=current_user,
               resource=f"notification:{new_notif.id}", request=request,
               detail=f"Sent '{new_notif.title}' ({new_notif.priority} priority)")
    
    return {"success": True, "message": "Notification sent successfully", "data": new_notif}


@router.post("/assignments")
async def create_assignment(
    request: Request,
    data: dict,
    current_user: User = Depends(check_role([Role.FACULTY, Role.ADMIN])),
    session: Session = Depends(get_session)
):
    faculty = session.exec(select(Faculty).where(Faculty.user_id == current_user.id)).first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found.")
    
    course_id = data.get("course_id")
    title = data.get("title")
    description = data.get("description")
    due_str = data.get("due_date")
    
    try:
        if "T" in due_str:
            due_date = datetime.fromisoformat(due_str)
        else:
            due_date = datetime.strptime(due_str, "%Y-%m-%d %H:%M")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD HH:MM")

    new_assignment = Assignment(title=title, description=description, due_date=due_date, course_id=course_id)
    session.add(new_assignment)
    
    course = session.get(Course, course_id)
    course_code = course.code if course else "Course"
    notif_msg = f"New assignment posted for {course_code}: {title}. Deadline: {due_date.strftime('%d %b, %H:%M')}. {description or ''}"
    
    new_notif = Notification(
        title=f"New Assignment: {title}", message=notif_msg,
        priority="Medium", notif_type=NotifType.SENT,
        sender_id=faculty.id, timestamp=datetime.utcnow()
    )
    session.add(new_notif)
    session.commit()

    log_action(session, action="CREATE_ASSIGNMENT", actor=current_user,
               resource=f"course:{course_id}", request=request,
               detail=f"Assignment '{title}' created for {course_code}, due {due_date}")
    
    return {"success": True, "message": "Assignment and Notification created successfully"}


@router.get("/course/{course_id}/students")
async def get_course_students(
    course_id: int,
    request: Request,
    current_user: User = Depends(check_role([Role.FACULTY, Role.ADMIN])),
    session: Session = Depends(get_session)
):
    faculty = session.exec(select(Faculty).where(Faculty.user_id == current_user.id)).first()
    course = session.get(Course, course_id)
    if not course or course.faculty_id != faculty.id:
        raise HTTPException(status_code=403, detail="Not authorized for this course")

    enrollments = session.exec(select(Enrollment).where(Enrollment.course_id == course_id)).all()
    student_list = []
    for enr in enrollments:
        student = session.get(Student, enr.student_id)
        if student:
            student_list.append({
                "id": student.id, "usn": student.usn, "name": student.name, "semester": student.semester,
                "marks": {"mse1": enr.mse1, "mse2": enr.mse2, "assignment1": enr.assignment1, "assignment2": enr.assignment2}
            })

    log_action(session, action="VIEW_COURSE_STUDENTS", actor=current_user,
               resource=f"course:{course_id}", request=request,
               detail=f"Viewed {len(student_list)} students for course {course.code}")

    return {"success": True, "data": student_list}


@router.post("/upload-file")
async def faculty_upload_file(
    request: Request,
    file: UploadFile = File(...),
    subject_code: str = Form(...),
    unit: str = Form("1"),
    semester: str = Form("6"),
    current_user: User = Depends(check_role([Role.FACULTY, Role.ADMIN])),
    session: Session = Depends(get_session)
):
    faculty = session.exec(select(Faculty).where(Faculty.user_id == current_user.id)).first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found.")

    upload_dir = os.path.join("uploads", semester, subject_code, f"unit_{unit}")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    new_up = UploadedFile(
        filename=file.filename,
        file_path=file_path,
        subject_code=subject_code,
        unit=unit,
        semester=semester,
        uploaded_by_id=current_user.id,
        uploaded_by_role=Role.FACULTY,
        status=FileStatus.APPROVED
    )
    session.add(new_up)
    session.commit()

    course = session.exec(select(Course).where(Course.code == subject_code)).first()
    if course:
        new_notif = Notification(
            title=f"New Study Material: {file.filename}",
            message=f"New notes uploaded for {subject_code} (Unit {unit}): {file.filename}. Check the repository!",
            priority="Low", notif_type=NotifType.SENT,
            sender_id=faculty.id, timestamp=datetime.utcnow()
        )
        session.add(new_notif)
        session.commit()

    log_action(session, action="UPLOAD_FILE_AUTO_APPROVED", actor=current_user,
               resource=f"file:{file.filename}", request=request,
               detail=f"Faculty uploaded '{file.filename}' (AUTO-APPROVED)")

    return {"success": True, "message": f"File '{file.filename}' uploaded and auto-approved. Students notified."}
