"""Change embedding vector dimension from 1536 (OpenAI) to 768 (nomic-embed-text / Ollama)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-03 00:00:00.000000
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old IVFFlat index (tied to the old vector size)
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_ivfflat;")

    # Change the embedding column from vector(1536) to vector(768)
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(768);")

    # Recreate the IVFFlat index for the new dimension
    op.execute(
        """
        CREATE INDEX ix_document_chunks_embedding_ivfflat
        ON document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_ivfflat;")
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536);")
    op.execute(
        """
        CREATE INDEX ix_document_chunks_embedding_ivfflat
        ON document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
        """
    )
