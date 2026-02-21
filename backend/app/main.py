from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, select
from .routers import auth, student, faculty, admin, common
from .database import engine, get_session
from .models import AuditLog
from .auth import check_role
from .models import User, Role
import os

app = FastAPI(title="University Portal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost",
        "http://127.0.0.1"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all new tables (AuditLog etc.) on startup
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

app.include_router(auth.router, prefix="/api")
app.include_router(student.router, prefix="/api")
app.include_router(faculty.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(common.router, prefix="/api")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/audit")
async def get_audit_log(
    limit: int = 50,
    current_user: User = Depends(check_role([Role.FACULTY, Role.ADMIN])),
    session = Depends(get_session)
):
    """View recent audit log entries (faculty/admin only)."""
    from sqlmodel import select as sql_select
    logs = session.exec(
        sql_select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
    ).all()
    return {
        "count": len(logs),
        "logs": [
            {
                "id": l.id,
                "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "actor": l.actor_email or "anonymous",
                "role": l.actor_role,
                "action": l.action,
                "resource": l.resource,
                "detail": l.detail,
                "ip": l.ip_address,
            }
            for l in logs
        ]
    }

# Mount user uploads securely
uploads_dir = os.path.abspath(os.path.join(os.getcwd(), "uploads"))
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Mount static frontend
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "static_frontend")
static_dir = os.path.abspath(static_dir)
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
