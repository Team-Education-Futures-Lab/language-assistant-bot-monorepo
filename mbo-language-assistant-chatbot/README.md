# MBO Language Assistant Chatbot

Frontend chat client for the NT2 assistant.

## Current Architecture

- This app talks to the API gateway only.
- Gateway base URL is configured by `REACT_APP_API_BASE_URL`.
- Realtime voice uses WebSocket via gateway route `/api/query/ws/realtime-voice`.
- The logo/home button in the sidebar returns to the main chat page.

## Key Flows

1. Chat page
- New/selected conversations are managed in `src/App.js`.
- The "NT2 Chatbot" logo button navigates to the main chat page state.

2. Realtime voice page
- `src/hooks/useStreamingVoiceChat.js` streams microphone chunks to gateway WebSocket.
- Incoming transcript/audio events are rendered live in the UI.

3. Legacy speech/text API helpers
- `src/api.js` keeps legacy HTTP speech/text helpers as disabled stubs and returns a clear message.
- Active path is realtime voice over WebSocket.

## Environment Variables

Use `.env.example` as template.

Required:

```env
REACT_APP_API_BASE_URL=http://localhost:5000
```

Optional:

```env
REACT_APP_STREAMING_VOICE_WS_URL=ws://localhost:5000/api/query/ws/realtime-voice
VITE_AI_API_BASE_URL=http://localhost:5000
```

Notes:

- Do not place provider secrets in frontend env files.
- If `REACT_APP_API_BASE_URL` is missing, the app now fails gracefully with a clear error message from `src/api.js`.

## Local Development

```bash
npm install
npm start
```

Default dev URL: `http://localhost:3000`

## Build

```bash
npm run build
```

## Backend Dependencies

Expected gateway routes used by this frontend:

- `GET /api/query/health`
- `WS /api/query/ws/realtime-voice`
- `GET /api/query/settings/{key}` (used by speech/settings reads)

## Tech Stack

- React + Create React App
- Tailwind CSS
- Mixed JS/TS utilities
