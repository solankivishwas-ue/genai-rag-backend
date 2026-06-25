from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    """Create an async test client without starting the real server."""
    # Patch settings to avoid requiring a real .env
    import os
    os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://rag_user:rag_password@localhost:5432/rag_db",
    )

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_root_redirects(client: AsyncClient):
    """Root endpoint should return app info."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "docs" in data


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """Basic health check should return 200 with status=ok."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_liveness_probe(client: AsyncClient):
    """Liveness probe should always return alive."""
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_openapi_schema_accessible(client: AsyncClient):
    """OpenAPI schema should be reachable."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] is not None
