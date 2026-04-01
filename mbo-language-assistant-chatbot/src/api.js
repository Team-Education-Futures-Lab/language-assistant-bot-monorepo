// Shared API helper functions for backend interactions

const defaultApiBaseUrl = (() => {
  if (typeof window === 'undefined') {
    return 'http://localhost:5000';
  }

  const protocol = window.location.protocol === 'https:' ? 'https' : 'http';
  const host = window.location.hostname || 'localhost';
  return `${protocol}://${host}:5000`;
})();

const configuredApiBaseUrl =
  process.env.REACT_APP_API_BASE_URL ||
  process.env.VITE_AI_API_BASE_URL ||
  defaultApiBaseUrl;

const buildRealtimeWsUrl = (apiBaseUrl) => {
  try {
    const parsed = new URL(apiBaseUrl);
    parsed.protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
    parsed.pathname = '/ws/realtime-voice';
    parsed.search = '';
    parsed.hash = '';
    return parsed.toString();
  } catch {
    return `${apiBaseUrl.replace(/^http/, 'ws')}/ws/realtime-voice`;
  }
};

export const API_BASE_URL = configuredApiBaseUrl.replace(/\/$/, '');
export const STREAMING_VOICE_WS_URL =
  process.env.REACT_APP_STREAMING_VOICE_WS_URL ||
  buildRealtimeWsUrl(API_BASE_URL);

// Query the backend API with text - with streaming support
export const queryBackendAPI = async (question, onChunk) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/query/text`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question: question,
        enable_tts: false
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.message || `API-fout: ${response.status}`);
    }

    // Read the streaming response line by line
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullAnswer = '';
    let sources = [];
    let contextFound = false;
    let buffer = ''; // Buffer for incomplete lines

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');

      // Keep the last incomplete line in the buffer
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim()) {
          try {
            const parsed = JSON.parse(line);

            if (parsed.error) {
              throw new Error(parsed.error);
            }

            if (parsed.answer) {
              fullAnswer = parsed.answer;
              if (onChunk) onChunk(fullAnswer);
            }
            if (parsed.sources) {
              sources = parsed.sources;
            }
            if (parsed.context_found !== undefined) {
              contextFound = parsed.context_found;
            }
          } catch (e) {
            console.warn('Failed to parse line:', line, e);
          }
        }
      }
    }

    // Process any remaining data in buffer
    if (buffer.trim()) {
      try {
        const parsed = JSON.parse(buffer);
        if (parsed.answer) {
          fullAnswer = parsed.answer;
        }
        if (parsed.sources) {
          sources = parsed.sources;
        }
        if (parsed.context_found !== undefined) {
          contextFound = parsed.context_found;
        }
      } catch (e) {
        console.warn('Failed to parse final buffer:', buffer, e);
      }
    }

    if (fullAnswer) {
      return {
        success: true,
        answer: fullAnswer,
        sources: sources,
        contextFound: contextFound
      };
    } else {
      throw new Error('Geen antwoord ontvangen van de API');
    }
  } catch (error) {
    console.error('API Error:', error);
    return {
      success: false,
      error: error.message
    };
  }
};

// Query the backend API with speech
export const queryBackendAPISpeech = async (audioBlob, options = {}) => {
  try {
    const { enableTts = false } = options;
    const formData = new FormData();
    formData.append('audio', audioBlob, 'audio.wav');
    formData.append('enable_tts', String(enableTts));

    const response = await fetch(`${API_BASE_URL}/api/query/speech`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.message || `API-fout: ${response.status}`);
    }

    const data = await response.json();
    
    if (data.status === 'success') {
      return {
        success: true,
        question: data.user_question,
        answer: data.answer,
        audioAvailable: Boolean(data.audio_available),
        audioBase64: data.audio || null
      };
    } else {
      throw new Error(data.message || 'Onbekende fout van de API');
    }
  } catch (error) {
    console.error('Speech API Error:', error);
    return {
      success: false,
      error: error.message
    };
  }
};

// Synthesize speech audio from text via backend TTS endpoint
export const synthesizeSpeechAudio = async (text) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/tts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text })
    });

    if (!response.ok) {
      let message = `API-fout: ${response.status}`;
      try {
        const errorData = await response.json();
        message = errorData.message || message;
      } catch (e) {
      }
      throw new Error(message);
    }

    const audioBlob = await response.blob();

    if (!audioBlob || audioBlob.size === 0) {
      throw new Error('Lege audio ontvangen van de TTS-service');
    }

    return {
      success: true,
      audioBlob
    };
  } catch (error) {
    console.error('TTS API Error:', error);
    return {
      success: false,
      error: error.message
    };
  }
};

// Start a live STT session
export const startLiveSttSession = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/live-stt/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });

    const data = await response.json();
    if (!response.ok || data.status !== 'success') {
      throw new Error(data.message || 'Kon live STT sessie niet starten');
    }

    return { success: true, sessionId: data.session_id };
  } catch (error) {
    return { success: false, error: error.message };
  }
};

// Send one audio chunk and receive partial transcript
export const sendLiveSttChunk = async (sessionId, audioBlob, isFinal = false) => {
  try {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('is_final', String(isFinal));
    formData.append('audio', audioBlob, `chunk.${audioBlob.type.includes('webm') ? 'webm' : 'wav'}`);

    const response = await fetch(`${API_BASE_URL}/api/live-stt/chunk`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    if (!response.ok || data.status !== 'success') {
      throw new Error(data.message || 'Live STT chunk mislukt');
    }

    return {
      success: true,
      partialText: data.partial_text || '',
      chunkText: data.chunk_text || '',
      finalText: data.final_text || ''
    };
  } catch (error) {
    return { success: false, error: error.message };
  }
};

// Finalize session and get full transcript
export const finalizeLiveSttSession = async (sessionId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/live-stt/finalize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId })
    });

    const data = await response.json();
    if (!response.ok || data.status !== 'success') {
      throw new Error(data.message || 'Live STT sessie finaliseren mislukt');
    }

    return { success: true, finalText: data.final_text || '' };
  } catch (error) {
    return { success: false, error: error.message };
  }
};

// Abort session cleanup
export const abortLiveSttSession = async (sessionId) => {
  try {
    await fetch(`${API_BASE_URL}/api/live-stt/session/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE'
    });
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
};

// ============================================================================
// NEW: Live STT with AI Response Generation (Full End-to-End Streaming)
// ============================================================================

// Send audio chunk and receive BOTH transcript AND Ollama response
export const sendLiveSttChunkWithResponse = async (sessionId, audioBlob, isFinal = false) => {
  try {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('is_final', String(isFinal));
    formData.append('audio', audioBlob, `chunk.${audioBlob.type.includes('webm') ? 'webm' : 'wav'}`);

    const response = await fetch(`${API_BASE_URL}/api/live-stt/chunk-with-response`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    if (!response.ok || data.status !== 'success') {
      throw new Error(data.message || 'Live STT chunk-with-response mislukt');
    }

    return {
      success: true,
      partialText: data.partial_text || '',
      chunkText: data.chunk_text || '',
      fullText: data.full_text || '',
      finalText: data.final_text || '',
      response: data.response || '',
      responseReady: data.response_ready || false,
      responseError: data.response_error || null,
      chunkIndex: data.chunk_index || 0
    };
  } catch (error) {
    return { 
      success: false, 
      error: error.message,
      partialText: '',
      response: '',
      responseReady: false
    };
  }
};
