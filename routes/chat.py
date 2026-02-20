from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from services.document_rag_service import (
    chat_with_single_document,
    chat_with_subject,
    chat_global
)

# ======================================
# 📦 Router Init
# ======================================

router = APIRouter()

# ======================================
# 🧾 Request Models
# ======================================

class DocumentChatRequest(BaseModel):
    file_id: int
    question: str


class SubjectChatRequest(BaseModel):
    subject_code: str
    question: str


class GlobalChatRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5


# ======================================
# 💬 CHAT WITH SINGLE DOCUMENT
# ======================================

@router.post("/chat/document")
async def chat_document(data: DocumentChatRequest):

    answer = chat_with_single_document(
        data.file_id,
        data.question
    )

    return {"answer": answer}


# ======================================
# 💬 CHAT WITH SUBJECT (MULTI DOCUMENT)
# ======================================

@router.post("/chat/subject")
async def chat_subject(data: SubjectChatRequest):

    answer = chat_with_subject(
        data.subject_code,
        data.question
    )

    return {"answer": answer}


# ======================================
# 💬 CHAT ACROSS ALL DOCUMENTS (GLOBAL)
# ======================================

@router.post("/chat/global")
async def chat_all(data: GlobalChatRequest):

    answer = chat_global(
        data.question,
        top_k=data.top_k
    )

    return {"answer": answer}


# ======================================
# 🔁 BACKWARD COMPAT — OLD /chat/pdf ENDPOINT
# ======================================

class PDFChatRequest(BaseModel):
    file_id: int
    question: str


@router.post("/chat/pdf")
async def chat_pdf(data: PDFChatRequest):
    """Legacy endpoint — redirects to the generic document chat."""
    answer = chat_with_single_document(
        data.file_id,
        data.question
    )
    return {"answer": answer}