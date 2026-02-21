from fastapi import APIRouter, Query
from database.db import get_connection
from typing import Optional

router = APIRouter()

@router.get("/files/list")
async def list_files(subject_code: str, unit: Optional[str] = None):
    conn = get_connection_repo()
    cur = conn.cursor()
    
    query = """
        SELECT id, filename, file_type, unit, semester
        FROM repository_files
        WHERE subject_code = %s
    """
    params = [subject_code]
    
    if unit:
        query += " AND unit = %s"
        params.append(unit)
        
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    
    cur.close()
    conn.close()
    
    files = []
    for r in rows:
        files.append({
            "id": r[0],
            "filename": r[1],
            "file_type": r[2],
            "unit": r[3],
            "semester": r[4]
        })
        
    return {"files": files}
