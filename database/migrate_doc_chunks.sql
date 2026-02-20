-- =============================================
-- MIGRATION: pdf_chunks  →  doc_chunks
-- Supports multi-document, type-aware RAG chunking
-- =============================================

-- 1. Enable pgvector if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the new doc_chunks table
CREATE TABLE IF NOT EXISTS doc_chunks (
    id            SERIAL PRIMARY KEY,
    file_id       INTEGER NOT NULL,
    subject_code  VARCHAR(50),
    content       TEXT NOT NULL,
    embedding     vector(384),           -- all-MiniLM-L6-v2 produces 384-dim vectors
    chunk_index   INTEGER DEFAULT 0,     -- order of chunk within the document
    file_type     VARCHAR(20) DEFAULT 'pdf',
    section_label VARCHAR(100),          -- e.g. page_1, slide_3, Heading text
    created_at    TIMESTAMP DEFAULT NOW()
);

-- 3. Indexes for fast vector search
CREATE INDEX IF NOT EXISTS idx_doc_chunks_file_id       ON doc_chunks (file_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_subject_code  ON doc_chunks (subject_code);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_file_type     ON doc_chunks (file_type);

-- 4. (Optional) Migrate existing data from pdf_chunks if it exists
-- Uncomment the block below if you want to preserve old data:
--
-- INSERT INTO doc_chunks (file_id, subject_code, content, embedding)
-- SELECT file_id, subject_code, content, embedding
-- FROM pdf_chunks;
--
-- DROP TABLE IF EXISTS pdf_chunks;
