# MBO Language Assistant Chatbot

Frontend application for the MBO Language Assistant ecosystem.

This app provides:
- text chat with streamed backend responses
- push-to-talk speech mode
- realtime streaming voice mode over WebSocket

It is built with React + Tailwind (Create React App tooling) and connects to backend services through an API gateway.

## System Overview

The frontend is part of a multi-service setup:
- Chatbot frontend (this repo): UI, microphone capture, playback, and chat state.
- API gateway: routes frontend requests to text, speech, realtime voice, and settings services.
- Realtime voice service: receives audio chunks, handles transcript and assistant response streaming.
- Database manager service: stores and serves runtime settings (used by speech mode).

## Main User Flows

1. Text Chat
- User sends text in the chat input.
- Frontend calls POST /api/query/text on the gateway.
- Response is streamed line-by-line and rendered as the assistant answer.

2. Speech Mode (Spraak)
- User records voice in the speech page.
- Frontend uploads audio to POST /api/query/speech.
- Optional TTS playback can be requested via POST /api/tts.

3. Realtime Voice Chat
- Frontend opens a WebSocket to /ws/realtime-voice.
- Audio is chunked in-browser and streamed continuously.
- UI receives partial transcript, final transcript, assistant text deltas, and assistant audio deltas in near real time.

## Project Structure

- src/App.js: app shell, page switching, chat state, and voice integration.
- src/api.js: HTTP and WebSocket base URL config + backend request helpers.
- src/hooks/useStreamingVoiceChat.js: realtime voice streaming lifecycle and mic/audio playback logic.
- src/components/SpeechPage.js: non-realtime speech capture + TTS playback flow.
- src/components/LiveSpeechPage.js: live STT page and chunk-based streaming controls.
- src/services/ai/: typed AI client/config/workflow helpers.

## Environment Variables

Create a local .env.local file (or .env) at repository root.

```env
REACT_APP_API_BASE_URL=http://localhost:5000
REACT_APP_STREAMING_VOICE_WS_URL=ws://localhost:5000/ws/realtime-voice

# Optional realtime voice tuning
REACT_APP_VOICE_BARGE_IN=false
REACT_APP_VOICE_RESUME_COOLDOWN_MS=800

# Optional AI client config (used by src/services/ai)
VITE_AI_API_BASE_URL=http://localhost:5000
VITE_AI_TRANSCRIBE_ENDPOINT=/ai/transcribe
VITE_AI_GENERATE_ENDPOINT=/ai/generate
VITE_AI_TTS_ENDPOINT=/ai/tts
```

Important:
- Keep provider secrets (for example OPENAI_API_KEY) on backend services only, never in this frontend app.
- Browser-exposed env vars in CRA are bundled client-side, so they are not secret storage.

## Development

Install dependencies:

```bash
npm install
```

Run dev server:

```bash
npm start
```

Open:

```text
http://localhost:3000
```

Run tests:

```bash
npm test
```

Create production build:

```bash
npm run build
```

## Required Backend Endpoints

The frontend expects these gateway endpoints:
- POST /api/query/text
- POST /api/query/speech
- POST /api/tts
- POST /api/live-stt/start
- POST /api/live-stt/chunk
- POST /api/live-stt/chunk-with-response
- POST /api/live-stt/finalize
- DELETE /api/live-stt/session/{session_id}
- WS /ws/realtime-voice

Speech mode also reads VAD settings from the database manager service endpoint:
- GET http://localhost:5004/settings/speech_vad_silence_ms
- GET http://localhost:5004/settings/speech_max_recording_ms

## Security Notes

- No hardcoded API keys or provider secrets were found in the current frontend source.
- Localhost service URLs are present as defaults and are not sensitive.
- Keep all sensitive credentials in backend runtime environment variables.

## Known Notes

- SpeechPage currently uses a direct settings URL (http://localhost:5004) for VAD configuration.
- The app includes a built build/ folder; this can be regenerated with npm run build.

## Tech Stack

- React 19
- Tailwind CSS 3
- TypeScript type support (mixed JS/TS project)
- Create React App (react-scripts 5)
