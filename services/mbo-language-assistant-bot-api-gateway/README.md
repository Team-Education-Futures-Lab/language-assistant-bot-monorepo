# MBO Language Assistant - API Gateway

Central backend gateway for the MBO Language Assistant services.

This service is the single entry point for frontend clients and proxies requests to the appropriate microservices:
- text input service
- speech input service
- retrieve service
- database manager service
- realtime voice service

## What This Service Does

- Exposes unified HTTP endpoints for text, speech, TTS, subjects, prompts, settings, and live STT.
- Streams text-query responses back to the client as NDJSON.
- Proxies WebSocket traffic for realtime voice between frontend and realtime voice service.
- Provides service-level health checks.

## Project Files

- api_gateway.py: main Flask gateway with HTTP and WebSocket proxy routes.
- requirements.txt: Python dependencies.
- Dockerfile: container image build file.
- .env.example: local configuration template.
- .gitignore: ignores environment files and runtime artifacts.

## Environment Variables

Create a local .env file in this folder.

Example values:

```env
GATEWAY_HOST=localhost
GATEWAY_PORT=5000

TEXT_SERVICE_URL=http://localhost:5001
SPEECH_SERVICE_URL=http://localhost:5002
RETRIEVE_SERVICE_URL=http://localhost:5003
DATABASE_SERVICE_URL=http://localhost:5004

REALTIME_VOICE_SERVICE_URL=http://localhost:5005
REALTIME_VOICE_SERVICE_WS_URL=ws://localhost:5005/ws/realtime-voice

GATEWAY_BACKEND_WS_TIMEOUT_SEC=180
GATEWAY_BACKEND_WS_PING_INTERVAL_SEC=0
```

## HTTP Endpoints

Health:
- GET /
- GET /health

Query:
- POST /api/query/text
- POST /api/query/speech
- POST /api/tts
- POST /api/query

Subjects and chunks:
- GET, POST /api/subjects
- GET, PUT, DELETE /api/subjects/{subject_id}
- POST /api/subjects/{subject_id}/upload
- DELETE /api/subjects/{subject_id}/uploads/{upload_name}
- GET, POST /api/subjects/{subject_id}/chunks

Prompts:
- GET, POST /api/prompts
- GET /api/prompts/active
- GET, PUT, DELETE /api/prompts/{prompt_id}

Settings:
- GET, POST /api/settings
- GET, DELETE /api/settings/{key}

Live STT:
- POST /api/live-stt/start
- POST /api/live-stt/chunk
- POST /api/live-stt/chunk-with-response
- POST /api/live-stt/finalize
- DELETE /api/live-stt/session/{session_id}

## WebSocket Endpoint

- WS /ws/realtime-voice

Behavior:
- Accepts frontend WebSocket connection.
- Opens backend WebSocket connection to realtime voice service.
- Forwards messages bidirectionally.
- Optional keepalive pings controlled by GATEWAY_BACKEND_WS_PING_INTERVAL_SEC.

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

3. Run the gateway.

```bash
python api_gateway.py
```

Default URL:

```text
http://localhost:5000
```

## Docker

Build image:

```bash
docker build -t mbo-api-gateway .
```

Run container:

```bash
docker run --rm -p 5000:5000 --env-file .env mbo-api-gateway python api_gateway.py
```

## Security Notes

- No hardcoded API keys were found in current source or .env.example.
- Keep secrets in local .env only.
- This repo currently ignores both .env and .env.example by default.
