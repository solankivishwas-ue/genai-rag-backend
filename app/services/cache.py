from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Singleton client ──────────────────────────────────────────────────────────
_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """
    Return the shared async Redis client.
    Creates it on first call (lazy init).
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        logger.info("Redis client initialized", url=settings.REDIS_URL)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection pool gracefully (call on app shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")


# ── Key helpers ───────────────────────────────────────────────────────────────

def _hash(value: str) -> str:
    """SHA-256 hex digest of a string — used as a compact, safe cache key."""
    return hashlib.sha256(value.encode()).hexdigest()


def embedding_key(text: str) -> str:
    """Cache key for a text embedding vector."""
    return f"rag:embedding:{_hash(text)}"


def rag_query_key(query: str, top_k: int, threshold: float) -> str:
    """Cache key for a full RAG query response."""
    payload = f"{query}|{top_k}|{threshold:.4f}"
    return f"rag:query:{_hash(payload)}"


def document_list_key(page: int, page_size: int) -> str:
    """Cache key for a paginated document list."""
    return f"rag:documents:list:p{page}:s{page_size}"


# ── Generic cache operations ─────────────────────────────────────────────────

class CacheService:
    """
    Thin wrapper around the async Redis client.

    All methods are no-ops when CACHE_ENABLED=false or Redis is unreachable,
    so the application degrades gracefully without raising exceptions.
    """

    def __init__(self, client: Redis) -> None:
        self._r = client

    # ── Get ───────────────────────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve and JSON-deserialise a cached value.
        Returns None on miss or any Redis error.
        """
        if not settings.CACHE_ENABLED:
            return None
        try:
            raw = await self._r.get(key)
            if raw is None:
                logger.debug("Cache miss", key=key)
                return None
            logger.debug("Cache hit", key=key)
            return json.loads(raw)
        except RedisError as exc:
            logger.warning("Redis GET failed — bypassing cache", key=key, error=str(exc))
            return None

    # ── Set ───────────────────────────────────────────────────────────────────

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """
        JSON-serialise and store a value with an expiry (seconds).
        Silently skips on Redis errors.
        """
        if not settings.CACHE_ENABLED:
            return
        try:
            await self._r.setex(key, ttl, json.dumps(value))
            logger.debug("Cache set", key=key, ttl=ttl)
        except RedisError as exc:
            logger.warning("Redis SET failed — bypassing cache", key=key, error=str(exc))

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete(self, *keys: str) -> None:
        """Delete one or more keys. Silently skips on errors."""
        if not settings.CACHE_ENABLED or not keys:
            return
        try:
            await self._r.delete(*keys)
            logger.debug("Cache deleted", keys=keys)
        except RedisError as exc:
            logger.warning("Redis DELETE failed", keys=keys, error=str(exc))

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a glob pattern using SCAN (non-blocking).
        Returns the number of keys deleted.
        """
        if not settings.CACHE_ENABLED:
            return 0
        try:
            deleted = 0
            async for key in self._r.scan_iter(match=pattern, count=100):
                await self._r.delete(key)
                deleted += 1
            if deleted:
                logger.info("Cache pattern cleared", pattern=pattern, deleted=deleted)
            return deleted
        except RedisError as exc:
            logger.warning("Redis SCAN/DELETE failed", pattern=pattern, error=str(exc))
            return 0

    # ── Health ────────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Return True if Redis responds to PING."""
        try:
            return await self._r.ping()
        except RedisError:
            return False


async def get_cache() -> CacheService:
    """FastAPI dependency: returns a ready CacheService."""
    client = await get_redis()
    return CacheService(client)
