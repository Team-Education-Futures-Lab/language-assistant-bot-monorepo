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
- `services/mbo-language-assistant-bot-api-gateway`
  - Single entry point for frontend requests
  - Routes requests to downstream services
- `services/mbo-language-assistant-bot-database-manager`
  - CRUD and management APIs for subjects/chunks/settings
  - Connects to Supabase/PostgreSQL
- `services/mbo-language-assistant-bot-realtime-voice-service`
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

## Repository Scope

This monorepo intentionally tracks the chatbot, dashboard, selected backend services, and Nx root workspace files.
Other experimental or non-target folders are excluded through the root `.gitignore` policy.
