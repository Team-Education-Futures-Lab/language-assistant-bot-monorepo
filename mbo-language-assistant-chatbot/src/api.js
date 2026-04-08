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

const buildRealtimeWsUrl = (apiBaseUrl) => {
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

export const API_BASE_URL = configuredApiBaseUrl.replace(/\/$/, '');
export const STREAMING_VOICE_WS_URL =
  process.env.REACT_APP_STREAMING_VOICE_WS_URL ||
  buildRealtimeWsUrl(API_BASE_URL);

// Query the backend API with text - with streaming support
export const queryBackendAPI = async (question, onChunk) => {
  return { success: false, error: REMOVED_API_MESSAGE };
};

// Query the backend API with speech
export const queryBackendAPISpeech = async (audioBlob, options = {}) => {
  return { success: false, error: REMOVED_API_MESSAGE };
};

// Synthesize speech audio from text via backend TTS endpoint
export const synthesizeSpeechAudio = async (text) => {
  return { success: false, error: REMOVED_API_MESSAGE };
};

// Start a live STT session
export const startLiveSttSession = async () => {
  return { success: false, error: REMOVED_API_MESSAGE };
};

// Send one audio chunk and receive partial transcript
export const sendLiveSttChunk = async (sessionId, audioBlob, isFinal = false) => {
  return { success: false, error: REMOVED_API_MESSAGE };
};

// Finalize session and get full transcript
export const finalizeLiveSttSession = async (sessionId) => {
  return { success: false, error: REMOVED_API_MESSAGE };
};

// Abort session cleanup
export const abortLiveSttSession = async (sessionId) => {
  return { success: false, error: REMOVED_API_MESSAGE };
};

// ============================================================================
// NEW: Live STT with AI Response Generation (Full End-to-End Streaming)
// ============================================================================

// Send audio chunk and receive BOTH transcript AND Ollama response
export const sendLiveSttChunkWithResponse = async (sessionId, audioBlob, isFinal = false) => {
  return {
    success: false,
    error: REMOVED_API_MESSAGE,
    partialText: '',
    response: '',
    responseReady: false
  };
};
