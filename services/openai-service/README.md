# MBO Language Assistant - Realtime Voice Service

WebSocket backend for browser voice conversations through the API gateway.

## Current Responsibilities

- Maintains a full-duplex WebSocket session between the gateway and OpenAI Realtime.
- Streams transcription and assistant audio/text events back through the gateway.
- Enriches responses with retrieval context from the database manager.
- Exposes health endpoints for service checks.

## API Surface

HTTP endpoints:
- GET `/`
- GET `/health`

WebSocket endpoint:
- WS `/ws/realtime-voice`

## Environment Variables

Use `.env.example` as template.

Important keys:

- `APP_ENV=development|production`
- `LOG_LEVEL=INFO|WARNING|ERROR`
- `SERVICE_HOST` and `SERVICE_PORT` (local dev)
- `PORT` (platform-injected in production)
- `API_GATEWAY_ORIGIN` (primary allowed origin)
- `API_GATEWAY_ALLOWED_ORIGINS` (optional comma-separated extra origins)
- `RATE_LIMIT_DEFAULT` (example: `120 per minute`)
- `USE_PROXY_FIX` and `PROXY_FIX_*`
- `OPENAI_API_KEY`
- `OPENAI_REALTIME_MODEL`
- `OPENAI_REALTIME_TRANSCRIPTION_MODEL`
- `OPENAI_REALTIME_VOICE`
- `OPENAI_REALTIME_WS_URL`
- `OPENAI_REALTIME_API_BASE`
- `OPENAI_REALTIME_USE_EPHEMERAL_TOKEN`
- `DATABASE_MANAGER_URL`
- `OPENAI_WS_TIMEOUT_SEC`
- `OPENAI_WS_PING_INTERVAL_SEC`
- `WEB_CONCURRENCY`
- `GUNICORN_WORKER_CLASS`
- `GUNICORN_TIMEOUT`
- `GUNICORN_GRACEFUL_TIMEOUT`
- `GUNICORN_KEEPALIVE`
- `GUNICORN_LOG_LEVEL`

## Local Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python realtime_voice_service.py
```

## Production Deployment (generic)

Build command:

```bash
pip install -r requirements-prod.txt
```

Start command:

```bash
gunicorn -c gunicorn_conf.py realtime_voice_service:app
```

If the platform supports Procfile startup, this repository includes `Procfile` with the same command.

## Notes

- Keep `python realtime_voice_service.py` for local development only.
- In production, set `API_GATEWAY_ORIGIN` to your deployed API gateway domain.
- Keep `OPENAI_API_KEY` in platform secret storage.
