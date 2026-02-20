import os
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from database.db import get_connection

# ===============================
# 🔧 INIT MODELS
# ===============================

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

llm = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)


# ===============================
# ✂️ TEXT SPLITTERS (TYPE-AWARE)
# ===============================

# Smaller chunks for dense content (PDFs, DOCX)
_splitter_dense = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100
)

# Larger chunks for slide-based content (PPTX) — each slide is already short
_splitter_slide = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=50
)

# Larger chunks for plain text / CSV
_splitter_plain = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150
)

_SPLITTER_MAP = {
    "pdf":  _splitter_dense,
    "docx": _splitter_dense,
    "pptx": _splitter_slide,
    "txt":  _splitter_plain,
    "csv":  _splitter_plain,
    "png":  _splitter_dense,
    "jpg":  _splitter_dense,
    "jpeg": _splitter_dense,
}


def _get_splitter(file_type: str) -> RecursiveCharacterTextSplitter:
    return _SPLITTER_MAP.get(file_type, _splitter_dense)


def split_text(text: str, file_type: str = "pdf") -> list[str]:
    """Split text into chunks using a strategy appropriate for the file type."""
    splitter = _get_splitter(file_type)
    return splitter.split_text(text)


# ===============================
# 🧠 EMBEDDING
# ===============================

def embed(text):
    return embedding_model.encode(text).tolist()


# ===============================
# 📄 PROCESS SINGLE DOCUMENT AFTER UPLOAD (TYPE-AWARE)
# ===============================

def process_document_chunks(file_id, subject_code, text, file_type="pdf"):
    """
    Chunk and embed a single document, storing results in doc_chunks.
    Uses a chunking strategy appropriate for the file_type.
    """
    chunks = split_text(text, file_type)

    conn = get_connection()
    cur = conn.cursor()

    for i, chunk in enumerate(chunks):

        vector = embed(chunk)

        cur.execute("""
            INSERT INTO doc_chunks (file_id, subject_code, content, embedding, chunk_index, file_type)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            file_id,
            subject_code,
            chunk,
            vector,
            i,
            file_type
        ))

    conn.commit()
    cur.close()
    conn.close()


# ===============================
# 📚 PROCESS MULTIPLE DOCUMENTS (BATCH RAG INDEXING)
# ===============================

def process_multiple_document_chunks(documents: list[dict]):
    """
    Batch-process multiple documents for RAG indexing.

    Each item in `documents` must have:
        file_id      : int
        subject_code : str
        text         : str
        file_type    : str   (pdf, docx, pptx, txt, csv, png, …)
    """
    conn = get_connection()
    cur = conn.cursor()

    for doc in documents:
        file_id = doc["file_id"]
        subject_code = doc["subject_code"]
        file_type = doc.get("file_type", "pdf")
        text = doc["text"]

        chunks = split_text(text, file_type)

        for i, chunk in enumerate(chunks):
            vector = embed(chunk)

            cur.execute("""
                INSERT INTO doc_chunks (file_id, subject_code, content, embedding, chunk_index, file_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                file_id,
                subject_code,
                chunk,
                vector,
                i,
                file_type
            ))

    conn.commit()
    cur.close()
    conn.close()


# ===============================
# 📄 STRUCTURED CHUNKING (SECTION-AWARE)
# ===============================

def process_structured_chunks(file_id, subject_code, sections: list[dict], file_type="pdf"):
    """
    Chunk using structural sections (pages / slides / headings).
    Each section is chunked independently so chunk boundaries respect
    document structure.

    sections = [{"section": "page_1", "content": "..."}, ...]
    """
    conn = get_connection()
    cur = conn.cursor()
    chunk_index = 0

    for sec in sections:
        section_label = sec["section"]
        content = sec["content"]

        if not content.strip():
            continue

        chunks = split_text(content, file_type)

        for chunk in chunks:
            vector = embed(chunk)

            cur.execute("""
                INSERT INTO doc_chunks
                    (file_id, subject_code, content, embedding, chunk_index, file_type, section_label)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                file_id,
                subject_code,
                chunk,
                vector,
                chunk_index,
                file_type,
                section_label
            ))
            chunk_index += 1

    conn.commit()
    cur.close()
    conn.close()


# ===============================
# 💬 INTERNAL CHAT ENGINE
# ===============================

def _generate_answer(context, question):

    prompt = f"""
You are a strict academic assistant.

Rules:
- Answer ONLY using the provided context.
- If answer is missing, reply:
  "I could not find this in the uploaded documents."

Context:
{context}

Question:
{question}
"""

    res = llm.chat.completions.create(
        model="arcee-ai/trinity-large-preview:free",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content


# ===============================
# 💬 CHAT WITH ONE DOCUMENT
# ===============================

def chat_with_single_document(file_id, question):
    """Retrieve top-3 chunks from a single document and generate an answer."""

    q_embed = embed(question)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT content, section_label
        FROM doc_chunks
        WHERE file_id = %s
        ORDER BY embedding <-> %s::vector
        LIMIT 3
    """, (file_id, q_embed))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    context = "\n".join([r[0] for r in rows])

    return _generate_answer(context, question)


# ===============================
# 💬 CHAT WITH SUBJECT (MULTI DOCUMENT)
# ===============================

def chat_with_subject(subject_code, question):
    """Retrieve top-5 chunks across all documents for a subject."""

    q_embed = embed(question)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT content, section_label, file_id
        FROM doc_chunks
        WHERE subject_code = %s
        ORDER BY embedding <-> %s::vector
        LIMIT 5
    """, (subject_code, q_embed))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    context = "\n".join([r[0] for r in rows])

    return _generate_answer(context, question)


# ===============================
# 💬 CHAT ACROSS ALL DOCUMENTS (GLOBAL RAG)
# ===============================

def chat_global(question, top_k=5):
    """Search across ALL indexed documents regardless of subject."""

    q_embed = embed(question)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT content, subject_code, file_id, section_label
        FROM doc_chunks
        ORDER BY embedding <-> %s::vector
        LIMIT %s
    """, (q_embed, top_k))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    context = "\n".join([r[0] for r in rows])

    return _generate_answer(context, question)