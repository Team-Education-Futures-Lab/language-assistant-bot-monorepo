import React, { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, User, Bot, Trash2, Play, Pause } from 'lucide-react';
import { queryBackendAPISpeech, synthesizeSpeechAudio } from '../api';

// --- TUNING CONSTANTS ---
// If the Green bar never crosses the Red line, LOWER this number.
// If the Green bar is always past the Red line (background noise), RAISE this number.
const VAD_RMS_THRESHOLD = 0.012; 

const VAD_SILENCE_MS = 1400;      // Wait 1.4s for silence
const MIN_RECORDING_MS = 600;     // Minimum speech duration
const MAX_RECORDING_MS = 30000;   // Safety stop after 30s
const VAD_DYNAMIC_MULTIPLIER = 3.2;
const VAD_NOISE_FLOOR_INIT = 0.003;
const VAD_NOISE_ADAPT_ALPHA = 0.04;
const VAD_MIN_ZCR = 0.015;
const VAD_MAX_ZCR = 0.22;
const VAD_SPEECH_FRAMES_REQUIRED = 4;

export default function SpeechPage() {
  const SETTINGS_API_URL = 'http://localhost:5004';
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [response, setResponse] = useState('');
  const [question, setQuestion] = useState('');
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [generatingAudio, setGeneratingAudio] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [conversationActive, setConversationActive] = useState(false);
  const [conversationStatus, setConversationStatus] = useState('idle');
  
  // Debugging / Visualizer State
  const [currentVolume, setCurrentVolume] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [vadSilenceMs, setVadSilenceMs] = useState(VAD_SILENCE_MS);
  const [maxRecordingMs, setMaxRecordingMs] = useState(MAX_RECORDING_MS);

  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const sourceNodeRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioPlayerRef = useRef(null);
  const cachedResponseRef = useRef('');
  const recordingStartRef = useRef(0);
  const lastVoiceDetectedAtRef = useRef(0);
  const hasDetectedSpeechRef = useRef(false);
  const stopRecordingInProgressRef = useRef(false);
  const conversationActiveRef = useRef(false);
  const startRecordingInProgressRef = useRef(false);
  const isRecordingRef = useRef(false);
  const vadStopRequestedRef = useRef(false);
  const nextListenTimeoutRef = useRef(null);
  const sampleRateRef = useRef(44100);
  const audioUrlRef = useRef(null);
  const playbackLockRef = useRef(false);
  const noiseFloorRef = useRef(VAD_NOISE_FLOOR_INIT);
  const speechFrameStreakRef = useRef(0);
  const vadSilenceMsRef = useRef(VAD_SILENCE_MS);
  const maxRecordingMsRef = useRef(MAX_RECORDING_MS);
  
  // Throttle volume updates to prevent UI lag
  const lastVolumeUpdateRef = useRef(0);

  useEffect(() => {
    conversationActiveRef.current = conversationActive;
  }, [conversationActive]);

  useEffect(() => {
    audioUrlRef.current = audioUrl;
  }, [audioUrl]);

  useEffect(() => {
    vadSilenceMsRef.current = vadSilenceMs;
  }, [vadSilenceMs]);

  useEffect(() => {
    maxRecordingMsRef.current = maxRecordingMs;
  }, [maxRecordingMs]);

  const loadVadSettings = async () => {
    try {
      const [silenceResp, maxResp] = await Promise.all([
        fetch(`${SETTINGS_API_URL}/settings/speech_vad_silence_ms`),
        fetch(`${SETTINGS_API_URL}/settings/speech_max_recording_ms`)
      ]);

      if (silenceResp.ok) {
        const silenceData = await silenceResp.json();
        const parsedSilence = Number(silenceData?.setting?.value);
        if (!Number.isNaN(parsedSilence) && parsedSilence >= 200 && parsedSilence <= 20000) {
          vadSilenceMsRef.current = parsedSilence;
          setVadSilenceMs(parsedSilence);
        }
      }

      if (maxResp.ok) {
        const maxData = await maxResp.json();
        const parsedMax = Number(maxData?.setting?.value);
        if (!Number.isNaN(parsedMax) && parsedMax >= 1000 && parsedMax <= 120000) {
          maxRecordingMsRef.current = parsedMax;
          setMaxRecordingMs(parsedMax);
        }
      }
    } catch (error) {
      console.warn('Kon VAD-instellingen niet laden, standaardwaarden blijven actief.', error);
    }
  };

  useEffect(() => {
    loadVadSettings();
  }, []);

  const clearAudioCache = () => {
    const audio = audioPlayerRef.current;
    if (audio) {
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
    }
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setAudioPlaying(false);
    cachedResponseRef.current = '';
  };

  const cleanupRecordingResources = () => {
    try {
      if (processorRef.current) {
        processorRef.current.onaudioprocess = null;
        processorRef.current.disconnect();
      }
      if (sourceNodeRef.current) sourceNodeRef.current.disconnect();
      if (streamRef.current) streamRef.current.getTracks().forEach(track => track.stop());
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
      }
    } catch (error) {
      console.error('Error cleaning up recording resources:', error);
    } finally {
      processorRef.current = null;
      sourceNodeRef.current = null;
      streamRef.current = null;
      audioContextRef.current = null;
      audioChunksRef.current = [];
      isRecordingRef.current = false;
      setCurrentVolume(0); // Reset visualizer
    }
  };

  const handleMicClick = () => conversationActive ? stopConversation() : startConversation();

  useEffect(() => {
    return () => {
      conversationActiveRef.current = false;
      if (nextListenTimeoutRef.current) {
        clearTimeout(nextListenTimeoutRef.current);
      }
      cleanupRecordingResources();
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    };
  }, []);

  const scheduleNextListen = (delayMs = 350) => {
    if (playbackLockRef.current) {
      return;
    }
    if (nextListenTimeoutRef.current) {
      clearTimeout(nextListenTimeoutRef.current);
    }
    nextListenTimeoutRef.current = setTimeout(() => {
      if (conversationActiveRef.current && !playbackLockRef.current) {
        startRecordingInternal({ resetTranscript: false });
      }
    }, delayMs);
  };

  const base64ToAudioBlob = (base64Audio) => {
    try {
      const binary = window.atob(base64Audio);
      const len = binary.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      return new Blob([bytes], { type: 'audio/mpeg' });
    } catch (error) {
      console.error('Failed to decode base64 audio:', error);
      return null;
    }
  };

  const encodeWAV = (samples, sampleRate) => {
    if (!samples || samples.length === 0) return null;
    const MONO = 1, BITS = 16, BYTES = BITS / 8;
    const buffer = new ArrayBuffer(44 + samples.length * BYTES);
    const view = new DataView(buffer);
    const writeString = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
    
    writeString(0, 'RIFF'); view.setUint32(4, 36 + samples.length * BYTES, true); writeString(8, 'WAVE');
    writeString(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, MONO, true);
    view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * MONO * BYTES, true);
    view.setUint16(32, MONO * BYTES, true); view.setUint16(34, BITS, true);
    writeString(36, 'data'); view.setUint32(40, samples.length * BYTES, true);

    let offset = 44;
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      offset += 2;
    }
    return new Blob([buffer], { type: 'audio/wav' });
  };

  const generateAudio = async (text) => {
    console.log('🎵 generateAudio() called with text:', text?.substring(0, 30) + '...');
    setGeneratingAudio(true);
    setStatusMessage('🎵 Audio genereren...');
    try {
      console.log('📤 Calling synthesizeSpeechAudio backend...');
      const ttsResult = await synthesizeSpeechAudio(text);
      console.log('📥 TTS backend response:', {
        success: ttsResult.success,
        audioBlob: ttsResult.audioBlob ? `${ttsResult.audioBlob.size} bytes, ${ttsResult.audioBlob.type}` : null,
        error: ttsResult.error
      });
      if (!ttsResult.success) {
        console.error('❌ TTS backend error:', ttsResult.error);
        setStatusMessage('❌ Audio genereren mislukt: ' + ttsResult.error);
        throw new Error(ttsResult.error || 'TTS failed');
      }
      console.log('✅ Got TTS audio blob:', ttsResult.audioBlob?.size, 'bytes, type:', ttsResult.audioBlob?.type);
      setStatusMessage('✅ Audio klaar, voorbereiden op afspelen...');
      return ttsResult.audioBlob;
    } catch (error) {
      console.error('❌ generateAudio error:', error);
      setStatusMessage('❌ Fout: ' + error.message);
      alert('Audio genereren mislukt: ' + error.message);
      return null;
    } finally {
      setGeneratingAudio(false);
    }
  };

  const playAudioBlob = async (audioBlob, textForCache = '') => {
    if (!audioBlob) return false;

    const audio = audioPlayerRef.current;
    if (!audio) {
      setStatusMessage('Audiospeler is nog niet klaar');
      return false;
    }

    const newAudioUrl = URL.createObjectURL(audioBlob);
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }
    if (nextListenTimeoutRef.current) {
      clearTimeout(nextListenTimeoutRef.current);
      nextListenTimeoutRef.current = null;
    }
    playbackLockRef.current = true;
    setAudioUrl(newAudioUrl);
    cachedResponseRef.current = textForCache;

    audio.onplay = () => {
      setStatusMessage('Antwoord wordt afgespeeld...');
      setAudioPlaying(true);
      playbackLockRef.current = true;
      if (conversationActiveRef.current) setConversationStatus('speaking');
    };

    audio.onpause = () => {
      setAudioPlaying(false);
    };

    audio.onended = () => {
      setAudioPlaying(false);
      playbackLockRef.current = false;
      if (conversationActiveRef.current) {
        setConversationStatus('listening');
        setStatusMessage('Luisteren...');
        scheduleNextListen(350);
      }
    };

    audio.onerror = () => {
      setAudioPlaying(false);
      playbackLockRef.current = false;
      setStatusMessage('Audio afspelen mislukt');
      if (conversationActiveRef.current) {
        setConversationStatus('listening');
        scheduleNextListen(500);
      }
    };

    try {
      audio.src = newAudioUrl;
      audio.load();
      await audio.play();
      return true;
    } catch (error) {
      console.error('Error playing audio blob:', error);
      setAudioPlaying(false);
      playbackLockRef.current = false;
      setStatusMessage('Audio kon niet automatisch starten');
      return false;
    }
  };

  const playAudio = async () => {
    if (!response) {
      setStatusMessage('Geen antwoord beschikbaar om af te spelen');
      return;
    }

    const audio = audioPlayerRef.current;
    if (audioPlaying && audio) {
      audio.pause();
      return;
    }

    if (audioUrl && cachedResponseRef.current === response && audio) {
      audio.currentTime = 0;
      try {
        await audio.play();
        return;
      } catch (error) {
        console.error('Replay failed:', error);
      }
    }

    const fallbackBlob = await generateAudio(response);
    if (fallbackBlob) {
      await playAudioBlob(fallbackBlob, response);
    }
  };

  const startRecordingInternal = async ({ resetTranscript = false } = {}) => {
    if (isRecordingRef.current || processing || generatingAudio || startRecordingInProgressRef.current || playbackLockRef.current) {
      console.warn('⚠️ Recording blocked:', { recording, processing, generatingAudio, inProgress: startRecordingInProgressRef.current });
      return;
    }
    
    console.log('🎙️ startRecordingInternal called (conversation mode:', conversationActiveRef.current, ')');
    startRecordingInProgressRef.current = true;

    // Pull latest timing settings from DB before each recording cycle.
    // This makes dashboard changes effective immediately without page refresh.
    await loadVadSettings();

    if (resetTranscript) {
      setResponse('');
      setQuestion('');
      clearAudioCache();
    }

    stopRecordingInProgressRef.current = false;
    vadStopRequestedRef.current = false;
    recordingStartRef.current = Date.now();
    lastVoiceDetectedAtRef.current = recordingStartRef.current;
    hasDetectedSpeechRef.current = false;
    speechFrameStreakRef.current = 0;
    noiseFloorRef.current = VAD_NOISE_FLOOR_INIT;
    setConversationStatus(conversationActiveRef.current ? 'listening' : 'idle');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
          sampleRate: 16000,
        },
      });
      console.log('✅ Microphone access granted');
      streamRef.current = stream;
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      audioContextRef.current = audioContext;
      sampleRateRef.current = audioContext.sampleRate || 44100;
      const source = audioContext.createMediaStreamSource(stream);
      sourceNodeRef.current = source;
      audioChunksRef.current = [];
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      console.log('✅ Audio context and processor initialized');

      processor.onaudioprocess = (e) => {
        const samples = e.inputBuffer.getChannelData(0);
        audioChunksRef.current.push(new Float32Array(samples));

        // 1. Calculate RMS (always, for visualizer)
        let sumSquares = 0;
        let zeroCrossings = 0;
        let prevSign = samples[0] >= 0;
        for (let i = 0; i < samples.length; i++) sumSquares += samples[i] * samples[i];
        for (let i = 1; i < samples.length; i++) {
          const currentSign = samples[i] >= 0;
          if (currentSign !== prevSign) zeroCrossings += 1;
          prevSign = currentSign;
        }
        const rms = Math.sqrt(sumSquares / samples.length);
        const zcr = zeroCrossings / samples.length;
        const now = Date.now();
        const dynamicThreshold = Math.max(VAD_RMS_THRESHOLD, noiseFloorRef.current * VAD_DYNAMIC_MULTIPLIER);
        const speechLike = rms > dynamicThreshold && zcr >= VAD_MIN_ZCR && zcr <= VAD_MAX_ZCR;

        // Continuously adapt environmental noise floor from non-speech frames.
        if (!speechLike) {
          noiseFloorRef.current =
            (1 - VAD_NOISE_ADAPT_ALPHA) * noiseFloorRef.current +
            VAD_NOISE_ADAPT_ALPHA * rms;
        }

        // 2. Update Visualizer (Throttled to 10fps for performance)
        if (now - lastVolumeUpdateRef.current > 100) {
          lastVolumeUpdateRef.current = now;
          setCurrentVolume(rms); // Update UI
        }

        // 3. VAD Logic (only if conversation is active and not stopping)
        if (conversationActiveRef.current && !stopRecordingInProgressRef.current && !vadStopRequestedRef.current) {
          // 3a. Detect Speech
          if (speechLike) {
            speechFrameStreakRef.current += 1;
          } else {
            speechFrameStreakRef.current = 0;
          }

          if (!hasDetectedSpeechRef.current && speechFrameStreakRef.current >= VAD_SPEECH_FRAMES_REQUIRED) {
            console.log(
              '🎙️ Voice confirmed. RMS:',
              rms.toFixed(4),
              'ZCR:',
              zcr.toFixed(4),
              'threshold:',
              dynamicThreshold.toFixed(4)
            );
            hasDetectedSpeechRef.current = true;
            lastVoiceDetectedAtRef.current = now;
          } else if (hasDetectedSpeechRef.current && speechLike) {
            lastVoiceDetectedAtRef.current = now;
          }

          const recordingDuration = now - recordingStartRef.current;
          const silenceDuration = now - lastVoiceDetectedAtRef.current;

          // 3b. Stop Logic
          if (recordingDuration > maxRecordingMsRef.current) {
            console.log('⏰ Max duration stop (limit:', maxRecordingMsRef.current, 'ms)');
            vadStopRequestedRef.current = true;
            stopRecording({ trigger: 'max-duration' });
          } else if (
            hasDetectedSpeechRef.current &&
            recordingDuration >= MIN_RECORDING_MS &&
            silenceDuration >= vadSilenceMsRef.current
          ) {
            console.log('🤐 Silence detected stop (', silenceDuration, 'ms silence, threshold:', vadSilenceMsRef.current, 'ms )');
            vadStopRequestedRef.current = true;
            stopRecording({ trigger: 'silence' });
          }
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);
      setRecording(true);
      isRecordingRef.current = true;
      if (conversationActiveRef.current) setConversationStatus('listening');
      console.log('✅ Recording started! conversationActiveRef:', conversationActiveRef.current);

    } catch (e) {
      console.error('❌ Mic error:', e);
      alert('Microfoonfout: ' + e.message);
      setRecording(false);
      isRecordingRef.current = false;
      setConversationActive(false);
      setConversationStatus('idle');
    } finally {
      startRecordingInProgressRef.current = false;
    }
  };

  const stopRecording = async ({ trigger = 'manual' } = {}) => {
    if (!isRecordingRef.current || stopRecordingInProgressRef.current) return;

    console.log('⏸️ stopRecording called (trigger:', trigger, ', audioChunks:', audioChunksRef.current.length, ')');
    stopRecordingInProgressRef.current = true;
    isRecordingRef.current = false;
    setRecording(false);
    setProcessing(true);
    setConversationStatus('processing');
    setCurrentVolume(0); // Reset visualizer

    try {
      const capturedChunks = [...audioChunksRef.current];
      const sampleRate = sampleRateRef.current || 44100;
      const hadSpeech = hasDetectedSpeechRef.current;
      cleanupRecordingResources();

      if (!hadSpeech) {
        setStatusMessage('Geen duidelijke spraak gedetecteerd, opnieuw luisteren...');
        if (conversationActiveRef.current) {
          setConversationStatus('listening');
          scheduleNextListen(350);
        }
        return;
      }

      const totalLength = capturedChunks.reduce((acc, arr) => acc + arr.length, 0);
      const combined = new Float32Array(totalLength);
      let offset = 0;
      for (const chunk of capturedChunks) {
        combined.set(chunk, offset);
        offset += chunk.length;
      }

      const wav = encodeWAV(Array.from(combined), sampleRate);
      console.log('📦 WAV encoded. Size:', wav?.size, 'bytes');
      
      if (wav && wav.size > 8000) {
        console.log('📤 Sending', wav.size, 'bytes to backend...');
        setStatusMessage('📤 Sending audio to backend...');
        const result = await queryBackendAPISpeech(wav, { enableTts: true });
        console.log('📥 Backend response:', result);
        console.log('   - success:', result.success);
        console.log('   - question:', result.question?.substring(0, 50));
        console.log('   - answer:', result.answer?.substring(0, 50));
        console.log('   - error:', result.error);
        
        if (result.success) {
          console.log('✅ Got answer:', result.answer?.substring(0, 50) + '...');
          setStatusMessage('✅ Response received');
          setQuestion(result.question || 'Your question');
          setResponse(result.answer);
          setConversationStatus('speaking');

          let audioBlob = null;
          if (result.audioAvailable && result.audioBase64) {
            audioBlob = base64ToAudioBlob(result.audioBase64);
          }
          if (!audioBlob) {
            audioBlob = await generateAudio(result.answer);
          }

          if (audioBlob) {
            await playAudioBlob(audioBlob, result.answer);
          } else if (conversationActiveRef.current) {
            setConversationStatus('listening');
            scheduleNextListen(500);
          }
        } else {
          console.error('❌ Backend returned error:', result.error);
          setStatusMessage('❌ Backendfout: ' + result.error);
          setResponse('Fout: ' + result.error);
          if (conversationActiveRef.current) {
            setConversationStatus('listening');
            scheduleNextListen(700);
          }
        }
      } else {
        console.warn('⚠️ WAV too small or encoding failed', { size: wav?.size, chunks: capturedChunks.length });
        setStatusMessage('⚠️ Opname te kort - opnieuw proberen...');
        setResponse('Opname te kort (of microfoonvolume te laag).');
        // Retry loop if it was just a false start
        if (conversationActiveRef.current) {
            console.log('🔄 Retrying...');
            scheduleNextListen(500);
        }
      }
    } catch (error) {
      setResponse('Fout: ' + error.message);
      if (conversationActiveRef.current) {
        setConversationStatus('listening');
        scheduleNextListen(700);
      }
    } finally {
      setProcessing(false);
      stopRecordingInProgressRef.current = false;
      vadStopRequestedRef.current = false;
      if (!conversationActiveRef.current) setConversationStatus('idle');
    }
  };

  // ... helper functions for replay, mic click, etc ...
  const startConversation = () => {
    console.log('🎤 Starting conversation...');
    if (nextListenTimeoutRef.current) {
      clearTimeout(nextListenTimeoutRef.current);
      nextListenTimeoutRef.current = null;
    }
    conversationActiveRef.current = true; // Set ref BEFORE startRecording so VAD activates synchronously
    setConversationActive(true);
    setConversationStatus('listening');
    startRecordingInternal({ resetTranscript: true });
  };
  
  const stopConversation = () => {
    conversationActiveRef.current = false;
    if (nextListenTimeoutRef.current) {
      clearTimeout(nextListenTimeoutRef.current);
      nextListenTimeoutRef.current = null;
    }
    setConversationActive(false);
    setConversationStatus('idle');
    setRecording(false);
    isRecordingRef.current = false;
    setProcessing(false);
    setAudioPlaying(false);
    setStatusMessage('');
    playbackLockRef.current = false;
    cleanupRecordingResources();
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
    }
  };

  // Calculate percentage for volume bar (0.00 to 0.10 scale typically)
  const volumePercent = Math.min(100, (currentVolume / 0.05) * 100);
  const thresholdPercent = Math.min(100, (VAD_RMS_THRESHOLD / 0.05) * 100);

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ backgroundColor: 'var(--color-background)' }}>
      {/* Top Section */}
      <div className="flex flex-col items-center justify-center border-b" style={{ height: '40%', borderColor: 'var(--color-border)', backgroundColor: 'var(--color-background)' }}>
        <div className="flex flex-col items-center gap-6 max-w-2xl w-full px-4">
          <h2 className="text-3xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>Spraakassistent</h2>
          
          <button
            onClick={handleMicClick}
            className={`relative w-32 h-32 rounded-full flex items-center justify-center transition-all duration-300 ${conversationActive ? 'scale-110 shadow-2xl' : 'hover:scale-105 shadow-lg'}`}
            style={{ backgroundColor: conversationActive ? (recording ? '#ef4444' : '#f59e0b') : 'var(--color-accent)' }}
          >
            {conversationActive ? <MicOff className="text-white" size={42} /> : <Mic className="text-white" size={42} />}
            {conversationActive && <div className="absolute inset-0 rounded-full border-4 border-red-200 animate-pulse" />}
          </button>

          {/* --- VOLUME DEBUGGER --- */}
          {conversationActive && recording && (
            <div className="w-64 flex flex-col gap-1">
                <div className="flex justify-between text-xs text-gray-500">
                    <span>Stil</span>
                    <span>Luid</span>
                </div>
                <div className="relative h-4 bg-gray-200 rounded-full overflow-hidden border border-gray-300">
                    {/* The Volume Bar */}
                    <div 
                        className="h-full transition-all duration-100 ease-out"
                        style={{ 
                            width: `${volumePercent}%`,
                            backgroundColor: currentVolume > VAD_RMS_THRESHOLD ? '#22c55e' : '#9ca3af' // Green if talking, Gray if silent
                        }}
                    />
                    {/* The Threshold Line */}
                    <div 
                        className="absolute top-0 bottom-0 w-1 bg-red-500 z-10"
                        style={{ left: `${thresholdPercent}%` }}
                        title="Spraakdrempel"
                    />
                </div>
                <p className="text-xs text-center text-gray-500 mt-1">
                    {currentVolume > VAD_RMS_THRESHOLD ? "Spraak gedetecteerd" : "Wachten op spraak..."}
                </p>
            </div>
          )}

          <p className="text-center text-lg font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            {conversationActive ? (recording ? "Luisteren..." : conversationStatus === 'processing' ? "Nadenken..." : "Spreken...") : "Klik om te starten"}
          </p>

          {/* Status Message Display */}
          {statusMessage && (
            <div className="mt-2 p-3 rounded-lg text-sm font-medium text-center"
              style={{
                backgroundColor: statusMessage.includes('❌') ? '#fee2e2' : statusMessage.includes('✅') ? '#dcfce7' : '#fef3c7',
                color: statusMessage.includes('❌') ? '#991b1b' : statusMessage.includes('✅') ? '#166534' : '#92400e',
                border: '1px solid currentColor'
              }}
            >
              {statusMessage}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Section */}
      <div className="flex flex-col" style={{ height: '60%', backgroundColor: 'var(--color-background)' }}>
        <div className="flex flex-col h-full max-w-2xl w-full mx-auto px-4 py-6">
          {/* Response Text Areas ... */}
          {question && (
            <div className="mb-4">
               <div className="p-4 rounded-lg h-24 overflow-y-auto" style={{ backgroundColor: 'var(--color-secondary)', border: '1px solid var(--color-border)' }}>
                 <div className="flex items-center gap-2 mb-2 text-sm font-bold opacity-50"><User size={14}/> Jij</div>
                 {question}
               </div>
            </div>
          )}
          
          {response && (
            <div className="mb-4 flex-1 min-h-0">
               <div className="p-4 rounded-lg h-full overflow-y-auto" style={{ backgroundColor: 'var(--color-secondary)', border: '1px solid var(--color-border)' }}>
                 <div className="flex items-center gap-2 mb-2 text-sm font-bold opacity-50"><Bot size={14}/> Assistent</div>
                 {response}
               </div>
            </div>
          )}

          <audio ref={audioPlayerRef} className="hidden" />

          {/* Action Buttons */}
          {response && (
             <div className="flex gap-3 mt-auto pt-4">
                <button onClick={playAudio} className="flex-1 px-4 py-3 rounded-lg bg-blue-600 text-white font-medium hover:opacity-90 flex justify-center items-center gap-2">
                  {audioPlaying ? <Pause size={18}/> : <Play size={18}/>} {audioPlaying ? "Pauzeren" : "Afspelen"}
                </button>
                <button onClick={() => { setResponse(''); setQuestion(''); clearAudioCache(); }} className="px-6 py-3 rounded-lg bg-red-500 text-white font-medium hover:opacity-90 flex justify-center items-center gap-2">
                  <Trash2 size={18}/> Wissen
                </button>
             </div>
          )}
        </div>
      </div>
    </div>
  );
}