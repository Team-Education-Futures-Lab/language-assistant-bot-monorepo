# MBO Language Assistant - Realtime Voice Service

Realtime voice backend service for browser-based Dutch conversation practice.

Flow:
- Browser sends microphone audio chunks via WebSocket.
- API gateway proxies the socket to this service.
- This service streams audio to OpenAI Realtime, receives transcript and assistant output, and streams text/audio events back to the browser.
- It optionally enriches responses with retrieved context from the database manager service.

## What This Service Does

- Maintains a full-duplex WebSocket session between browser clients and OpenAI Realtime.
- Uses server-side VAD events to detect speech start/stop.
- Emits live transcription deltas and final transcripts.
- Emits assistant text deltas/final text and audio deltas.
- Performs retrieval against stored chunks through the database manager and injects context into the conversation when available.

## API Surface

HTTP endpoints:
- GET /
- GET /health

WebSocket endpoint:
- WS /ws/realtime-voice

Incoming browser message types:
- session.start
- audio.chunk
- recording.stop
- session.close

Outgoing browser message types (examples):
- session.started
- session.ready
- speech.started
- speech.stopped
- transcript.delta
- transcript.final
- retrieval.context
- assistant.response.started
- assistant.message.started
- assistant.text.delta
- assistant.text.final
- assistant.audio.delta
- assistant.audio.done
- response.done
- error

## Project Files

- realtime_voice_service.py: main Flask + Flask-Sock service logic.
- requirements.txt: Python dependencies.
- Dockerfile: container build definition.
- .env.example: non-secret environment template.
- .gitignore: prevents committing local secrets and runtime artifacts.

## Environment Variables

Create a local .env file in this directory:

```env
SERVICE_HOST=localhost
SERVICE_PORT=5005
LOG_LEVEL=INFO

OPENAI_API_KEY=your_openai_api_key_here
OPENAI_REALTIME_MODEL=gpt-4o-mini-realtime-preview
OPENAI_REALTIME_TRANSCRIPTION_MODEL=whisper-1
OPENAI_REALTIME_LANGUAGE=nl
OPENAI_REALTIME_VOICE=alloy
OPENAI_REALTIME_WS_URL=wss://api.openai.com/v1/realtime
OPENAI_REALTIME_API_BASE=https://api.openai.com/v1
OPENAI_REALTIME_USE_EPHEMERAL_TOKEN=false

OPENAI_REALTIME_SYSTEM_PROMPT=Je bent een behulpzame taalassistent voor MBO-studenten. Reageer altijd in de taal die de gebruiker spreekt. Houd je antwoorden beknopt en duidelijk.

OPENAI_REALTIME_VAD_THRESHOLD=0.5
OPENAI_REALTIME_VAD_SILENCE_MS=500
OPENAI_REALTIME_PREFIX_PADDING_MS=300

DATABASE_MANAGER_URL=http://localhost:5004
RETRIEVE_TOP_K=5
RETRIEVE_TIMEOUT_SEC=4

OPENAI_WS_TIMEOUT_SEC=180
OPENAI_WS_PING_INTERVAL_SEC=0
```

Notes:
- OPENAI_API_KEY is required for realtime voice streaming.
- Keep .env local only. This repo ignores .env by default.

## Local Run

1. Create and activate a virtual environment.

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

3. Start the service.

```bash
python realtime_voice_service.py
```

Default address:

```text
http://localhost:5005
```

## Docker

Build:

```bash
docker build -t mbo-realtime-voice-service .
```

Run:

```bash
docker run --rm -p 5005:5005 --env-file .env mbo-realtime-voice-service python realtime_voice_service.py
```

## Health Check

GET /health returns:
- status: ok when OPENAI_API_KEY is configured, otherwise degraded.
- model and voice currently in use.

## Security Notes

- Do not store real API keys in .env.example or source code.
- Use .env (ignored by Git) for secrets.
- Rotate compromised keys immediately if they were ever committed.

## Operational Notes

- The service can optionally use ephemeral OpenAI client secrets when OPENAI_REALTIME_USE_EPHEMERAL_TOKEN=true.
- Retrieval context is pulled from the database manager by scanning subjects and chunks, then ranked by token overlap.
- CORS is currently open for all origins; tighten it for production deployments.
