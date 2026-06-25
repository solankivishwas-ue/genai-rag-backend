-- ============================================================
-- PostgreSQL + pgvector initialization script
-- Run once when setting up the database for the first time.
-- ============================================================

-- 1. Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Verify installation
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- ============================================================
-- Tables are created automatically by SQLAlchemy on startup.
-- This file is kept for reference and manual provisioning.
-- ============================================================

-- 3. Documents table (reference DDL)
CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       VARCHAR(512)    NOT NULL,
    source      VARCHAR(1024),
    content     TEXT            NOT NULL,
    metadata    TEXT,                       -- JSON string
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 4. Document chunks table with vector column (1536 dims = text-embedding-3-small)
CREATE TABLE IF NOT EXISTS document_chunks (
    id           UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID    NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    content      TEXT    NOT NULL,
    embedding    vector(1536),              -- pgvector column
    token_count  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. IVFFlat index for fast approximate cosine similarity search
--    (Requires at least a few hundred rows to be effective)
CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_ivfflat
    ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 6. Standard indexes
CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id
    ON document_chunks (document_id);

CREATE INDEX IF NOT EXISTS ix_documents_created_at
    ON documents (created_at DESC);
