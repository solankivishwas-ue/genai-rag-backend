from __future__ import annotations

import uuid
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.schemas.document import QueryRequest, QueryResponse, SourceChunk
from app.services.cache import CacheService, rag_query_key
from app.services.embedding import EmbeddingService, _get_client, _is_mock_mode

logger = get_logger(__name__)


class RAGService:
    """
    Orchestrates the full RAG pipeline:
      1. Check Redis for a cached answer (Layer 2 cache)
      2. Embed the query — with Redis embedding cache (Layer 1)
      3. Retrieve top-K chunks via pgvector cosine similarity
      4. Generate a grounded answer via the configured LLM (Ollama or OpenAI)
      5. Store the full response in Redis for future identical queries
    """

    def __init__(self, db: AsyncSession, cache: Optional[CacheService] = None) -> None:
        self.db = db
        self.cache = cache
        self.embedding_service = EmbeddingService()
        self.client = _get_client()

    # ── Retrieval ─────────────────────────────────────────────────────────────

    async def retrieve_similar_chunks(
        self,
        query_embedding: List[float],
        top_k: int,
        similarity_threshold: float,
    ) -> list:
        """Cosine similarity search via pgvector <=> operator."""
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

        stmt = text(
            """
            SELECT
                dc.id           AS chunk_id,
                dc.content      AS chunk_content,
                dc.chunk_index,
                dc.token_count,
                dc.document_id,
                d.title         AS doc_title,
                d.source        AS doc_source,
                1 - (dc.embedding <=> :embedding ::vector) AS similarity
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.embedding IS NOT NULL
              AND 1 - (dc.embedding <=> :embedding ::vector) >= :threshold
            ORDER BY dc.embedding <=> :embedding ::vector
            LIMIT :top_k
            """
        )
        result = await self.db.execute(
            stmt,
            {"embedding": embedding_str, "threshold": similarity_threshold, "top_k": top_k},
        )
        rows = result.fetchall()
        logger.info("Vector search complete", retrieved=len(rows), top_k=top_k)
        return rows

    # ── Generation ────────────────────────────────────────────────────────────

    async def generate_answer(
        self, query: str, context_chunks: list
    ) -> Tuple[str, int]:
        """Build a context-grounded prompt and call the configured LLM."""
        if not context_chunks:
            context = "No relevant context found."
        else:
            context_parts = [
                f"[{i+1}] Source: {row.doc_title}\n{row.chunk_content}"
                for i, row in enumerate(context_chunks)
            ]
            context = "\n\n---\n\n".join(context_parts)

        if _is_mock_mode():
            return (
                f"Mock mode — no LLM configured. Found {len(context_chunks)} relevant "
                f"chunk(s).\n\nContext preview:\n{context[:400]}",
                0,
            )

        system_prompt = (
            "You are a helpful AI assistant. Answer the user's question using ONLY "
            "the provided context. If the context does not contain enough information, "
            "say so clearly. Do not make up facts. Cite source numbers (e.g. [1]) "
            "when referencing specific parts of the context.\n\n"
            f"Context:\n{context}"
        )

        response = await self.client.chat.completions.create(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=settings.OPENAI_TEMPERATURE,
        )

        answer = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        logger.info("Answer generated", model=settings.chat_model, tokens=tokens)
        return answer, tokens

    # ── Full Pipeline (with Redis cache) ──────────────────────────────────────

    async def query(self, request: QueryRequest) -> QueryResponse:
        """
        End-to-end RAG query with two Redis cache layers:
          - Layer 1: Per-text embedding cache (in EmbeddingService)
          - Layer 2: Full query→response cache (here, keyed by query+params)
        """
        cache_key = rag_query_key(request.query, request.top_k, request.similarity_threshold)

        # ── Layer 2 cache read ────────────────────────────────────────────────
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                logger.info("RAG query cache hit", query=request.query[:60])
                return QueryResponse(**cached)

        # ── Full pipeline ─────────────────────────────────────────────────────
        query_embedding = await self.embedding_service.embed_text(
            request.query, cache=self.cache
        )

        rows = await self.retrieve_similar_chunks(
            query_embedding=query_embedding,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
        )

        answer, tokens = await self.generate_answer(request.query, rows)

        sources = []
        if request.include_sources:
            sources = [
                SourceChunk(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    document_title=row.doc_title,
                    content=row.chunk_content,
                    similarity_score=round(row.similarity, 4),
                )
                for row in rows
            ]

        response = QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources,
            model=settings.chat_model,
            tokens_used=tokens,
        )

        # ── Layer 2 cache write ───────────────────────────────────────────────
        if self.cache:
            await self.cache.set(
                cache_key,
                response.model_dump(mode="json"),
                ttl=settings.REDIS_TTL_RAG_QUERY,
            )
            logger.info("RAG response cached", key=cache_key[:32], ttl=settings.REDIS_TTL_RAG_QUERY)

        return response
