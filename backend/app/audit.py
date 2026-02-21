"""
audit.py — Central audit logging helper.

Usage (in any route):
    from ..audit import log_action
    log_action(session, action="LOGIN", actor=current_user, request=request, detail="...")
"""
from datetime import datetime
from typing import Optional
from sqlmodel import Session
from .models import AuditLog, User


def log_action(
    session: Session,
    action: str,
    actor: Optional[User] = None,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    actor_role: Optional[str] = None,
    resource: Optional[str] = None,
    detail: Optional[str] = None,
    request=None,
):
    """
    Write a row to the audit_log table. Non-blocking — any exception is swallowed
    so audit failures never break the main request.
    """
    try:
        ip = None
        if request:
            # Support X-Forwarded-For for proxies
            xff = request.headers.get("x-forwarded-for")
            ip = xff.split(",")[0].strip() if xff else (
                request.client.host if request.client else None
            )

        if actor:
            actor_id = actor_id or actor.id
            actor_email = actor_email or actor.email
            actor_role = actor_role or str(actor.role)

        entry = AuditLog(
            timestamp=datetime.utcnow(),
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role,
            action=action,
            resource=resource,
            detail=detail,
            ip_address=ip,
        )
        session.add(entry)
        session.commit()
    except Exception:
        # Never let audit failures propagate
        pass
