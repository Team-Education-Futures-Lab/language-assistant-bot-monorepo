# MBO Language Assistant - Database Manager Service

Flask REST service for subjects, chunks, prompts, runtime settings, and retrieval.

## Current Responsibilities

- Stores and manages subjects, prompts, chunked content, and runtime settings in Supabase.
- Handles file upload/chunking for TXT/PDF learning material.
- Exposes retrieval endpoint with vector search and fallback lexical ranking.
- Enforces CORS allowlist and default request rate limits.

## API Overview

Health:
- GET `/health` (server-only)
- GET `/health/all` (server + dependency status)

Core endpoints:
- GET/POST `/subjects`
- GET/PUT/DELETE `/subjects/{subject_id}`
- POST `/subjects/{subject_id}/upload`
- DELETE `/subjects/{subject_id}/uploads/{upload_name}`
- GET/POST `/subjects/{subject_id}/chunks`
- POST `/subjects/{subject_id}/chunks/bulk`
- GET/PUT/DELETE `/chunks/{chunk_id}`
- GET/POST `/prompts`
- GET `/prompts/active`
- GET/PUT/PATCH/DELETE `/prompts/{prompt_id}`
- GET/POST `/settings`
- GET/PUT/PATCH/DELETE `/settings/{key}`
- POST `/retrieve`

## Environment Variables

Use `.env.example` as template.

Required:

- `SUPABASE_URL`
- `SUPABASE_KEY`

Runtime and networking:

- `APP_ENV=development|production`
- `LOG_LEVEL=INFO|WARNING|ERROR`
- `SERVICE_HOST` and `SERVICE_PORT` (local dev)
- `PORT` (platform-injected in production)

CORS (allow only API Gateway):

- `API_GATEWAY_ORIGIN` (primary allowed origin)
- `API_GATEWAY_ALLOWED_ORIGINS` (optional comma-separated extra allowed origins)

Rate limit and proxy:

- `RATE_LIMIT_DEFAULT` (example: `120 per minute`)
- `USE_PROXY_FIX` and `PROXY_FIX_*`

Production process tuning:

- `WEB_CONCURRENCY`
- `GUNICORN_WORKER_CLASS`
- `GUNICORN_THREADS`
- `GUNICORN_TIMEOUT`
- `GUNICORN_GRACEFUL_TIMEOUT`
- `GUNICORN_KEEPALIVE`
- `GUNICORN_LOG_LEVEL`

## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python database_manager.py
```

## Production Deployment (generic)

Build command:

```bash
pip install -r requirements-prod.txt
```

Start command:

```bash
gunicorn -c gunicorn_conf.py database_manager:app
```

If the platform supports Procfile startup, this repository includes `Procfile` with the same command.

## Notes

- Keep `python database_manager.py` for local dev only.
- Frontends should access these endpoints through the API gateway (`/api/query/*`) instead of calling this service directly.
- In production, set `API_GATEWAY_ORIGIN` to your deployed API gateway domain.
- Keep `SUPABASE_KEY` in platform secret storage.
