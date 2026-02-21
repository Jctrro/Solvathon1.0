"""
seed_faculty_extras.py
Run from the backend folder:
  python -m app.seed_faculty_extras

Creates the new FacultyTimetable, StudentTimetable, and Notification tables
and seeds them with the data that was previously hardcoded in faculty.html.

Safe to run multiple times — skips seeding if rows already exist.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlmodel import SQLModel, Session, select, create_engine
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

from app.models import (
    Faculty, FacultyTimetable, StudentTimetable,
    Notification, NotifType
)

def seed():
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # ── Find the first faculty member to attach timetable to ──────────────
        faculty = session.exec(select(Faculty)).first()
        if not faculty:
            print("❌  No faculty found in DB. Please create a faculty user first.")
            return

        fid = faculty.id
        print(f"✅  Using faculty: {faculty.name} (id={fid})")

        # ── Faculty Timetable ─────────────────────────────────────────────────
        existing_ft = session.exec(select(FacultyTimetable).where(FacultyTimetable.faculty_id == fid)).first()
        if not existing_ft:
            ft_rows = [
                FacultyTimetable(faculty_id=fid, day="Monday",    time_slot="9:00 – 10:00",  course_name="Data Structures",   classroom="LH-101", semester="Sem 3"),
                FacultyTimetable(faculty_id=fid, day="Monday",    time_slot="11:00 – 12:00", course_name="Machine Learning",  classroom="LH-204", semester="Sem 5"),
                FacultyTimetable(faculty_id=fid, day="Tuesday",   time_slot="10:00 – 11:00", course_name="Operating Systems", classroom="LH-102", semester="Sem 3"),
                FacultyTimetable(faculty_id=fid, day="Tuesday",   time_slot="2:00 – 3:00",   course_name="Software Engineering", classroom="LH-305", semester="Sem 5"),
                FacultyTimetable(faculty_id=fid, day="Wednesday", time_slot="9:00 – 10:00",  course_name="Computer Networks", classroom="LH-203", semester="Sem 5"),
                FacultyTimetable(faculty_id=fid, day="Wednesday", time_slot="11:00 – 12:00", course_name="Data Structures",   classroom="LH-101", semester="Sem 3"),
                FacultyTimetable(faculty_id=fid, day="Thursday",  time_slot="10:00 – 11:00", course_name="Machine Learning",  classroom="LH-204", semester="Sem 5"),
                FacultyTimetable(faculty_id=fid, day="Thursday",  time_slot="3:00 – 4:00",   course_name="Operating Systems", classroom="LH-102", semester="Sem 3"),
                FacultyTimetable(faculty_id=fid, day="Friday",    time_slot="9:00 – 10:00",  course_name="Software Engineering", classroom="LH-305", semester="Sem 5"),
                FacultyTimetable(faculty_id=fid, day="Friday",    time_slot="11:00 – 12:00", course_name="Computer Networks", classroom="LH-203", semester="Sem 5"),
            ]
            session.add_all(ft_rows)
            print(f"   → Inserted {len(ft_rows)} FacultyTimetable rows")
        else:
            print("   → FacultyTimetable already seeded, skipping")

        # ── Student Timetable ─────────────────────────────────────────────────
        existing_st = session.exec(select(StudentTimetable)).first()
        if not existing_st:
            fn = faculty.name
            st_rows = [
                # Sem 3 Section A
                StudentTimetable(semester="Sem 3", section="A", day="Monday",    time_slot="9:00–10:00",   subject="Data Structures",      faculty_name=fn, room="LH-101"),
                StudentTimetable(semester="Sem 3", section="A", day="Monday",    time_slot="10:00–11:00",  subject="Mathematics",          faculty_name="Prof. Rajan Mehta", room="LH-103"),
                StudentTimetable(semester="Sem 3", section="A", day="Tuesday",   time_slot="9:00–10:00",   subject="Physics",              faculty_name="Dr. Ananya Rao",    room="LH-205"),
                StudentTimetable(semester="Sem 3", section="A", day="Tuesday",   time_slot="11:00–12:00",  subject="Data Structures Lab",  faculty_name=fn, room="Lab-01"),
                StudentTimetable(semester="Sem 3", section="A", day="Wednesday", time_slot="10:00–11:00",  subject="Data Structures",      faculty_name=fn, room="LH-101"),
                StudentTimetable(semester="Sem 3", section="A", day="Thursday",  time_slot="9:00–10:00",   subject="Mathematics",          faculty_name="Prof. Rajan Mehta", room="LH-103"),
                StudentTimetable(semester="Sem 3", section="A", day="Friday",    time_slot="10:00–11:00",  subject="Physics Lab",          faculty_name="Dr. Ananya Rao",    room="Lab-02"),
                # Sem 3 Section B
                StudentTimetable(semester="Sem 3", section="B", day="Monday",    time_slot="11:00–12:00",  subject="Operating Systems",    faculty_name=fn, room="LH-102"),
                StudentTimetable(semester="Sem 3", section="B", day="Tuesday",   time_slot="10:00–11:00",  subject="Mathematics",          faculty_name="Prof. Rajan Mehta", room="LH-104"),
                StudentTimetable(semester="Sem 3", section="B", day="Wednesday", time_slot="9:00–10:00",   subject="Operating Systems",    faculty_name=fn, room="LH-102"),
                StudentTimetable(semester="Sem 3", section="B", day="Thursday",  time_slot="3:00–4:00",    subject="OS Lab",               faculty_name=fn, room="Lab-03"),
                # Sem 5 Section A
                StudentTimetable(semester="Sem 5", section="A", day="Monday",    time_slot="11:00–12:00",  subject="Machine Learning",     faculty_name=fn, room="LH-204"),
                StudentTimetable(semester="Sem 5", section="A", day="Tuesday",   time_slot="9:00–10:00",   subject="Cloud Computing",      faculty_name="Prof. Suresh Kumar", room="LH-301"),
                StudentTimetable(semester="Sem 5", section="A", day="Thursday",  time_slot="10:00–11:00",  subject="Machine Learning",     faculty_name=fn, room="LH-204"),
                StudentTimetable(semester="Sem 5", section="A", day="Friday",    time_slot="2:00–3:00",    subject="ML Lab",               faculty_name=fn, room="Lab-04"),
                # Sem 5 Section B
                StudentTimetable(semester="Sem 5", section="B", day="Wednesday", time_slot="11:00–12:00",  subject="Computer Networks",    faculty_name=fn, room="LH-203"),
                StudentTimetable(semester="Sem 5", section="B", day="Friday",    time_slot="11:00–12:00",  subject="Computer Networks",    faculty_name=fn, room="LH-203"),
                StudentTimetable(semester="Sem 5", section="B", day="Thursday",  time_slot="2:00–3:00",    subject="Networks Lab",         faculty_name=fn, room="Lab-05"),
                # Sem 5 Section C
                StudentTimetable(semester="Sem 5", section="C", day="Tuesday",   time_slot="2:00–3:00",    subject="Software Engineering", faculty_name=fn, room="LH-305"),
                StudentTimetable(semester="Sem 5", section="C", day="Friday",    time_slot="9:00–10:00",   subject="Software Engineering", faculty_name=fn, room="LH-305"),
            ]
            session.add_all(st_rows)
            print(f"   → Inserted {len(st_rows)} StudentTimetable rows")
        else:
            print("   → StudentTimetable already seeded, skipping")

        # ── Notifications ─────────────────────────────────────────────────────
        existing_notif = session.exec(select(Notification)).first()
        if not existing_notif:
            now = datetime.utcnow()
            notifs = [
                # HOD notices
                Notification(title="Faculty Meeting — March 2026",      message="Mandatory faculty meeting scheduled for March 3rd at 11:00 AM in Conference Room B. Attendance is compulsory.",               priority="High",   notif_type=NotifType.HOD,  sender_id=None, timestamp=datetime(2026, 2, 19, 9, 30)),
                Notification(title="Syllabus Submission Deadline",       message="Please submit the updated course syllabus for all your courses by Feb 28, 2026 to the academic office.",                     priority="Medium", notif_type=NotifType.HOD,  sender_id=None, timestamp=datetime(2026, 2, 17, 14, 0)),
                Notification(title="Workshop on AI in Education",        message="Optional workshop on integrating AI tools in classroom teaching. Feb 25, 2026, 3:00 PM, Seminar Hall.",                        priority="Low",    notif_type=NotifType.HOD,  sender_id=None, timestamp=datetime(2026, 2, 15, 10, 0)),
                # Sent by faculty
                Notification(title="DSA Assignment 3 Released",          message="Assignment 3 on AVL Trees and Red-Black Trees is now available. Submission deadline: Feb 24, 2026.",                         priority="High",   notif_type=NotifType.SENT, sender_id=fid,  timestamp=datetime(2026, 2, 18, 10, 0)),
                Notification(title="ML Mid-Term Exam Schedule",          message="Mid-term exam for CS401 is scheduled for March 5, 2026. Syllabus covers Units 1–3.",                                         priority="High",   notif_type=NotifType.SENT, sender_id=fid,  timestamp=datetime(2026, 2, 16, 9, 0)),
                Notification(title="Lab Session Postponed",              message="The OS Lab session originally scheduled for Feb 20 has been postponed to Feb 22. Same time, same room.",                      priority="Medium", notif_type=NotifType.SENT, sender_id=fid,  timestamp=datetime(2026, 2, 15, 16, 0)),
            ]
            session.add_all(notifs)
            print(f"   → Inserted {len(notifs)} Notification rows")
        else:
            print("   → Notifications already seeded, skipping")

        session.commit()
        print("\n✅  Seed complete!")

if __name__ == "__main__":
    seed()
