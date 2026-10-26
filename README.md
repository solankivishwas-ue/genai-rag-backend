# GenAI RAG Backend

A FastAPI backend for retrieval-augmented generation (RAG). You upload documents, it splits them into chunks, stores an embedding for each chunk in Postgres with pgvector, and answers questions using the chunks closest to the question. It can use OpenAI or a local Ollama model. A small React chat app is included.

## Why I built it

TODO: write 2 or 3 sentences in your own words.

## Tech stack

- Python 3.10, FastAPI, SQLAlchemy (async), Alembic
- PostgreSQL 16 with pgvector
- Redis (caches embeddings and query results)
- OpenAI or Ollama for embeddings and chat, through the OpenAI Python client
- JWT login with python-jose and passlib
- Prometheus metrics (`/metrics`), structlog logging
- React 19 and Vite for the frontend
- Docker Compose

## How to run it

Everything below ran on Windows with Docker Desktop, unless marked TODO.

### 1. Configure

```bash
cp .env.example .env
```

TODO: I did not run this step because a `.env` already existed. Confirm it works on a clean clone.

### 2. Start the API, Postgres and Redis

```bash
docker compose up -d --build db redis api
curl http://localhost:8000/api/v1/health/ready
```

`docker-compose.yml` sets `USE_OLLAMA=true` for the `api` service, and that value overrides `.env`. The API expects Ollama at `http://host.docker.internal:11434`. Without Ollama running, `/health/ready` returns `"status": "degraded"` and embeddings and answers fail.

The API is then at http://localhost:8000, with Swagger docs at `/docs`.

### 3. Run without an LLM (mock mode)

With `MOCK_EMBEDDINGS=true` the app makes fake, hash-based embeddings and returns a placeholder answer instead of calling a model. This is for testing the plumbing only. Retrieval only matches text that is almost identical to a stored chunk.

Save this as `override.yml` outside the repo:

```yaml
services:
  api:
    environment:
      USE_OLLAMA: "true"
      MOCK_EMBEDDINGS: "true"
```

Then:

```bash
docker compose -f docker-compose.yml -f override.yml up -d --build db redis api
```

`USE_OLLAMA` stays `true` here on purpose. The `document_chunks.embedding` column is `vector(768)` after Alembic migration 0003, and the Ollama setting produces 768-dimension vectors.

### 4. Try it

```bash
B=http://localhost:8000/api/v1; H='Content-Type: application/json'

curl -X POST $B/auth/register -H "$H" \
  -d '{"email":"demo@example.com","password":"Demo-Passw0rd!","full_name":"Demo User"}'

curl -X POST $B/auth/login -H "$H" \
  -d '{"email":"demo@example.com","password":"Demo-Passw0rd!"}'
# copy access_token from the response into TOKEN

curl -X POST $B/documents/ -H "$H" -H "Authorization: Bearer $TOKEN" \
  -d '{"title":"Demo","content":"Your text here."}'

curl -X POST $B/documents/query -H "$H" -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"Your question here","similarity_threshold":0.5}'
```

### 5. Run the tests

```bash
pip install -r requirements.txt
pytest
```

### 6. Frontend

```bash
cd frontend
npm ci
npm run build
```

`npm run dev` starts the Vite dev server on port 5173 and proxies `/api` to `http://localhost:8000`. TODO: I built the frontend but did not run the dev server or click through the chat. Check it before publishing this section.

### Other setups

- TODO: real answers with Ollama. Run `ollama pull nomic-embed-text` and `ollama pull llama3.2` on the host, then start the stack as in step 2. Not tested, because Ollama was not installed when I checked.
- TODO: OpenAI. I did not test this. The code supports `USE_OLLAMA=false` with an `OPENAI_API_KEY`, but the compose file forces `USE_OLLAMA=true`, and the database column is sized for 768-dimension vectors while OpenAI's `text-embedding-3-small` returns 1536. See "What I'd improve next".

TODO: add the live frontend URL only once a backend is hosted for it.

## Main endpoints

All paths start with `/api/v1`. The auth and documents endpoints need a bearer token, except register, login and refresh.

**Health**
- `GET /health` basic status
- `GET /health/live` liveness
- `GET /health/ready` checks the database, pgvector, Redis and the LLM provider

**Auth**
- `POST /auth/register`
- `POST /auth/login` returns an access token and a refresh token
- `POST /auth/refresh` returns a new access token
- `GET /auth/me` returns the current user

**Documents**
- `POST /documents/` ingest text from a JSON body
- `POST /documents/upload` ingest a PDF, DOCX or TXT file (optional `title` query parameter)
- `POST /documents/ingest-async` same as the JSON ingest, but runs as a background task and returns 202
- `GET /documents/` list documents, with `page` and `page_size`
- `GET /documents/{id}` get one document
- `DELETE /documents/{id}` delete a document and its chunks
- `POST /documents/query` ask a question, get one JSON response with sources
- `POST /documents/query/stream` same question, answer streamed as server-sent events

**Other**
- `GET /metrics` Prometheus metrics
- Prometheus and Grafana are in `docker-compose.yml` under the `monitoring` profile (`docker compose --profile monitoring up -d`). TODO: I did not start them.

## What I'd improve next

- Tests cover only the root, health and OpenAPI endpoints (4 tests in `tests/test_health.py`). There are no tests for auth, ingestion or querying.
- There is no check of answer quality, such as a set of questions with known answers.
- OpenAI mode does not work on a fresh database. `migrations/init.sql` creates `vector(1536)`, Alembic migration 0003 changes it to `vector(768)`, and `docker-compose.yml` hardcodes `USE_OLLAMA=true`. Switching providers needs a column resize and re-embedding.
- The Redis embedding cache key is a hash of the text only. It does not include the model or dimension, so a cached vector from one provider can be reused after switching to another. I hit this and had to flush Redis.
- Documents have no owner. Any logged-in user can list, read, query and delete every document.
- `/documents/ingest-async` runs in a FastAPI background task and only logs failures. The caller has no way to check whether ingestion worked.
- The `api` container runs `uvicorn --reload`, and compose mounts `./app` into it. That suits development, not a deployed setup.
- Unhandled errors return a generic 500 message, and I could not find the traceback in `docker compose logs`, which made debugging slow.
- `SECRET_KEY` has a default value. The app logs a warning at startup when `APP_ENV=production` and the default is still in use, but it does not refuse to start.
- There is no rate limiting.
