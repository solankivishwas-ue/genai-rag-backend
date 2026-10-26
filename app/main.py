from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import _DEFAULT_SECRET_KEY, settings
from app.core.logging import get_logger, setup_logging
from app.database import dispose_engine, run_migrations
from app.services.cache import close_redis

# Logging must be configured before any logger is used
setup_logging()
logger = get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info(
        "Starting application",
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
    )
    if settings.is_production and settings.SECRET_KEY == _DEFAULT_SECRET_KEY:
        logger.warning(
            "SECRET_KEY is still the default value in production — "
            "set a strong SECRET_KEY, JWTs can be forged otherwise"
        )
    try:
        run_migrations()
        logger.info("Database migrations applied")
    except Exception as exc:
        logger.warning("Alembic migration failed — falling back to create_all()", error=str(exc))
        try:
            from app.database import engine, Base
            # Import all models so Base.metadata knows about them
            import app.models.document  # noqa: F401
            import app.models.user      # noqa: F401
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Tables created via SQLAlchemy create_all() fallback")
        except Exception as exc2:
            logger.error("create_all() also failed — DB may be unavailable", error=str(exc2))

    logger.info("Application ready", host=settings.HOST, port=settings.PORT)
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down application")
    await dispose_engine()
    await close_redis()


# ── Application Factory ───────────────────────────────────────────────────────
def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "## GenAI RAG Backend\n\n"
            "Production-ready **Retrieval-Augmented Generation** API.\n\n"
            "### Features\n"
            "- 📄 **Document Ingestion** — JSON body, file upload (PDF/DOCX/TXT), async background\n"
            "- 🔍 **Vector Search** — pgvector cosine similarity with IVFFlat index\n"
            "- 🤖 **RAG Pipeline** — OpenAI embeddings + GPT-4o chat, blocking & streaming\n"
            "- 🔐 **JWT Auth** — Register / login / refresh / protected routes\n"
            "- 📊 **Monitoring** — Prometheus `/metrics` endpoint\n"
            "- 🏥 **Health Checks** — `/health`, `/health/live`, `/health/ready`\n"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        contact={"name": "RAG Backend", "url": "https://github.com/solankivishwas-ue/genai-rag-backend"},
        license_info={"name": "MIT"},
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Prometheus Metrics ────────────────────────────────────────────────────
    if settings.ENABLE_METRICS:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_respect_env_var=False,
            excluded_handlers=["/metrics", "/health"],
        ).instrument(app).expose(app, endpoint=settings.METRICS_PATH)
        logger.info("Prometheus metrics enabled", path=settings.METRICS_PATH)

    # ── Global error handler ──────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred. Please try again later."},
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse(
            content={
                "app": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "docs": "/docs",
                "health": "/api/v1/health",
                "metrics": settings.METRICS_PATH if settings.ENABLE_METRICS else None,
            }
        )

    return app


app = create_application()
