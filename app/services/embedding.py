from __future__ import annotations

import hashlib
import math
import random
from typing import List

import tiktoken
from openai import AsyncOpenAI

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Mode helpers ──────────────────────────────────────────────────────────────

def _is_mock_mode() -> bool:
    """Use mock embeddings when MOCK_EMBEDDINGS=true or API key is missing/placeholder."""
    if settings.MOCK_EMBEDDINGS:
        return True
    if settings.USE_OLLAMA:
        return False  # Ollama is real, not mock
    key = settings.OPENAI_API_KEY or ""
    return not key or key.startswith("sk-your")


def _get_client() -> AsyncOpenAI:
    """Return an AsyncOpenAI client pointed at Ollama or OpenAI depending on config."""
    if settings.USE_OLLAMA:
        return AsyncOpenAI(
            base_url=f"{settings.OLLAMA_BASE_URL}/v1",
            api_key="ollama",  # required by SDK, ignored by Ollama
        )
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _embedding_model() -> str:
    return settings.OLLAMA_EMBEDDING_MODEL if settings.USE_OLLAMA else settings.OPENAI_EMBEDDING_MODEL


def _embedding_dims() -> int:
    return settings.embedding_dimensions


def _mock_embedding(text: str, dims: int | None = None) -> List[float]:
    """Generate a deterministic pseudo-random unit vector from text hash."""
    dims = dims or _embedding_dims()
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(dims)]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


# ── Tiktoken encoder (cached) ─────────────────────────────────────────────────

def _get_encoder(model: str = "text-embedding-3-small") -> tiktoken.Encoding:
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = "text-embedding-3-small") -> int:
    return len(_get_encoder(model).encode(text))


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    model: str = "text-embedding-3-small",
) -> List[str]:
    """Token-aware text chunker using tiktoken."""
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    enc = _get_encoder(model)
    token_ids = enc.encode(text)
    total_tokens = len(token_ids)

    if total_tokens == 0:
        return []

    chunks: List[str] = []
    start = 0

    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        chunk_str = enc.decode(token_ids[start:end])
        chunks.append(chunk_str)
        if end == total_tokens:
            break
        start += chunk_size - chunk_overlap

    logger.debug(
        "Text chunked",
        total_tokens=total_tokens,
        chunk_size=chunk_size,
        num_chunks=len(chunks),
    )
    return chunks


# ── Embedding service ─────────────────────────────────────────────────────────

class EmbeddingService:
    """
    Wraps embedding generation — supports OpenAI, Ollama, and mock mode.
    Automatically caches results in Redis.
    """

    _MAX_BATCH_SIZE = 2048

    def __init__(self) -> None:
        self.model = _embedding_model()
        self.dimensions = _embedding_dims()

    async def embed_text(self, text: str, cache: "CacheService | None" = None) -> List[float]:
        from app.services.cache import embedding_key

        cleaned = text.replace("\n", " ").strip()
        key = embedding_key(cleaned)

        if cache:
            cached = await cache.get(key)
            if cached is not None:
                logger.debug("Embedding cache hit", key=key[:24])
                return cached

        if _is_mock_mode():
            logger.warning("Mock embedding used", text_preview=cleaned[:40])
            emb = _mock_embedding(cleaned, self.dimensions)
        else:
            provider = "Ollama" if settings.USE_OLLAMA else "OpenAI"
            logger.debug("Calling embedding API", provider=provider, model=self.model)
            client = _get_client()
            response = await client.embeddings.create(
                input=[cleaned],
                model=self.model,
            )
            emb = response.data[0].embedding
            logger.debug("Embedding received", dims=len(emb), provider=provider)

        if cache:
            await cache.set(key, emb, ttl=settings.REDIS_TTL_EMBEDDING)

        return emb

    async def embed_batch(
        self,
        texts: List[str],
        cache: "CacheService | None" = None,
    ) -> List[List[float]]:
        from app.services.cache import embedding_key

        cleaned = [t.replace("\n", " ").strip() for t in texts]
        results: List[List[float] | None] = [None] * len(cleaned)
        miss_indices: List[int] = []

        if cache:
            for i, text in enumerate(cleaned):
                cached = await cache.get(embedding_key(text))
                if cached is not None:
                    results[i] = cached
                else:
                    miss_indices.append(i)
        else:
            miss_indices = list(range(len(cleaned)))

        logger.info(
            "Embedding batch",
            total=len(texts),
            cache_hits=len(texts) - len(miss_indices),
            misses=len(miss_indices),
            provider="ollama" if settings.USE_OLLAMA else ("mock" if _is_mock_mode() else "openai"),
        )

        if miss_indices:
            miss_texts = [cleaned[i] for i in miss_indices]
            all_new: List[List[float]] = []

            if _is_mock_mode():
                logger.warning("Mock embeddings for batch", count=len(miss_texts))
                all_new = [_mock_embedding(t, self.dimensions) for t in miss_texts]
            else:
                client = _get_client()
                # Ollama doesn't support batch > 1 reliably — embed one-by-one
                if settings.USE_OLLAMA:
                    for text in miss_texts:
                        resp = await client.embeddings.create(input=[text], model=self.model)
                        all_new.append(resp.data[0].embedding)
                else:
                    for batch_start in range(0, len(miss_texts), self._MAX_BATCH_SIZE):
                        batch = miss_texts[batch_start: batch_start + self._MAX_BATCH_SIZE]
                        response = await client.embeddings.create(input=batch, model=self.model)
                        sorted_data = sorted(response.data, key=lambda x: x.index)
                        all_new.extend([item.embedding for item in sorted_data])

            for list_pos, orig_idx in enumerate(miss_indices):
                emb = all_new[list_pos]
                results[orig_idx] = emb
                if cache:
                    await cache.set(
                        embedding_key(cleaned[orig_idx]),
                        emb,
                        ttl=settings.REDIS_TTL_EMBEDDING,
                    )

        return [r for r in results if r is not None]
