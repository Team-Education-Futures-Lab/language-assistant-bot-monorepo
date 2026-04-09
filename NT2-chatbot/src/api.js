// Shared API helper functions for backend interactions

const REMOVED_API_MESSAGE = 'Deze API is verwijderd uit api_gateway. Gebruik realtime voice via WebSocket of beschikbare /api/query routes.';

// API Configuration: Base URL is configurable via environment variable
// Set REACT_APP_API_BASE_URL in the .env file (required)
// For development: http://localhost:5000
// For production: https://your-api-domain.com
//
// Gateway route policy:
// - Supported HTTP routes are under /api/query/*
// - Realtime voice WebSocket route: /api/query/ws/realtime-voice

const configuredApiBaseUrl =
  process.env.REACT_APP_API_BASE_URL ||
  process.env.VITE_AI_API_BASE_URL;

const CONFIG_ERROR_MESSAGE =
  'Chatbot API base URL is not configured. Set REACT_APP_API_BASE_URL in the frontend environment.';

if (!configuredApiBaseUrl) {
  console.error(CONFIG_ERROR_MESSAGE);
}

const buildRealtimeWsUrl = (apiBaseUrl) => {
  if (!apiBaseUrl) {
    return '';
  }

  try {
    const parsed = new URL(apiBaseUrl);
    parsed.protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
    parsed.pathname = '/api/query/ws/realtime-voice';
    parsed.search = '';
    parsed.hash = '';
    return parsed.toString();
  } catch {
    return `${apiBaseUrl.replace(/^http/, 'ws')}/api/query/ws/realtime-voice`;
  }
};

export const API_BASE_URL = configuredApiBaseUrl
  ? configuredApiBaseUrl.replace(/\/$/, '')
  : '';

export const STREAMING_VOICE_WS_URL =
  process.env.REACT_APP_STREAMING_VOICE_WS_URL ||
  (API_BASE_URL ? buildRealtimeWsUrl(API_BASE_URL) : '');

const getUnavailableApiMessage = () => {
  if (!API_BASE_URL) {
    return `${CONFIG_ERROR_MESSAGE} ${REMOVED_API_MESSAGE}`;
  }

  return REMOVED_API_MESSAGE;
};

// Query the backend API with text - with streaming support
export const queryBackendAPI = async (question, onChunk) => {
  return { success: false, error: getUnavailableApiMessage() };
};

// Query the backend API with speech
export const queryBackendAPISpeech = async (audioBlob, options = {}) => {
  return { success: false, error: getUnavailableApiMessage() };
};

// Synthesize speech audio from text via backend TTS endpoint
export const synthesizeSpeechAudio = async (text) => {
  return { success: false, error: getUnavailableApiMessage() };
};

// Start a live STT session
export const startLiveSttSession = async () => {
  return { success: false, error: getUnavailableApiMessage() };
};

// Send one audio chunk and receive partial transcript
export const sendLiveSttChunk = async (sessionId, audioBlob, isFinal = false) => {
  return { success: false, error: getUnavailableApiMessage() };
};

// Finalize session and get full transcript
export const finalizeLiveSttSession = async (sessionId) => {
  return { success: false, error: getUnavailableApiMessage() };
};

// Abort session cleanup
export const abortLiveSttSession = async (sessionId) => {
  return { success: false, error: getUnavailableApiMessage() };
};

// ============================================================================
// NEW: Live STT with AI Response Generation (Full End-to-End Streaming)
// ============================================================================

// Send audio chunk and receive BOTH transcript AND Ollama response
export const sendLiveSttChunkWithResponse = async (sessionId, audioBlob, isFinal = false) => {
  return {
    success: false,
    error: getUnavailableApiMessage(),
    partialText: '',
    response: '',
    responseReady: false
  };
};
