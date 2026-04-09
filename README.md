# MBO Language Assistant Monorepo

This repository contains an Nx-based monorepo for an MBO-focused language assistant platform.

The system combines:
- a student-facing chatbot frontend
- a teacher/admin dashboard
- Python microservices for API routing, retrieval, settings/data management, and realtime voice
- a shared root workspace for orchestration and project configuration

## What The System Does

The platform helps students practice and get support with course-related language questions using text and voice.

Core capabilities:
- Text chat workflow from browser to backend services
- Speech input workflow (recorded audio to response)
- Realtime voice conversation over WebSocket with partial transcripts and streamed assistant output
- Course material retrieval from a Supabase/PostgreSQL backend
- Dashboard-driven management of subjects, chunks, and runtime settings

## Monorepo Structure (Tracked Projects)

### Frontend apps
- `mbo-language-assistant-chatbot`
  - React app for students
  - Supports text chat, speech mode, and realtime voice mode
- `mbo-language-assistant-dashboard`
  - React dashboard for teachers/admins
  - Manages subjects and content chunks through service APIs

### Backend services
- `services/api-gateway`
  - Single entry point for frontend requests
  - Routes requests to downstream services
- `services/database-manager`
  - CRUD and management APIs for subjects/chunks/settings
  - Connects to Supabase/PostgreSQL
- `services/openai-service`
  - WebSocket bridge for live audio/transcript/assistant streaming
  - Integrates with OpenAI realtime flow
- `services/mbo-language-assistant-bot-retrieve-service`
  - Retrieves relevant context chunks for user questions

### Workspace root (Nx)
- `nx.json`, `package.json`, `project.json`
  - Define workspace behavior, tasks, and project-level tooling

## High-Level Request Flow

1. User interacts with chatbot UI (text or voice).
2. Frontend sends requests to API Gateway.
3. Gateway forwards to relevant service(s): retrieve, realtime voice, or data/settings manager.
4. Services fetch context and process responses.
5. Response is streamed or returned back to the frontend UI.

## Technology Snapshot

- Frontend: React + Tailwind CSS
- Backend: Python microservices (Flask-style service pattern)
- Data: Supabase/PostgreSQL (course subjects/chunks/settings)
- Orchestration: Nx workspace + per-project package/project configs

## Security And Configuration

- Runtime secrets must stay in local environment files only (`.env`), never source files.
- The root `.gitignore` is configured to exclude secret-bearing env files and non-tracked folders.
- Keep API keys and database credentials on backend runtime environments only.

## Quick Orientation

- Start with `services/README.md` for backend architecture and service-level setup.
- Use `mbo-language-assistant-chatbot/README.md` for frontend behavior and endpoint expectations.
- Use `mbo-language-assistant-dashboard/README.md` for admin/dashboard capabilities.

## Start Development With Nx (Step By Step)

Run everything from the repository root (`testing`).

1. Install root dependencies (Nx and workspace tooling).

```bash
npm install
```

2. Install frontend dependencies.

```bash
npm --prefix mbo-language-assistant-chatbot install
npm --prefix mbo-language-assistant-dashboard install
```

3. Prepare Python services (first time only).

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r services/api-gateway/requirements.txt
pip install -r services/database-manager/requirements.txt
pip install -r services/openai-service/requirements.txt
```

4. Start the full dev stack with Nx.

```bash
npm run dev-all
```

This starts:
- chatbot frontend (`mbo-chatbot-frontend:serve`) on port 3000
- dashboard frontend (`mbo-dashboard-frontend:serve`) on port 3001
- api gateway (`api-gateway:serve`) on port 5000
- database manager (`database-manager:serve`) on port 5004
- realtime voice service (`realtime-voice-service:serve`) on port 5005

5. Stop all dev services.

```bash
npm run stop-all
```

Optional: run a single project with Nx.

```bash
npx nx run mbo-chatbot-frontend:serve
npx nx run mbo-dashboard-frontend:serve
npx nx run api-gateway:serve
npx nx run database-manager:serve
npx nx run realtime-voice-service:serve
```

## Repository Scope

This monorepo intentionally tracks the chatbot, dashboard, selected backend services, and Nx root workspace files.
Other experimental or non-target folders are excluded through the root `.gitignore` policy.
