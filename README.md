# GenAI RAG Backend

Production-ready **Retrieval-Augmented Generation (RAG)** backend built with:

| Technology | Purpose |
|------------|---------|
| **FastAPI** | Async REST API framework |
| **PostgreSQL 16** | Primary database |
| **pgvector** | Vector similarity search |
| **SQLAlchemy 2.0** | Async ORM |
| **OpenAI API** | Embeddings (`text-embedding-3-small`) + Chat (`gpt-4o`) |
| **Docker / Compose** | Containerisation |

---

## Quick Start

### 1. Clone & configure

```bash
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
```

### 2. Start with Docker Compose

```bash
docker compose up -d
```

### 3. Access the API

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/redoc | ReDoc |
| http://localhost:8000/api/v1/health | Health check |
| http://localhost:8000/api/v1/health/ready | Readiness probe |

---

## API Endpoints

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Basic status |
| GET | `/api/v1/health/live` | Liveness probe |
| GET | `/api/v1/health/ready` | Readiness (checks DB + OpenAI) |

### Documents (RAG Pipeline)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/documents/` | Ingest a document (chunks + embeds) |
| GET | `/api/v1/documents/` | List all documents |
| GET | `/api/v1/documents/{id}` | Get a document by ID |
| DELETE | `/api/v1/documents/{id}` | Delete document + chunks |
| POST | `/api/v1/documents/query` | RAG query (ask a question) |

---

## Project Structure

```
GenAI RAG/
├── app/
│   ├── main.py             # FastAPI app factory + lifespan
│   ├── config.py           # Pydantic settings (env-driven)
│   ├── database.py         # Async SQLAlchemy engine + session
│   ├── api/
│   │   └── v1/
│   │       ├── router.py
│   │       └── endpoints/
│   │           ├── health.py
│   │           └── documents.py
│   ├── models/
│   │   └── document.py     # ORM models (Document, DocumentChunk)
│   ├── schemas/
│   │   └── document.py     # Pydantic request/response schemas
│   ├── services/
│   │   ├── embedding.py    # OpenAI embedding service + chunker
│   │   └── rag.py          # Full RAG pipeline
│   └── core/
│       └── logging.py      # Structured logging (structlog)
├── migrations/
│   └── init.sql            # PostgreSQL DDL + pgvector setup
├── tests/
│   └── test_health.py
├── .env.example
├── Dockerfile              # Multi-stage build
├── docker-compose.yml
└── requirements.txt
```

---

## Local Development (without Docker)

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env

# Start only the database
docker compose up -d db

# Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Example Usage

### Ingest a document
```bash
curl -X POST http://localhost:8000/api/v1/documents/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "FastAPI Tutorial",
    "source": "https://fastapi.tiangolo.com",
    "content": "FastAPI is a modern, fast web framework for building APIs with Python..."
  }'
```

### Ask a question
```bash
curl -X POST http://localhost:8000/api/v1/documents/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is FastAPI?",
    "top_k": 5,
    "similarity_threshold": 0.7
  }'
```
