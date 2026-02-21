from fastapi import APIRouter, UploadFile, File, Form
from typing import List
import shutil
import os

from database.db import get_connection
from services.document_processor import extract_text_universal, extract_text_with_structure, is_supported
from services.ai_classifier import classify_text
from services.document_rag_service import process_document_chunks, process_structured_chunks, process_multiple_document_chunks
from services.moderation_service import ai_review, determine_initial_status

router = APIRouter()


# ===============================
# 📤 SINGLE FILE UPLOAD (EXISTING)
# ===============================

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    role: str = Form(...),        # faculty | student
    owner_id: str = Form(...)
):

    # ===============================
    # STEP 1 — SAVE FILE LOCALLY
    # ===============================
    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # ⭐ Detect file type
    file_type = file.filename.split(".")[-1].lower()

    # ===============================
    # STEP 2 — EXTRACT TEXT (UNIVERSAL)
    # ===============================
    text = extract_text_universal(file_path)

    # ===============================
    # STEP 3 — AI CLASSIFY (AUTO SORT)
    # ===============================
    metadata = classify_text(text)

    # ===============================
    # STEP 4 — AI MODERATION ONLY FOR STUDENTS
    # ===============================
    ai_score = None
    ai_flags = None

    status, visibility = determine_initial_status(role)

    if role == "student":
        review = ai_review(text)
        ai_score = review["score"]
        ai_flags = review["flags"]

    # ===============================
    # STEP 5 — READ FILE BINARY
    # ===============================
    with open(file_path, "rb") as f:
        binary_data = f.read()

    # ===============================
    # STEP 6 — INSERT INTO DATABASE
    # ===============================
    conn = get_connection_repo()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO repository_files
        (filename, file_type, semester, subject_code, unit,
         file_data, uploader_role, owner_id,
         status, visibility, ai_score, ai_flags)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        file.filename,
        file_type,
        metadata["semester"],
        metadata["subject_code"],
        metadata["unit"],
        binary_data,
        role,
        owner_id,
        status,
        visibility,
        ai_score,
        ai_flags
    ))

    file_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    # ===============================
    # STEP 7 — RAG INDEXING (STRUCTURED + TYPE-AWARE)
    # ===============================
    sections = extract_text_with_structure(file_path)

    if sections:
        process_structured_chunks(
            file_id,
            metadata["subject_code"],
            sections,
            file_type
        )
    else:
        process_document_chunks(
            file_id,
            metadata["subject_code"],
            text,
            file_type
        )

    return {
        "message": "Upload successful",
        "role": role,
        "status": status,
        "visibility": visibility,
        "file_id": file_id,
        "metadata": metadata
    }


# ===============================
# 📤📤 MULTI-FILE UPLOAD (AUTO-SORT + BATCH CHUNK)
# ===============================

@router.post("/upload/batch")
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    role: str = Form(...),
    owner_id: str = Form(...)
):
    """
    Upload multiple documents at once.
    Each file is individually:
      1. Saved locally
      2. Text-extracted (universal)
      3. AI-classified (auto-sorted into semester/subject/unit)
      4. Moderated (if student)
      5. Stored in the DB
      6. Chunked + embedded for RAG (type-aware, structured)

    Returns a summary of all processed files.
    """

    results = []
    skipped = []
    rag_batch = []   # collected for batch RAG indexing

    status, visibility = determine_initial_status(role)

    for file in files:

        # --- Guard: skip unsupported file types ---
        if not is_supported(file.filename):
            skipped.append({
                "filename": file.filename,
                "reason": "Unsupported file type"
            })
            continue

        # --- STEP 1: Save locally ---
        file_path = f"uploads/{file.filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_type = file.filename.split(".")[-1].lower()

        # --- STEP 2: Extract text ---
        text = extract_text_universal(file_path)

        if not text.strip():
            skipped.append({
                "filename": file.filename,
                "reason": "No text could be extracted"
            })
            continue

        # --- STEP 3: AI classify (auto-sort) ---
        try:
            metadata = classify_text(text)
        except Exception:
            metadata = {
                "semester": "unknown",
                "subject_code": "unknown",
                "unit": "0"
            }

        # --- STEP 4: Moderation ---
        ai_score = None
        ai_flags = None

        if role == "student":
            review = ai_review(text)
            ai_score = review["score"]
            ai_flags = review["flags"]

        # --- STEP 5: Read binary ---
        with open(file_path, "rb") as f:
            binary_data = f.read()

        # --- STEP 6: Insert into DB ---
        conn = get_connection_repo()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO repository_files
            (filename, file_type, semester, subject_code, unit,
             file_data, uploader_role, owner_id,
             status, visibility, ai_score, ai_flags)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            file.filename,
            file_type,
            metadata["semester"],
            metadata["subject_code"],
            metadata["unit"],
            binary_data,
            role,
            owner_id,
            status,
            visibility,
            ai_score,
            ai_flags
        ))

        file_id = cur.fetchone()[0]

        conn.commit()
        cur.close()
        conn.close()

        # --- STEP 7: Structured RAG indexing ---
        sections = extract_text_with_structure(file_path)

        if sections:
            process_structured_chunks(
                file_id,
                metadata["subject_code"],
                sections,
                file_type
            )
        else:
            process_document_chunks(
                file_id,
                metadata["subject_code"],
                text,
                file_type
            )

        results.append({
            "filename": file.filename,
            "file_id": file_id,
            "file_type": file_type,
            "metadata": metadata,
            "status": status,
            "visibility": visibility
        })

    return {
        "message": f"Batch upload complete — {len(results)} processed, {len(skipped)} skipped",
        "role": role,
        "processed": results,
        "skipped": skipped
    }
