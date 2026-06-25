# GenAI RAG Backend — Full Project Report
## Interview-Ready Documentation

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Why We Built This](#2-why-we-built-this)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack — What & Why](#4-technology-stack--what--why)
5. [Initial Design — Phase 1](#5-initial-design--phase-1)
6. [The RAG Pipeline — How It Works](#6-the-rag-pipeline--how-it-works)
7. [Database Design](#7-database-design)
8. [API Design](#8-api-design)
9. [Authentication System](#9-authentication-system)
10. [Caching Strategy](#10-caching-strategy)
11. [Streaming Responses (SSE)](#11-streaming-responses-sse)
12. [Changes Made & Why](#12-changes-made--why)
13. [Ollama Integration — Phase 2](#13-ollama-integration--phase-2)
14. [Frontend](#14-frontend)
15. [Monitoring & Observability](#15-monitoring--observability)
16. [Key Problems We Solved](#16-key-problems-we-solved)
17. [Interview Q&A — Cheat Sheet](#17-interview-qa--cheat-sheet)

---

## 1. Project Overview

**GenAI RAG Backend** is a production-ready **Retrieval-Augmented Generation (RAG)** API system. It allows users to:

1. Upload documents (PDF, DOCX, TXT)
2. Ask natural language questions about those documents
3. Receive accurate, grounded answers from an LLM — backed by the actual document content

The system ensures the LLM only answers based on **what's in your documents**, not from its general training knowledge. This is the core value of RAG.

---

## 2. Why We Built This

### The Problem with Plain LLMs
When you ask GPT-4 a question, it answers from its training data (knowledge cutoff ~2024). It:
- Doesn't know your **private documents**
- Can **hallucinate** (make up facts)
- Can't cite **where** an answer came from

### What RAG Solves
RAG (Retrieval-Augmented Generation) fixes this by:
1. **Retrieving** the most relevant chunks from your documents
2. **Injecting** them into the LLM's prompt as context
3. **Instructing** the LLM to answer ONLY from that context

The result: accurate, document-grounded answers with **source citations**.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User's Browser                          │
│              React Frontend (localhost:5173)                 │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────────┐
│              FastAPI Backend (localhost:8000)                │
│                    [Docker Container]                        │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Auth Routes │  │  Doc Routes  │  │  Health Routes   │  │
│  │  /auth/*     │  │  /documents/ │  │  /health/*       │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────┘  │
│                           │                                  │
│  ┌────────────────────────▼──────────────────────────────┐  │
│  │                   RAG Pipeline                         │  │
│  │  1. Embed query  →  2. Vector search  →  3. LLM chat  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────┬─────────────────┬───────────────────┬────────────────┘
       │                 │                   │
┌──────▼──────┐  ┌───────▼──────┐  ┌────────▼────────┐
│ PostgreSQL   │  │    Redis     │  │  Ollama / OpenAI│
│ + pgvector   │  │    Cache     │  │  (Host machine) │
│ [Docker]     │  │  [Docker]    │  │                 │
└─────────────┘  └──────────────┘  └─────────────────┘
```

---

## 4. Technology Stack — What & Why

### Backend
| Technology | Version | Why We Chose It |
|------------|---------|-----------------|
| **FastAPI** | 0.111.0 | Async Python, auto Swagger docs, Pydantic validation, fastest Python framework |
| **Uvicorn** | 0.30.1 | ASGI server — handles async I/O, WebSockets, SSE streaming |
| **SQLAlchemy** | 2.0.30 | Async ORM, type-safe mapped columns, works well with pgvector |
| **PostgreSQL + pgvector** | pg16 | Stores documents AND vectors in one DB; pgvector enables cosine similarity search |
| **Alembic** | 1.13.1 | Database migrations — version-controls schema changes |
| **Redis** | 7-alpine | Two-layer caching: embeddings (24h TTL) + full RAG responses (1h TTL) |
| **OpenAI SDK** | 1.35.3 | Used for both OpenAI AND Ollama (Ollama has an OpenAI-compatible API) |
| **tiktoken** | 0.7.0 | Token-aware text chunking — splits documents exactly at token boundaries |
| **pypdf + python-docx** | latest | Parse PDF and DOCX files during upload |
| **structlog** | 24.2.0 | Structured JSON logging — better than plain print() for production |
| **Prometheus** | - | Metrics endpoint for monitoring request counts, latency, etc. |
| **python-jose + passlib** | latest | JWT token generation and bcrypt password hashing |

### Frontend
| Technology | Why |
|------------|-----|
| **React + Vite** | Fast dev server, modern component-based UI |
| **Lucide React** | Clean icon library |
| **Vanilla CSS** | Maximum control, no Tailwind overhead |
| **Fetch API (SSE)** | Native browser streaming — no extra library needed |

### Infrastructure
| Technology | Why |
|------------|-----|
| **Docker + Docker Compose** | One command to start everything: DB, Redis, API |
| **Ollama** | Local LLM — free, no API costs, runs on your machine |

---

## 5. Initial Design — Phase 1

### What We Built First

The project started as a pure **OpenAI-powered RAG API**:

```
Upload PDF → Extract text → Split into chunks → OpenAI embeddings → Store in pgvector
Ask question → OpenAI embedding → Cosine search → GPT-4o answer
```

#### Initial file structure:
```
app/
├── main.py              # FastAPI app factory
├── config.py            # Pydantic settings from .env
├── database.py          # SQLAlchemy async engine
├── models/
│   ├── document.py      # Document + DocumentChunk ORM models
│   └── user.py          # User ORM model
├── schemas/
│   └── document.py      # Pydantic request/response schemas
├── api/v1/
│   ├── router.py        # Route aggregator
│   └── endpoints/
│       ├── auth.py      # Register, login, JWT refresh
│       ├── documents.py # Upload, ingest, query, stream
│       └── health.py    # /health, /health/ready, /health/live
└── services/
    ├── embedding.py     # Text chunking + embedding generation
    ├── rag.py           # RAG pipeline orchestrator
    └── cache.py         # Redis cache wrapper
```

#### Key design decisions at this stage:

**Why async everywhere?**
FastAPI supports async Python (`async def`) natively. Using async SQLAlchemy and async Redis means the server can handle many concurrent requests without blocking — critical for an AI app where embedding/LLM calls can take 2-5 seconds.

**Why PostgreSQL for vectors?**
We chose pgvector extension over dedicated vector DBs (Pinecone, Weaviate) because:
- Documents and their vector chunks live in the **same database** — simpler ops
- No extra service to manage
- SQL joins work naturally (join chunks to documents for metadata)
- pgvector's IVFFlat index gives near-O(log n) similarity search

**Why chunk documents?**
LLMs have a **context window limit** (e.g., 128K tokens for GPT-4o). A 500-page PDF is ~250,000 tokens — too large to fit. Chunking splits it into 512-token pieces. We retrieve only the **top-5 most relevant chunks** — fitting easily within context.

**Why 512 tokens per chunk with 50-token overlap?**
- 512 tokens ≈ ~380 words — enough context per chunk for meaningful answers
- 50-token overlap ensures sentences cut at boundaries aren't lost between chunks
- Uses tiktoken (same tokenizer as OpenAI) for exact token counting

---

## 6. The RAG Pipeline — How It Works

This is the core of the entire project. Here's the step-by-step flow:

### Document Ingestion (upload time)

```
PDF file uploaded
     ↓
Extract raw text (pypdf / python-docx)
     ↓
Split into 512-token chunks with 50-token overlap (tiktoken)
     ↓
For each chunk: call Embedding API → get 768-dim float vector
     ↓
Store chunk text + vector in document_chunks table (pgvector)
     ↓
Cache embedding in Redis (TTL: 24 hours)
```

### Query Time (when user asks a question)

```
User types: "What is the main topic of chapter 3?"
     ↓
1. EMBED QUERY
   Call embedding API with the question text
   → Returns a 768-dim float vector
     ↓
2. VECTOR SEARCH (pgvector)
   SQL: SELECT chunks WHERE cosine_similarity(chunk.embedding, query.embedding) >= threshold
   ORDER BY similarity DESC LIMIT 5
   → Returns top-5 most relevant document chunks
     ↓
3. BUILD CONTEXT
   Format: "[1] Source: mybook.pdf\n<chunk text>\n---\n[2] Source: ..."
     ↓
4. LLM CHAT (streamed)
   System prompt: "Answer ONLY from this context: {context}"
   User message: "What is the main topic of chapter 3?"
   → LLM streams back answer token by token
     ↓
5. SSE STREAM TO BROWSER
   Each token: data: {"delta": "The "}\n\n
   Sources event: event: sources\ndata: [{chunk_id, title, score}]\n\n
   End: data: [DONE]\n\n
     ↓
6. CACHE FULL RESPONSE
   Store in Redis (TTL: 1 hour)
   Next identical query → instant answer from cache
```

### The SQL Query (vector search)
```sql
SELECT
    dc.id AS chunk_id,
    dc.content AS chunk_content,
    dc.document_id,
    d.title AS doc_title,
    1 - (dc.embedding <=> :query_vector::vector) AS similarity
FROM document_chunks dc
JOIN documents d ON d.id = dc.document_id
WHERE dc.embedding IS NOT NULL
  AND 1 - (dc.embedding <=> :query_vector::vector) >= :threshold
ORDER BY dc.embedding <=> :query_vector::vector
LIMIT 5;
```

> `<=>` is pgvector's **cosine distance** operator. `1 - cosine_distance = cosine_similarity`. We order by distance (ascending = most similar first).

---

## 7. Database Design

### Tables

#### `documents`
Stores the raw uploaded document.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `title` | VARCHAR(512) | Document name |
| `source` | VARCHAR(1024) | Original filename |
| `content` | TEXT | Full extracted text |
| `metadata` | TEXT (JSON) | File size, original name, etc. |
| `created_at` | TIMESTAMPTZ | When uploaded |
| `updated_at` | TIMESTAMPTZ | When last modified |

#### `document_chunks`
Stores each 512-token piece with its embedding vector.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `document_id` | UUID | Foreign key → documents |
| `chunk_index` | INTEGER | Position within document (0, 1, 2...) |
| `content` | TEXT | The actual chunk text |
| `embedding` | Vector(768) | 768-dim float array for similarity search |
| `token_count` | INTEGER | How many tokens in this chunk |
| `created_at` | TIMESTAMPTZ | When created |

> **Note:** The embedding dimension started at **1536** (OpenAI) and was migrated to **768** (Ollama/nomic-embed-text) — covered in Changes section.

#### `users`
Stores registered users for JWT authentication.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `email` | VARCHAR | Unique login identifier |
| `hashed_password` | VARCHAR | bcrypt hashed — never stored plain |
| `full_name` | VARCHAR | Display name |
| `is_active` | BOOLEAN | Soft disable without delete |
| `created_at` | TIMESTAMPTZ | Registration time |

#### IVFFlat Index
```sql
CREATE INDEX ix_document_chunks_embedding_ivfflat
ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```
This is a **approximate nearest-neighbor** index. `lists=100` divides the vector space into 100 clusters. At query time, only the nearest clusters are searched — making search **O(log n)** instead of O(n) (brute force). Trade-off: tiny accuracy loss for huge speed gain at scale.

### Schema Migrations (Alembic)
We have 3 migrations:
- **0001**: Create `documents`, `document_chunks`, `users` tables + pgvector extension
- **0002**: Add IVFFlat index to `document_chunks.embedding`
- **0003**: Change `embedding` column from `Vector(1536)` → `Vector(768)` for Ollama

---

## 8. API Design

All routes are versioned under `/api/v1/`. Full docs at `http://localhost:8000/docs`.

### Auth Routes (`/auth/`)
| Method | Endpoint | What it does |
|--------|----------|--------------|
| POST | `/auth/register` | Create account (email + password) |
| POST | `/auth/login` | Login → returns JWT access + refresh tokens |
| POST | `/auth/refresh` | Exchange refresh token for new access token |
| GET | `/auth/me` | Get current user profile |

### Document Routes (`/documents/`)
| Method | Endpoint | What it does |
|--------|----------|--------------|
| GET | `/documents/` | List all documents (paginated) |
| POST | `/documents/` | Ingest document from JSON body |
| POST | `/documents/upload` | Upload PDF/DOCX/TXT file |
| DELETE | `/documents/{id}` | Delete document + its chunks |
| POST | `/documents/query` | RAG query (blocking — waits for full answer) |
| POST | `/documents/query/stream` | RAG query (SSE streaming — tokens appear live) |

### Health Routes (`/health/`)
| Method | Endpoint | What it does |
|--------|----------|--------------|
| GET | `/health` | Basic status (always 200 if app is running) |
| GET | `/health/live` | Kubernetes liveness probe |
| GET | `/health/ready` | Checks DB, pgvector, Redis, LLM connectivity |

---

## 9. Authentication System

We implemented **JWT (JSON Web Token)** authentication with:

- **Registration**: Password is hashed with `bcrypt` before storing — never stored as plain text
- **Login**: Returns two tokens:
  - `access_token` (30 min TTL) — sent with every API request
  - `refresh_token` (7 days TTL) — used to get new access tokens without re-login
- **Protected routes**: Use FastAPI `Depends(get_current_user)` — automatically validates the JWT on every request
- **Token format**: `Authorization: Bearer <token>` header

### Why JWT over sessions?
- Stateless — no session table in DB needed
- Scales horizontally — any server instance can verify any token
- Refresh token pattern means users don't have to re-login every 30 minutes

---

## 10. Caching Strategy

We implemented a **two-layer Redis cache**:

### Layer 1 — Embedding Cache (TTL: 24 hours)
```
Key:  "emb:{md5(text)}"
Value: [0.123, -0.456, ...] (768 floats)
```
When the same text is embedded again (e.g., a common query phrase), the API skips the Ollama/OpenAI call entirely and returns the cached vector. **Saves latency + API costs.**

### Layer 2 — Full RAG Response Cache (TTL: 1 hour)
```
Key:  "rag:{md5(query + top_k + threshold)}"
Value: {answer, sources, model, tokens_used}
```
If the exact same question with the same parameters is asked again within 1 hour, the full answer is returned from Redis instantly. **Eliminates the entire RAG pipeline for repeat queries.**

### Why Redis over in-memory caching?
- Persists across server restarts (appendonly mode enabled)
- Shared across multiple API workers
- Built-in TTL (auto-expiry)

---

## 11. Streaming Responses (SSE)

One of the most important UX features — the answer appears word-by-word in the UI, like ChatGPT.

### How SSE (Server-Sent Events) Works

**Backend** — FastAPI `StreamingResponse` with a generator:
```python
async def _event_stream():
    # 1. Emit sources first
    yield f"event: sources\ndata: {sources_json}\n\n"
    
    # 2. Stream LLM tokens as they arrive
    async for chunk in llm_stream:
        delta = chunk.choices[0].delta.content or ""
        yield f"data: {json.dumps({'delta': delta})}\n\n"
    
    # 3. Signal completion
    yield "data: [DONE]\n\n"

return StreamingResponse(_event_stream(), media_type="text/event-stream")
```

**Frontend** — React with `fetch()` ReadableStream:
```javascript
const res = await fetch('/api/v1/documents/query/stream', { method: 'POST', ... });
const reader = res.body.getReader();

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // Parse SSE lines → update chat message in real-time
}
```

### Why SSE over WebSockets?
- SSE is **one-way** (server → client only) — perfect for streaming answers
- Works over standard HTTP — no upgrade handshake
- Built-in browser reconnection
- Simpler to implement than WebSockets for this use case

---

## 12. Changes Made & Why

This section documents every significant change and the reason behind it.

---

### Change 1 — CORS Configuration
**Problem:** Browser blocked requests from `localhost:5173` (Vite) to `localhost:8000` (FastAPI). Error: `No 'Access-Control-Allow-Origin' header`.

**Fix:** Added `CORSMiddleware` in `main.py` with `http://localhost:5173` in allowed origins.

**Why this happens:** Browsers enforce the **same-origin policy** — requests to a different port are considered cross-origin. CORS headers tell the browser "this API allows requests from that origin."

---

### Change 2 — Mock Embeddings Mode
**Problem:** During development, every document upload called OpenAI embeddings API — spending credits even for testing.

**Fix:** Added `MOCK_EMBEDDINGS=true` in config. When enabled:
- Generates **deterministic random unit vectors** using MD5 hash of the text as seed
- Same text → same mock vector (reproducible)
- No API call made

**Why deterministic?** Random vectors work for basic testing but must be consistent — if you embed the same chunk twice, you need the same vector or the cache won't work correctly.

---

### Change 3 — SSE Error Handling in Backend
**Problem:** When OpenAI threw an exception inside the streaming generator, the Python exception propagated up and **killed the HTTP connection mid-stream**. Browser showed `ERR_INCOMPLETE_CHUNKED_ENCODING`.

**Fix:** Wrapped the entire generator in `try/except`:
```python
try:
    async for chunk in llm_stream:
        yield f"data: {json.dumps({'delta': delta})}\n\n"
except Exception as exc:
    yield f"data: {json.dumps({'error': str(exc)})}\n\n"
finally:
    yield "data: [DONE]\n\n"
```
Now errors are **sent to the frontend as a JSON event** instead of crashing the stream.

---

### Change 4 — SSE Error Handling in Frontend
**Problem:** When the backend sent `{"error": "..."}` inside the stream, the frontend ignored it (no handler for that shape). The UI showed "(No answer generated)" with no explanation.

**Fix:** Added `parsed.error` check in the SSE reader:
```javascript
if (parsed.error) {
    streamError = parsed.error;  // Show as error bubble in UI
} else if (parsed.delta !== undefined) {
    answerText += parsed.delta;  // Normal token
}
```

---

### Change 5 — OpenAI Quota Exceeded → Ollama
**Problem:** OpenAI API returned `429 - insufficient_quota`. Development was blocked — couldn't test without spending money.

**Fix:** Integrated **Ollama** as a local LLM alternative:
- Same OpenAI Python SDK, different `base_url`
- `nomic-embed-text` for embeddings (768 dims, free, local)
- `llama3.2` for chat (free, local, runs on your CPU/GPU)

**Why this was a good design decision:** By using the OpenAI SDK's `base_url` parameter, we didn't need a separate Ollama SDK. The entire codebase just points to a different URL. Zero additional dependencies.

---

### Change 6 — Vector Dimension Migration (1536 → 768)
**Problem:** OpenAI's `text-embedding-3-small` returns 1536-dim vectors. Ollama's `nomic-embed-text` returns 768-dim vectors. The pgvector column was `Vector(1536)` — inserting a 768-dim vector caused:
```
ValueError: expected 1536 dimensions, not 768
```

**Fix:**
1. Created Alembic migration `0003` to `ALTER COLUMN embedding TYPE vector(768)`
2. Changed Python model to use `settings.embedding_dimensions` (a property that returns 768 or 1536 based on `USE_OLLAMA`)
3. Truncated existing documents (old 1536-dim vectors are incompatible with new 768-dim column)

**Interview-worthy note:** This is a real-world database schema migration scenario. You can't just change the column type if data exists with the old size — you must truncate or re-embed.

---

### Change 7 — Similarity Threshold Set to 0.0
**Problem:** Documents uploaded with mock embeddings (random vectors) were queried with real Ollama embeddings. Random vs real = near-zero cosine similarity → threshold 0.7 filtered out ALL results → empty context → unhelpful LLM answer.

**Fix:** Frontend sets `similarity_threshold=0.0` in query requests, ensuring all chunks are returned regardless of similarity score. The LLM then filters relevance naturally in its response.

---

### Change 8 — `host.docker.internal` for Ollama
**Problem:** Ollama runs on the host machine (Windows), not inside Docker. From inside the Docker container, `localhost` refers to the container itself, not the host machine.

**Fix:** Used `host.docker.internal` — a special DNS name that Docker Desktop provides on Windows/Mac to reach the host machine from inside containers:
```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```
Also added `extra_hosts: ["host.docker.internal:host-gateway"]` in `docker-compose.yml` as a fallback for Linux environments.

---

## 13. Ollama Integration — Phase 2

### What Changed
We added a `USE_OLLAMA` flag that switches the entire LLM stack to local:

```python
def _get_client() -> AsyncOpenAI:
    if settings.USE_OLLAMA:
        return AsyncOpenAI(
            base_url=f"{settings.OLLAMA_BASE_URL}/v1",  # Ollama's OpenAI-compatible API
            api_key="ollama",  # Required by SDK, ignored by Ollama
        )
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
```

### Three Modes Supported
| Mode | When | Embeddings | Chat |
|------|------|------------|------|
| **OpenAI** | `USE_OLLAMA=false`, valid key | `text-embedding-3-small` (1536d) | `gpt-4o` |
| **Ollama** | `USE_OLLAMA=true` | `nomic-embed-text` (768d) | `llama3.2` |
| **Mock** | `MOCK_EMBEDDINGS=true` or no key | Random unit vectors | Mock text response |

### Why Ollama Uses One-by-One Embedding
OpenAI supports batching up to 2048 texts in one API call. Ollama's `/v1/embeddings` endpoint has inconsistent batch support depending on version. We embed one-by-one for Ollama to ensure reliability:
```python
if settings.USE_OLLAMA:
    for text in miss_texts:
        resp = await client.embeddings.create(input=[text], model=self.model)
        all_new.append(resp.data[0].embedding)
```

---

## 14. Frontend

### Components
| File | Purpose |
|------|---------|
| `AuthPage.jsx` | Login / Register form |
| `Sidebar.jsx` | Document list + upload button |
| `UploadModal.jsx` | Drag-and-drop PDF upload dialog |
| `ChatWindow.jsx` | Real-time chat with SSE streaming |

### Key Frontend Features
- **JWT stored in localStorage** — persists across page refreshes
- **SSE streaming** — tokens appear word-by-word as the LLM generates them
- **Sources accordion** — expandable panel showing which document chunks were used
- **Typing indicator** — animated dots while waiting for first token
- **Error display** — stream errors shown as red alert bubbles, not silent failures
- **Copy button** — one-click copy of any AI response

### API Client (`client.js`)
All API calls go through a single `fetch` wrapper that:
- Automatically adds `Authorization: Bearer <token>` header
- Redirects to login on 401
- Handles `similarity_threshold=0.0` for stream queries

---

## 15. Monitoring & Observability

### Prometheus Metrics
Exposed at `http://localhost:8000/metrics`:
- Request count by endpoint and status code
- Request latency (p50, p95, p99)
- Active requests

### Structured Logging (structlog)
Every log line is JSON:
```json
{"event": "Vector search complete", "retrieved": 5, "top_k": 5, "level": "info"}
```
Structured logs are machine-parseable — can be shipped to Elasticsearch, Datadog, etc.

### Health Checks
`/health/ready` checks all dependencies:
- PostgreSQL connectivity (SELECT 1)
- pgvector extension present
- Redis PING
- Ollama/OpenAI model list reachable

Used for Kubernetes readiness probes in production.

---

## 16. Key Problems We Solved

| Problem | Root Cause | Solution |
|---------|-----------|----------|
| CORS error on upload | Frontend port ≠ backend port | CORSMiddleware with allowed origins |
| `ERR_INCOMPLETE_CHUNKED_ENCODING` | Unhandled Python exception killed SSE generator | try/except in generator, yield error as JSON |
| "No answer generated" in UI | Frontend ignored `{"error":...}` SSE events | Added `parsed.error` handler |
| OpenAI 429 quota exceeded | Free tier rate limit | Switched to Ollama (local, free) |
| Dimension mismatch 1536 vs 768 | Different models return different vector sizes | Alembic migration + configurable dimension |
| `get_openai_client` import error | Renamed function during Ollama refactor | Global search-and-replace across all files |
| `host.docker.internal` not resolving | Ollama on host, API in Docker container | `extra_hosts: host-gateway` in docker-compose |
| `USE_OLLAMA` not picked up | `.env` had only OpenAI settings; compose env overriding | Added Ollama settings to `.env` directly |
| Alembic `DuplicateTable` error | Migration tried to create already-existing tables | `alembic stamp 0002` to sync state |

---

## 17. Interview Q&A — Cheat Sheet

**Q: What is RAG and why is it better than plain LLMs?**
> RAG = Retrieval-Augmented Generation. Instead of asking an LLM to answer from its training data (which can be outdated or wrong), we first retrieve the most relevant chunks from our own documents, inject them into the prompt as context, and tell the LLM to answer only from that context. This eliminates hallucinations for domain-specific questions and lets you work with private data.

**Q: How does vector similarity search work?**
> We convert text to high-dimensional float vectors (embeddings) where semantically similar texts are close together in vector space. At query time, we embed the user's question and find document chunks whose vectors have the highest cosine similarity. Cosine similarity = dot product of normalized vectors, ranging from -1 (opposite) to 1 (identical). pgvector's `<=>` operator computes cosine distance efficiently using an IVFFlat approximate nearest-neighbor index.

**Q: Why PostgreSQL for vectors instead of Pinecone or Weaviate?**
> PostgreSQL + pgvector keeps everything in one database — documents, chunks, vectors, and users. No extra service to manage or pay for. For this scale (millions of chunks), pgvector with an IVFFlat index performs comparably to dedicated vector DBs. In production at billions of vectors, you'd consider specialized solutions.

**Q: Explain the streaming implementation.**
> We use Server-Sent Events (SSE) with FastAPI's `StreamingResponse`. The backend is an async Python generator that `yield`s SSE-formatted strings as the LLM produces tokens. The frontend uses the browser's `fetch()` + `ReadableStream` API to read tokens incrementally, updating the React state character-by-character. We chose SSE over WebSockets because streaming is one-directional (server to client) — SSE is simpler and works over plain HTTP.

**Q: How is authentication implemented?**
> JWT (JSON Web Tokens). On login, we issue a short-lived access token (30 min) and a long-lived refresh token (7 days). The access token is sent as a Bearer token in every request header. FastAPI's `Depends(get_current_user)` validates the JWT signature using our secret key. Passwords are hashed with bcrypt — irreversible, salted, and slow by design to resist brute force.

**Q: Explain your caching strategy.**
> Two Redis cache layers. Layer 1 caches embeddings (24h TTL) — the same text phrase always produces the same vector, so we cache it and skip the API call. Layer 2 caches full RAG responses (1h TTL) — if the same question is asked with same parameters, skip the entire pipeline and return instantly. Both layers save latency and reduce LLM API costs.

**Q: Why did you switch from OpenAI to Ollama?**
> OpenAI's free tier has a quota limit — we hit `429 insufficient_quota` during development. Instead of paying for credits just to test, we integrated Ollama, which runs open-source LLMs locally. We used the OpenAI Python SDK pointing at Ollama's OpenAI-compatible API endpoint — zero code change to the core logic, just a different `base_url`. This is good engineering: the LLM provider is an interchangeable dependency.

**Q: What's the significance of the `extra_hosts: host-gateway` in docker-compose?**
> Ollama runs on the host machine (Windows), not inside Docker. By default, containers can't reach `localhost` of the host — they have their own network namespace. `host.docker.internal` is a DNS name Docker Desktop provides on Windows/Mac to bridge this. `host-gateway` is the Linux equivalent. Without it, the container can't make HTTP requests to Ollama at `localhost:11434`.

**Q: Walk me through what happens when a user uploads a PDF.**
> 1. React sends a `multipart/form-data` POST to `/documents/upload`. 2. FastAPI validates the file extension and size. 3. pypdf extracts the full text. 4. tiktoken splits it into 512-token chunks with 50-token overlap. 5. For each chunk, we call Ollama's embedding API → get a 768-dim vector. 6. Each chunk + vector is inserted into `document_chunks` in PostgreSQL. 7. Embeddings are cached in Redis (24h). 8. The full document metadata is saved in the `documents` table. 9. A success response is returned to the frontend.

---

*This document covers the complete lifecycle of the GenAI RAG project — from initial design through all iterations and fixes.*
