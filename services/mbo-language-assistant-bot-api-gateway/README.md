# MBO Language Assistant - API Gateway

Central HTTP and WebSocket gateway for frontend clients.

## Current Responsibilities

- Proxies subject, chunk, prompt, settings, and retrieve requests to the database manager service.
- Proxies realtime voice WebSocket traffic to the realtime voice service.
- Exposes health endpoints for gateway-only and full dependency checks.
- Enforces CORS allowlist and default request rate limiting.

## Runtime Endpoints

- GET `/api/query/health/gateway`
- GET `/api/query/health`
- GET `/api/query/health/all` (alias)
- GET/POST `/api/query/subjects`
- GET/PUT/DELETE `/api/query/subjects/{subject_id}`
- POST `/api/query/subjects/{subject_id}/upload`
- DELETE `/api/query/subjects/{subject_id}/uploads/{upload_name}`
- GET/POST `/api/query/subjects/{subject_id}/chunks`
- GET/PUT/DELETE `/api/query/chunks/{chunk_id}`
- GET/POST `/api/query/prompts`
- GET `/api/query/prompts/active`
- GET/PUT/DELETE `/api/query/prompts/{prompt_id}`
- GET/POST `/api/query/settings`
- GET/PUT/PATCH/DELETE `/api/query/settings/{key}`
- POST `/api/query/retrieve`
- WS `/api/query/ws/realtime-voice`

## Environment Variables

Use [.env.example](.env.example) as template.

Important keys:

- `APP_ENV=development|production`
- `LOG_LEVEL=INFO|WARNING|ERROR`
- `GATEWAY_HOST` and `GATEWAY_PORT` (for local dev)
- `PORT` (platform-injected port in production)
- `DATABASE_SERVICE_URL`
- `REALTIME_VOICE_SERVICE_URL`
- `REALTIME_VOICE_SERVICE_WS_URL`
- `FRONTEND_CHATBOT_ORIGIN`
- `FRONTEND_DASHBOARD_ORIGIN`
- `FRONTEND_ALLOWED_ORIGINS` (comma-separated extra origins)
- `RATE_LIMIT_DEFAULT` (example: `120 per minute`)
- `USE_PROXY_FIX` and `PROXY_FIX_*` (for reverse-proxy deployments)
- `WEB_CONCURRENCY` and `GUNICORN_*` (production process tuning)

## Local Development (unchanged)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python api_gateway.py
```

## Production Deployment (recommended)

1. Install production dependencies:

```bash
pip install -r requirements-prod.txt
```

2. Start with a production WSGI server (includes WebSocket worker):

```bash
gunicorn -c gunicorn_conf.py api_gateway:app
```

If the platform supports Procfile-based startup, this repository already includes [Procfile](Procfile) with the same command.

## Generic Platform Setup

Use these values in any host platform UI:

- Build command: `pip install -r requirements-prod.txt`
- Start command: `gunicorn -c gunicorn_conf.py api_gateway:app`

Required environment variables:

- `APP_ENV=production`
- `DATABASE_SERVICE_URL`
- `REALTIME_VOICE_SERVICE_URL`
- `REALTIME_VOICE_SERVICE_WS_URL`
- `FRONTEND_CHATBOT_ORIGIN`
- `FRONTEND_DASHBOARD_ORIGIN`

Usually auto-provided by platform:

- `PORT`

Optional but recommended:

- `FRONTEND_ALLOWED_ORIGINS`
- `RATE_LIMIT_DEFAULT`
- `USE_PROXY_FIX=true`
- `WEB_CONCURRENCY`
- `GUNICORN_TIMEOUT`
- `GUNICORN_GRACEFUL_TIMEOUT`
- `GUNICORN_KEEPALIVE`
- `GUNICORN_LOG_LEVEL`

## Notes For Hosting Platforms

- Do not run `python api_gateway.py` in production.
- Keep `python api_gateway.py` for local development only.
- Make sure the platform domain(s) are added to CORS variables.
- Ensure `DATABASE_SERVICE_URL` and `REALTIME_VOICE_SERVICE_URL` are reachable from the deployed gateway.
