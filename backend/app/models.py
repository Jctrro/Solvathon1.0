from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class Role(str, Enum):
    STUDENT = "STUDENT"
    FACULTY = "FACULTY"
    ADMIN = "ADMIN"

class Status(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"

class FileStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"

# --- Core Auth ---

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    role: Role
    status: Status = Field(default=Status.ACTIVE)
    failed_attempts: int = Field(default=0)
    lockout_until: Optional[datetime] = None

    student_profile: Optional["Student"] = Relationship(back_populates="user")
    faculty_profile: Optional["Faculty"] = Relationship(back_populates="user")
    admin_profile: Optional["Admin"] = Relationship(back_populates="user")

    created_at: datetime = Field(default_factory=datetime.utcnow)

class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    usn: str = Field(unique=True, index=True)
    name: str
    branch: str
    semester: int
    department: str = Field(index=True) # e.g. "CSE", "ISE"
    personal_email: Optional[str] = None # For registration/notifications
    user_id: int = Field(foreign_key="user.id", unique=True)

    user: User = Relationship(back_populates="student_profile")
    enrollments: List["Enrollment"] = Relationship(back_populates="student")
    pins: List["StudentPin"] = Relationship(back_populates="student")

class Faculty(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: str = Field(unique=True, index=True)
    name: str
    department: str
    user_id: int = Field(foreign_key="user.id", unique=True)

    user: User = Relationship(back_populates="faculty_profile")
    courses: List["Course"] = Relationship(back_populates="faculty")
    timetable: List["FacultyTimetable"] = Relationship(back_populates="faculty")
    notifications: List["Notification"] = Relationship(back_populates="sender")

class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    name: str
    credits: float = Field(default=3.0)
    department: str = Field(index=True)
    faculty_id: Optional[int] = Field(default=None, foreign_key="faculty.id")

    faculty: Optional[Faculty] = Relationship(back_populates="courses")
    enrollments: List["Enrollment"] = Relationship(back_populates="course")
    assignments: List["Assignment"] = Relationship(back_populates="course")
    attendance_records: List["Attendance"] = Relationship(back_populates="course")

class Enrollment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    course_id: int = Field(foreign_key="course.id")
    
    # Marks
    mse1: Optional[float] = Field(default=0.0)
    mse2: Optional[float] = Field(default=0.0)
    assignment1: Optional[float] = Field(default=0.0)
    assignment2: Optional[float] = Field(default=0.0)

    student: Student = Relationship(back_populates="enrollments")
    course: Course = Relationship(back_populates="enrollments")

class Assignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    due_date: datetime
    course_id: int = Field(foreign_key="course.id")

    course: Course = Relationship(back_populates="assignments")

class Attendance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime
    present: bool
    student_id: int = Field(foreign_key="student.id")
    course_id: int = Field(foreign_key="course.id")

    course: Course = Relationship(back_populates="attendance_records")

# ── NEW: Faculty Timetable ──────────────────────────────────────────────────

class FacultyTimetable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    faculty_id: int = Field(foreign_key="faculty.id")
    day: str           # Monday, Tuesday …
    time_slot: str     # e.g. "9:00 – 10:00"
    course_name: str   # display name on timetable
    classroom: str
    semester: str      # Sem 3, Sem 5 …

    faculty: Optional[Faculty] = Relationship(back_populates="timetable")

# ── NEW: Student Timetable ─────────────────────────────────────────────────

class StudentTimetable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    semester: str       # "Sem 3"
    section: str        # "A"
    day: str
    time_slot: str
    subject: str
    faculty_name: str
    room: str

# ── NEW: Notifications ────────────────────────────────────────────────────

class NotifType(str, Enum):
    HOD = "HOD"
    SENT = "SENT"

class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    message: str
    priority: str          # High / Medium / Low
    notif_type: NotifType  # HOD / SENT
    sender_id: Optional[int] = Field(default=None, foreign_key="faculty.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    sender: Optional[Faculty] = Relationship(back_populates="notifications")

class StudentPin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    title: str
    description: Optional[str] = None
    due_date: datetime
    
    student: Optional[Student] = Relationship(back_populates="pins")

class Admin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    department: str
    user_id: int = Field(foreign_key="user.id", unique=True)

    user: User = Relationship(back_populates="admin_profile")

# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor_id: Optional[int] = None          # user.id who triggered the action
    actor_email: Optional[str] = None       # human-readable identity
    actor_role: Optional[str] = None        # STUDENT / FACULTY / ADMIN / SYSTEM
    action: str                             # e.g. LOGIN, UPLOAD_FILE, SEND_NOTIF
    resource: Optional[str] = None          # e.g. "file:42", "course:3"
    detail: Optional[str] = None            # free-text description
    ip_address: Optional[str] = None        # request IP

class UploadedFile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_path: str
    subject_code: str
    unit: str
    semester: str
    uploaded_by_id: int = Field(foreign_key="user.id")
    uploaded_by_role: Role
    status: FileStatus = Field(default=FileStatus.PENDING)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
