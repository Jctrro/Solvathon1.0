from fastapi import APIRouter
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from database.db import get_connection

# ==================================================
# 🔧 LOAD EMBEDDING MODEL ONCE
# ==================================================

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text: str):
    return embedding_model.encode(text).tolist()

# ==================================================
# 📦 REQUEST MODEL
# ==================================================

class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 6

router = APIRouter()

# ==================================================
# 🔎 SEMANTIC DOCUMENT SEARCH (DASHBOARD SEARCH)
# ==================================================

@router.post("/search/topic")
async def semantic_topic_search(data: SemanticSearchRequest):

    query_vector = embed(data.query)

    conn = get_connection_repo()
    cur = conn.cursor()

    # ⭐ IMPORTANT:
    # Using YOUR TABLE: doc_chunks
    # pgvector operator: <->

    cur.execute("""
        SELECT
            dc.file_id,
            dc.subject_code,
            dc.file_type,
            dc.section_label,
            dc.content,
            (dc.embedding <-> %s::vector) AS distance

        FROM doc_chunks dc

        ORDER BY distance ASC
        LIMIT 25
    """, (query_vector,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    # ==================================================
    # ⭐ GROUP BY DOCUMENT (file_id)
    # ==================================================

    doc_map = {}

    for r in rows:

        file_id = r[0]
        subject_code = r[1]
        file_type = r[2]
        section_label = r[3]
        content = r[4]
        distance = r[5]

        if file_id not in doc_map:
            doc_map[file_id] = {
                "file_id": file_id,
                "subject_code": subject_code,
                "file_type": file_type,
                "section": section_label,
                "snippet": content[:200],
                "best_distance": distance
            }
        else:
            # keep best semantic match
            if distance < doc_map[file_id]["best_distance"]:
                doc_map[file_id]["best_distance"] = distance
                doc_map[file_id]["snippet"] = content[:200]
                doc_map[file_id]["section"] = section_label

    # sort by relevance
    results = sorted(doc_map.values(), key=lambda x: x["best_distance"])

    return {
        "documents": results[:data.limit]
    }
