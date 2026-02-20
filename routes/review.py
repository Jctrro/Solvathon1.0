from fastapi import APIRouter
from database.db import get_connection

router = APIRouter()

# ==========================
# GET PENDING STUDENT NOTES
# ==========================

@router.get("/review/pending")
def get_pending():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, filename, ai_score, ai_flags
        FROM repository_files
        WHERE uploader_role='student'
        AND status='ai_reviewed'
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

# ==========================
# APPROVE NOTE
# ==========================

@router.post("/review/approve")
def approve(file_id:int):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE repository_files
        SET status='approved',
            visibility='peer'
        WHERE id=%s
    """,(file_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"message":"Approved"}

# ==========================
# REJECT NOTE
# ==========================

@router.post("/review/reject")
def reject(file_id:int):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE repository_files
        SET status='rejected'
        WHERE id=%s
    """,(file_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"message":"Rejected"}