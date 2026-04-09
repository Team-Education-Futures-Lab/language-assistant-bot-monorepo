# MBO Language Assistant Services

This folder contains the active Python backend services for the monorepo.

## Current Service Layout

- [api-gateway](api-gateway)
  - Central HTTP and WebSocket entry point for the webapps.
  - Proxies API requests to downstream services.
- [database-manager](database-manager)
  - CRUD and retrieval service for subjects, chunks, prompts, and settings.
  - Connects to Supabase/PostgreSQL.
- [openai-service](openai-service)
  - Realtime voice backend for browser audio streaming and OpenAI Realtime.
  - Uses the database manager for retrieval context and runtime settings.
- [mbo-language-assistant-bot-retrieve-service](mbo-language-assistant-bot-retrieve-service)
  - Standalone retrieval helper service kept for compatibility and experiments.

## Active Request Flow

1. `NT2-chatbot` and `dashboard` send requests to `api-gateway`.
2. `api-gateway` forwards data requests to `database-manager` and realtime voice traffic to `openai-service`.
3. `openai-service` reads retrieval context and runtime settings from `database-manager`.
4. Responses are streamed or returned to the frontend through the gateway.

## Development Setup

Run commands from the repository root (`testing`) whenever possible.

### Install dependencies

```bash
npm install
npm --prefix NT2-chatbot install
npm --prefix dashboard install
```

### Prepare Python services

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r services/api-gateway/requirements.txt
pip install -r services/database-manager/requirements.txt
pip install -r services/openai-service/requirements.txt
pip install -r services/mbo-language-assistant-bot-retrieve-service/requirements.txt
```

### Start everything with Nx

```bash
npm run dev-all
```

This starts:

- chatbot frontend: `mbo-chatbot-frontend:serve`
- dashboard frontend: `mbo-dashboard-frontend:serve`
- API gateway: `api-gateway:serve`
- database manager: `database-manager:serve`
- realtime voice service: `realtime-voice-service:serve`

### Stop all dev services

```bash
npm run stop-all
```

## Individual Service Paths

- `services/api-gateway/api_gateway.py`
- `services/database-manager/database_manager.py`
- `services/openai-service/realtime_voice_service.py`
- `services/mbo-language-assistant-bot-retrieve-service/retrieve_service.py`

## Notes

- Frontends should use the API gateway, not the backend services directly.
- Keep secrets in each service `.env` file, not in source code.
- The retrieve service is not part of the main gateway-first runtime, but it remains in the workspace for compatibility.