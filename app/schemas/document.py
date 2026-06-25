from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Document Schemas ─────────────────────────────────────────────────────────

class DocumentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=512, description="Document title")
    source: Optional[str] = Field(None, max_length=1024, description="URL or file path")
    content: str = Field(..., min_length=1, description="Raw document text")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Arbitrary metadata")


class DocumentCreate(DocumentBase):
    """Schema for ingesting a new document."""
    pass


class DocumentResponse(DocumentBase):
    """Schema returned to the client."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int


# ── Chunk Schemas ─────────────────────────────────────────────────────────────

class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: Optional[int]
    created_at: datetime


# ── RAG Query Schemas ─────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The question to answer")
    top_k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve")
    similarity_threshold: float = Field(
        0.7, ge=0.0, le=1.0, description="Minimum similarity score"
    )
    include_sources: bool = Field(True, description="Include source chunks in response")


class SourceChunk(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    content: str
    similarity_score: float


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[SourceChunk] = []
    model: str
    tokens_used: int


# ── Health Schemas ────────────────────────────────────────────────────────────

class HealthStatus(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str
    database: str
    openai: str


class ComponentHealth(BaseModel):
    name: str
    status: str
    latency_ms: Optional[float] = None
    detail: Optional[str] = None
