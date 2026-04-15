import { useEffect, useRef, useState } from 'react';
import { STREAMING_VOICE_WS_URL } from '../api';

const TARGET_SAMPLE_RATE = 24000;
const CHUNK_DURATION_MS = 100;
const CHUNK_SAMPLE_COUNT = Math.floor((TARGET_SAMPLE_RATE * CHUNK_DURATION_MS) / 1000);

const parseBooleanEnv = (value, defaultValue = false) => {
  if (value == null || value === '') return defaultValue;
  return ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase());
};

const BARGE_IN_ENABLED = parseBooleanEnv(process.env.REACT_APP_VOICE_BARGE_IN, false);
const RESPONSE_RESUME_COOLDOWN_MS = Number(process.env.REACT_APP_VOICE_RESUME_COOLDOWN_MS || 800);
const VOICE_SPEED_MIN = 0.25;
const VOICE_SPEED_MAX = 1.5;
const DEFAULT_VOICE_SPEED = 1.0;

const clampVoiceSpeed = (value) => {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return DEFAULT_VOICE_SPEED;
  return Math.min(VOICE_SPEED_MAX, Math.max(VOICE_SPEED_MIN, numericValue));
};

const toBase64 = (uint8Array) => {
  let binary = '';
  for (let index = 0; index < uint8Array.length; index += 1) {
    binary += String.fromCharCode(uint8Array[index]);
  }
  return window.btoa(binary);
};

const fromBase64 = (base64Value) => {
  const binary = window.atob(base64Value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
};

const resampleBuffer = (inputSamples, inputRate, targetRate) => {
  if (!inputSamples?.length) return new Float32Array(0);
  if (inputRate === targetRate) return new Float32Array(inputSamples);

  const ratio = inputRate / targetRate;
  const outputLength = Math.max(1, Math.round(inputSamples.length / ratio));
  const output = new Float32Array(outputLength);

  for (let outputIndex = 0; outputIndex < outputLength; outputIndex += 1) {
    const start = Math.floor(outputIndex * ratio);
    const end = Math.min(inputSamples.length, Math.floor((outputIndex + 1) * ratio));
    if (end <= start) {
      output[outputIndex] = inputSamples[start] || 0;
      continue;
    }

    let sum = 0;
    for (let inputIndex = start; inputIndex < end; inputIndex += 1) {
      sum += inputSamples[inputIndex];
    }
    output[outputIndex] = sum / (end - start);
  }

  return output;
};

const float32ToPcm16 = (floatSamples) => {
  const bytes = new Uint8Array(floatSamples.length * 2);
  const view = new DataView(bytes.buffer);

  for (let index = 0; index < floatSamples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, floatSamples[index]));
    view.setInt16(index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }

  return bytes;
};

const pcm16ToFloat32 = (pcmBytes) => {
  const sampleCount = Math.floor(pcmBytes.length / 2);
  const floats = new Float32Array(sampleCount);
  const view = new DataView(pcmBytes.buffer, pcmBytes.byteOffset, pcmBytes.byteLength);

  for (let index = 0; index < sampleCount; index += 1) {
    floats[index] = view.getInt16(index * 2, true) / 32768;
  }

  return floats;
};

export default function useStreamingVoiceChat(callbacks = {}) {
  const callbacksRef = useRef(callbacks);
  const socketRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const captureContextRef = useRef(null);
  const sourceNodeRef = useRef(null);
  const processorRef = useRef(null);
  const sampleBufferRef = useRef([]);
  const playbackContextRef = useRef(null);
  const nextPlaybackTimeRef = useRef(0);
  const shouldCloseAfterResponseRef = useRef(false);
  const assistantSpeakingRef = useRef(false);
  const micPauseUntilRef = useRef(0);
  const micBlockedRef = useRef(false);
  const connectionErrorActiveRef = useRef(false);
  const wsFallbackInProgressRef = useRef(false);
  const responseHasAudioRef = useRef(false);
  const playbackDrainTimerRef = useRef(null);
  const playbackSpeedRef = useRef(DEFAULT_VOICE_SPEED);

  const [statusText, setStatusText] = useState('');
  const [liveTranscript, setLiveTranscript] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [awaitingResponse, setAwaitingResponse] = useState(false);
  const [error, setError] = useState('');
  const [playbackSpeed, setPlaybackSpeed] = useState(DEFAULT_VOICE_SPEED);

  useEffect(() => {
    callbacksRef.current = callbacks;
  }, [callbacks]);

  const closeSocket = () => {
    if (socketRef.current) {
      const socket = socketRef.current;
      socketRef.current = null;
      try {
        socket.close();
      } catch (socketError) {
      }
    }
  };

  const stopCapture = () => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current.onaudioprocess = null;
      processorRef.current = null;
    }
    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (captureContextRef.current && captureContextRef.current.state !== 'closed') {
      captureContextRef.current.close().catch(() => {});
      captureContextRef.current = null;
    }
    sampleBufferRef.current = [];
  };

  const resetPlayback = () => {
    if (playbackContextRef.current && playbackContextRef.current.state !== 'closed') {
      playbackContextRef.current.close().catch(() => {});
    }
    playbackContextRef.current = null;
    nextPlaybackTimeRef.current = 0;
  };

  const cleanupAll = () => {
    if (playbackDrainTimerRef.current) {
      clearTimeout(playbackDrainTimerRef.current);
      playbackDrainTimerRef.current = null;
    }
    stopCapture();
    closeSocket();
    resetPlayback();
    shouldCloseAfterResponseRef.current = false;
    assistantSpeakingRef.current = false;
    micPauseUntilRef.current = 0;
    micBlockedRef.current = false;
    responseHasAudioRef.current = false;
    setIsConnecting(false);
    setIsConnected(false);
    setIsRecording(false);
    setAwaitingResponse(false);
  };

  useEffect(() => () => {
    if (playbackDrainTimerRef.current) {
      clearTimeout(playbackDrainTimerRef.current);
      playbackDrainTimerRef.current = null;
    }
    stopCapture();
    closeSocket();
    resetPlayback();
    shouldCloseAfterResponseRef.current = false;
    assistantSpeakingRef.current = false;
    micPauseUntilRef.current = 0;
    micBlockedRef.current = false;
    responseHasAudioRef.current = false;
  }, []);

  const canStreamMicrophoneNow = () => {
    // Hard block always wins while assistant response/audio is active.
    if (micBlockedRef.current) return false;
    if (BARGE_IN_ENABLED) return true;
    if (assistantSpeakingRef.current) return false;
    return Date.now() >= micPauseUntilRef.current;
  };

  const sendJsonMessage = (payload) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify(payload));
  };

  const updatePlaybackSpeed = (nextSpeed) => {
    const normalizedSpeed = clampVoiceSpeed(nextSpeed);
    playbackSpeedRef.current = normalizedSpeed;
    setPlaybackSpeed(normalizedSpeed);

    sendJsonMessage({
      type: 'session.update',
      speed: normalizedSpeed,
    });
  };

  const finalizeMicUnblockAfterPlayback = () => {
    assistantSpeakingRef.current = false;
    micBlockedRef.current = false;
    micPauseUntilRef.current = Date.now() + Math.max(0, RESPONSE_RESUME_COOLDOWN_MS);
    setAwaitingResponse(false);
    setStatusText('Klaar');
    playbackDrainTimerRef.current = null;
  };

  const scheduleMicUnblockAfterPlaybackDrain = () => {
    if (playbackDrainTimerRef.current) {
      clearTimeout(playbackDrainTimerRef.current);
      playbackDrainTimerRef.current = null;
    }

    let remainingPlaybackMs = 0;
    const playbackContext = playbackContextRef.current;
    if (playbackContext && playbackContext.state !== 'closed') {
      remainingPlaybackMs = Math.max(0, (nextPlaybackTimeRef.current - playbackContext.currentTime) * 1000);
    }

    const totalBlockMs = remainingPlaybackMs + Math.max(0, RESPONSE_RESUME_COOLDOWN_MS);
    micBlockedRef.current = true;
    setAwaitingResponse(true);
    setStatusText('Audio afspelen...');

    playbackDrainTimerRef.current = setTimeout(() => {
      finalizeMicUnblockAfterPlayback();
    }, totalBlockMs);
  };

  const flushBufferedAudio = () => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN || sampleBufferRef.current.length === 0) return;

    const remainingSamples = Float32Array.from(sampleBufferRef.current);
    sampleBufferRef.current = [];
    const pcmBytes = float32ToPcm16(remainingSamples);
    sendJsonMessage({ type: 'audio.chunk', audio: toBase64(pcmBytes) });
  };

  const queuePlaybackAudio = async (base64Audio) => {
    const pcmBytes = fromBase64(base64Audio);
    if (!pcmBytes.length) return;

    let playbackContext = playbackContextRef.current;
    if (!playbackContext || playbackContext.state === 'closed') {
      playbackContext = new (window.AudioContext || window.webkitAudioContext)();
      playbackContextRef.current = playbackContext;
      nextPlaybackTimeRef.current = playbackContext.currentTime;
    }

    if (playbackContext.state === 'suspended') {
      await playbackContext.resume();
    }

    const samples = pcm16ToFloat32(pcmBytes);
    const audioBuffer = playbackContext.createBuffer(1, samples.length, TARGET_SAMPLE_RATE);
    audioBuffer.getChannelData(0).set(samples);

    const source = playbackContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(playbackContext.destination);

    const startTime = Math.max(playbackContext.currentTime, nextPlaybackTimeRef.current);
    source.start(startTime);
    nextPlaybackTimeRef.current = startTime + audioBuffer.duration;
  };

  const beginMicrophoneCapture = async () => {
    const mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
    });

    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const sourceNode = audioContext.createMediaStreamSource(mediaStream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);

    mediaStreamRef.current = mediaStream;
    captureContextRef.current = audioContext;
    sourceNodeRef.current = sourceNode;
    processorRef.current = processor;
    sampleBufferRef.current = [];

    processor.onaudioprocess = (event) => {
      if (!canStreamMicrophoneNow()) {
        sampleBufferRef.current = [];
        return;
      }

      const inputSamples = event.inputBuffer.getChannelData(0);
      const resampled = resampleBuffer(inputSamples, audioContext.sampleRate, TARGET_SAMPLE_RATE);
      sampleBufferRef.current.push(...resampled);

      while (sampleBufferRef.current.length >= CHUNK_SAMPLE_COUNT) {
        const chunkSamples = Float32Array.from(sampleBufferRef.current.slice(0, CHUNK_SAMPLE_COUNT));
        sampleBufferRef.current = sampleBufferRef.current.slice(CHUNK_SAMPLE_COUNT);
        const pcmBytes = float32ToPcm16(chunkSamples);
        sendJsonMessage({ type: 'audio.chunk', audio: toBase64(pcmBytes) });
      }
    };

    sourceNode.connect(processor);
    processor.connect(audioContext.destination);
  };

  const handleSocketMessage = async (rawEvent) => {
    let event;
    try {
      event = JSON.parse(rawEvent.data);
    } catch (parseError) {
      return;
    }

    switch (event.type) {
      case 'session.started':
        setIsConnected(true);
        setStatusText('Microfoon klaar');
        callbacksRef.current.onSessionStarted?.(event);
        try {
          await beginMicrophoneCapture();
          setIsConnecting(false);
          setIsRecording(true);
          setError('');
          setStatusText('Luisteren...');
        } catch (microphoneError) {
          setError(microphoneError.message || 'Microfoon kon niet worden gestart');
          setStatusText('Microfoonfout');
          cleanupAll();
          callbacksRef.current.onError?.({ message: microphoneError.message || 'Microfoon kon niet worden gestart' });
        }
        break;

      case 'status':
        setStatusText(event.message || '');
        callbacksRef.current.onStatus?.(event);
        break;

      case 'speech.started':
        setStatusText('Spraak gedetecteerd');
        callbacksRef.current.onSpeechStarted?.(event);
        break;

      case 'speech.stopped':
        micBlockedRef.current = true;
        setStatusText('Spraak gestopt, transcript afronden...');
        setAwaitingResponse(true);
        callbacksRef.current.onSpeechStopped?.(event);
        break;

      case 'transcript.delta':
        if (assistantSpeakingRef.current) {
          break;
        }
        setLiveTranscript(event.transcript || '');
        callbacksRef.current.onTranscriptDelta?.(event);
        break;

      case 'transcript.final':
        if (assistantSpeakingRef.current) {
          break;
        }
        setLiveTranscript(event.transcript || '');
        setStatusText('Transcript gereed');
        callbacksRef.current.onTranscriptFinal?.(event);
        break;

      case 'assistant.response.started':
        assistantSpeakingRef.current = true;
        micBlockedRef.current = true;
        responseHasAudioRef.current = false;
        setStatusText('Antwoord genereren...');
        callbacksRef.current.onAssistantResponseStarted?.(event);
        break;

      case 'assistant.message.started':
        callbacksRef.current.onAssistantMessageStarted?.(event);
        break;

      case 'assistant.text.delta':
        callbacksRef.current.onAssistantTextDelta?.(event);
        break;

      case 'assistant.text.final':
        callbacksRef.current.onAssistantTextFinal?.(event);
        break;

      case 'assistant.audio.delta':
        responseHasAudioRef.current = true;
        setAwaitingResponse(true);
        setStatusText('Audio afspelen...');
        await queuePlaybackAudio(event.audio || '');
        callbacksRef.current.onAssistantAudioDelta?.(event);
        break;

      case 'assistant.audio.done':
        scheduleMicUnblockAfterPlaybackDrain();
        callbacksRef.current.onAssistantAudioDone?.(event);
        break;

      case 'response.done':
        if (!responseHasAudioRef.current) {
          assistantSpeakingRef.current = false;
          micBlockedRef.current = false;
          micPauseUntilRef.current = Date.now() + Math.max(0, RESPONSE_RESUME_COOLDOWN_MS);
          setAwaitingResponse(false);
          setStatusText('Klaar');
        }
        callbacksRef.current.onResponseDone?.(event);
        if (shouldCloseAfterResponseRef.current) {
          closeSocket();
        }
        break;

      case 'error':
        assistantSpeakingRef.current = false;
        micPauseUntilRef.current = 0;
        micBlockedRef.current = false;
        responseHasAudioRef.current = false;
        setAwaitingResponse(false);
        setError(event.message || 'Onbekende realtime fout');
        setStatusText(`Fout: ${event.message || 'Onbekende realtime fout'}`);
        callbacksRef.current.onError?.(event);
        if (!isRecording) {
          closeSocket();
        }
        break;

      default:
        break;
    }
  };

  const startRecording = async () => {
    if (socketRef.current || isConnecting || isRecording) return;

    cleanupAll();
    setIsConnecting(true);
    setError('');
    setLiveTranscript('');
    setStatusText('Verbinden met realtime spraakservice...');
    connectionErrorActiveRef.current = false;
    shouldCloseAfterResponseRef.current = false;
    assistantSpeakingRef.current = false;
    micPauseUntilRef.current = 0;
    micBlockedRef.current = false;
    wsFallbackInProgressRef.current = false;

    const getWsCandidates = () => {
      const candidates = [];

      if (STREAMING_VOICE_WS_URL) {
        candidates.push(STREAMING_VOICE_WS_URL);
      }

      if (typeof window !== 'undefined') {
        const browserProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const browserHost = window.location.hostname || 'localhost';
        candidates.push(`${browserProtocol}://${browserHost}:5000/api/query/ws/realtime-voice`);
      }

      candidates.push('ws://localhost:5000/api/query/ws/realtime-voice');

      // De-duplicate while keeping order.
      return [...new Set(candidates)];
    };

    const candidates = getWsCandidates();

    const connectWithCandidate = (index) => {
      if (index >= candidates.length) {
        const connectionErrorMessage = 'Assistent Fout: WebSocket verbinding mislukt';
        connectionErrorActiveRef.current = true;
        setError('WebSocket verbinding mislukt');
        setStatusText(connectionErrorMessage);
        cleanupAll();
        callbacksRef.current.onError?.({ message: 'WebSocket verbinding mislukt' });
        return;
      }

      const targetUrl = candidates[index];
      let socket = null;

      try {
        socket = new WebSocket(targetUrl);
      } catch (connectError) {
        wsFallbackInProgressRef.current = true;
        connectWithCandidate(index + 1);
        return;
      }

      socketRef.current = socket;

      socket.onopen = () => {
        wsFallbackInProgressRef.current = false;
        setIsConnected(true);
        setStatusText('Realtime sessie starten...');
        sendJsonMessage({
          type: 'session.start',
          speed: playbackSpeedRef.current,
        });
      };

      socket.onmessage = handleSocketMessage;

      socket.onerror = () => {
        try {
          socket.close();
        } catch (closeError) {
        }

        if (index < candidates.length - 1) {
          wsFallbackInProgressRef.current = true;
          setStatusText('Verbinding opnieuw proberen...');
          connectWithCandidate(index + 1);
          return;
        }

        const connectionErrorMessage = 'Assistent Fout: WebSocket verbinding mislukt';
        connectionErrorActiveRef.current = true;
        setError('WebSocket verbinding mislukt');
        setStatusText(connectionErrorMessage);
        cleanupAll();
        callbacksRef.current.onError?.({ message: 'WebSocket verbinding mislukt', wsUrl: targetUrl });
      };

      socket.onclose = () => {
        if (wsFallbackInProgressRef.current) {
          return;
        }

        socketRef.current = null;
        stopCapture();
        assistantSpeakingRef.current = false;
        micPauseUntilRef.current = 0;
        setIsConnecting(false);
        setIsConnected(false);
        setIsRecording(false);
        if (!awaitingResponse && !connectionErrorActiveRef.current) {
          setStatusText('');
        }
      };
    };

    connectWithCandidate(0);
  };

  const stopRecording = () => {
    if (!socketRef.current) return;

    flushBufferedAudio();
    stopCapture();
    setIsRecording(false);
    setAwaitingResponse(true);
    setStatusText('Audio afronden...');
    shouldCloseAfterResponseRef.current = true;
    sendJsonMessage({ type: 'recording.stop' });
  };

  const endSession = () => {
    if (!socketRef.current) return;

    shouldCloseAfterResponseRef.current = false;
    assistantSpeakingRef.current = false;
    responseHasAudioRef.current = false;

    sendJsonMessage({ type: 'session.close' });
    cleanupAll();
    setLiveTranscript('');
    setStatusText('Verbinding verbroken');
  };

  return {
    startRecording,
    stopRecording,
    endSession,
    isConnecting,
    isConnected,
    isRecording,
    awaitingResponse,
    isBusy: isConnecting || isRecording || awaitingResponse,
    statusText,
    liveTranscript,
    error,
    playbackSpeed,
    setPlaybackSpeed: updatePlaybackSpeed,
  };
}
