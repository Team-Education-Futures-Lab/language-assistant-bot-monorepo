# MBO Language Assistant - Retrieve Service

Dedicated retrieval microservice for returning relevant learning-context chunks.

This service supports two retrieval paths:
- Vector retrieval from PGVector (primary)
- Lexical fallback retrieval through the Database Manager REST API (fallback)

## What This Service Does

- Accepts a user question and returns ranked context chunks.
- Formats context for direct use in LLM prompts.
- Includes source filenames and chunk counts in responses.
- Automatically falls back when vector DB is unavailable.

## Service Architecture

Input:
- HTTP POST request with a question and optional k value.

Primary mode:
- Uses sentence-transformers embeddings with PGVector similarity search.

Fallback mode:
- Calls Database Manager endpoints to collect chunks across subjects.
- Applies lexical token-overlap ranking.

Output:
- Structured JSON with context_found, formatted_context, sources, and chunk_count.

## Endpoints

- GET /
- GET /health
- POST /retrieve

### POST /retrieve payload

```json
{
  "question": "Wat is de juiste procedure voor ...?",
  "k": 10
}
```

### POST /retrieve response (success)

```json
{
  "status": "success",
  "question": "...",
  "context_found": true,
  "formatted_context": "--- Context from ...",
  "sources": ["document1.pdf", "slides_week2.txt"],
  "chunk_count": 5,
  "service": "Retrieve Service",
  "mode": "vector"
}
```

## Environment Variables

Use local .env file in this directory.

```env
SERVICE_HOST=localhost
SERVICE_PORT=5003
DATABASE_MANAGER_URL=http://localhost:5004

DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=school-db
COLLECTION_NAME=course_materials_vectors
```

Notes:
- .env is ignored by git via .gitignore.
- .env.example is loaded as fallback defaults if present.

## Local Development

1. Create and activate virtual environment.

```bash
python -m venv .venv
# PowerShell
.venv\Scripts\Activate.ps1
# CMD
.venv\Scripts\activate.bat
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Run the service.

```bash
python retrieve_service.py
```

Default base URL:

```text
http://localhost:5003
```

## Docker

Build image:

```bash
docker build -t mbo-retrieve-service .
```

Run container:

```bash
docker run --rm -p 5003:5003 --env-file .env mbo-retrieve-service python retrieve_service.py
```

## Health Behavior

GET /health reports service health as:
- ok: vector DB connected OR fallback database manager reachable
- degraded: neither vector DB nor fallback reachable

## Dependencies

See requirements.txt for full list, including:
- flask
- flask-cors
- langchain-huggingface
- langchain-postgres
- sentence-transformers
- psycopg2-binary

## Security Notes

- Keep DB credentials only in .env.
- Do not commit credential-bearing env files.
- This repo ignores .env and .env.example by default.
