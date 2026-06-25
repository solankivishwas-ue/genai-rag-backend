from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.core.logging import get_logger
from app.database import AsyncSessionLocal
from app.schemas.document import ComponentHealth, HealthStatus
from app.services.cache import get_cache
from app.services.embedding import _get_client

router = APIRouter(tags=["Health"])
logger = get_logger(__name__)


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Basic health check",
    description="Returns application status. Does not check external dependencies.",
)
async def health() -> HealthStatus:
    return HealthStatus(
        status="ok",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database="unknown",
        openai="unknown",
    )


@router.get(
    "/health/live",
    response_model=Dict[str, str],
    summary="Liveness probe",
    description="Kubernetes liveness probe – always returns 200 if process is alive.",
)
async def liveness() -> Dict[str, str]:
    return {"status": "alive"}


@router.get(
    "/health/ready",
    response_model=Dict[str, Any],
    summary="Readiness probe",
    description="Checks all critical dependencies (DB, OpenAI) before serving traffic.",
)
async def readiness() -> Dict[str, Any]:
    checks: list[ComponentHealth] = []
    overall = "ready"

    # ── Database check ────────────────────────────────────────────────────────
    db_start = time.monotonic()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_latency = round((time.monotonic() - db_start) * 1000, 2)
        checks.append(
            ComponentHealth(name="database", status="ok", latency_ms=db_latency)
        )
    except Exception as exc:
        logger.warning("Database health check failed", error=str(exc))
        checks.append(
            ComponentHealth(name="database", status="error", detail=str(exc))
        )
        overall = "degraded"

    # ── pgvector check ────────────────────────────────────────────────────────
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            row = result.fetchone()
            if row:
                checks.append(ComponentHealth(name="pgvector", status="ok"))
            else:
                checks.append(
                    ComponentHealth(
                        name="pgvector",
                        status="warning",
                        detail="Extension not installed",
                    )
                )
                overall = "degraded"
    except Exception as exc:
        checks.append(
            ComponentHealth(name="pgvector", status="error", detail=str(exc))
        )
        overall = "degraded"

    # ── LLM check (Ollama or OpenAI) ─────────────────────────────────────────
    llm_name = "ollama" if settings.USE_OLLAMA else "openai"
    llm_start = time.monotonic()
    try:
        client = _get_client()
        await client.models.list()
        llm_latency = round((time.monotonic() - llm_start) * 1000, 2)
        checks.append(
            ComponentHealth(name=llm_name, status="ok", latency_ms=llm_latency)
        )
    except Exception as exc:
        logger.warning(f"{llm_name} health check failed", error=str(exc))
        checks.append(
            ComponentHealth(name=llm_name, status="error", detail=str(exc))
        )
        overall = "degraded"

    # ── Redis check ───────────────────────────────────────────────────────────
    redis_start = time.monotonic()
    try:
        cache = await get_cache()
        is_alive = await cache.ping()
        redis_latency = round((time.monotonic() - redis_start) * 1000, 2)
        if is_alive:
            checks.append(
                ComponentHealth(name="redis", status="ok", latency_ms=redis_latency)
            )
        else:
            checks.append(ComponentHealth(name="redis", status="error", detail="PING failed"))
            overall = "degraded"
    except Exception as exc:
        logger.warning("Redis health check failed", error=str(exc))
        checks.append(ComponentHealth(name="redis", status="error", detail=str(exc)))
        overall = "degraded"

    return {
        "status": overall,
        "checks": [c.model_dump() for c in checks],
    }
