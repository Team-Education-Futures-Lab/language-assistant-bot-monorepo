import React, { useEffect, useRef, useState } from 'react';
import { Mic, MicOff } from 'lucide-react';
import {
  startLiveSttSession,
  sendLiveSttChunk,
  sendLiveSttChunkWithResponse,
  finalizeLiveSttSession,
  abortLiveSttSession,
} from '../api';

// ============================================================================
// NEW HELPER: Convert Web Audio PCM to WAV Blob (for proper streaming)
// ============================================================================
function audioBufferToWav(audioBuffer) {
  const numberOfChannels = audioBuffer.numberOfChannels;
  const sampleRate = audioBuffer.sampleRate;
  const format = 1;
  const bitDepth = 16;
  const bytesPerSample = bitDepth / 8;
  const blockAlign = numberOfChannels * bytesPerSample;

  const channelData = [];
  for (let i = 0; i < numberOfChannels; i++) {
    channelData.push(audioBuffer.getChannelData(i));
  }

  const interleaved = new Float32Array(audioBuffer.length * numberOfChannels);
  for (let i = 0; i < audioBuffer.length; i++) {
    for (let j = 0; j < numberOfChannels; j++) {
      interleaved[i * numberOfChannels + j] = channelData[j][i];
    }
  }

  const dataLength = interleaved.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);

  const writeString = (offset, string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  };

  const floatTo16BitPCM = (output, offset, input) => {
    for (let i = 0; i < input.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, input[i]));
      output.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
  };

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataLength, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, format, true);
  view.setUint16(22, numberOfChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitDepth, true);
  writeString(36, 'data');
  view.setUint32(40, dataLength, true);

  floatTo16BitPCM(view, 44, interleaved);

  return new Blob([buffer], { type: 'audio/wav' });
}

export default function LiveSpeechPage() {
  const [recording, setRecording] = useState(false);
  const [status, setStatus] = useState('Klaar');
  const [partialText, setPartialText] = useState('');
  const [finalText, setFinalText] = useState('');
  const [error, setError] = useState('');
  const [chunkCount, setChunkCount] = useState(0);
  const [lastChunkSize, setLastChunkSize] = useState(0);
  const [lastChunkMs, setLastChunkMs] = useState(0);
  const [lastChunkText, setLastChunkText] = useState('');

  // NEW: Response generation mode
  const [enableResponseGeneration, setEnableResponseGeneration] = useState(false);
  const [responseLiveText, setResponseLiveText] = useState('');
  const [responseReady, setResponseReady] = useState(false);
  const [responseError, setResponseError] = useState('');

  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const sessionIdRef = useRef('');
  const uploadQueueRef = useRef(Promise.resolve());
  const recordedBlobsRef = useRef([]);

  // NEW REFS: Web Audio API alternative approach for proper WAV streaming
  const audioContextRef = useRef(null);
  const scriptProcessorRef = useRef(null);
  const useWebAudioRef = useRef(false);

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (sessionIdRef.current) {
        abortLiveSttSession(sessionIdRef.current);
      }

      // NEW: Cleanup Web Audio resources
      if (scriptProcessorRef.current) {
        scriptProcessorRef.current.disconnect();
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, []);

  const enqueueChunk = (audioBlob, isFinal = false) => {
    uploadQueueRef.current = uploadQueueRef.current.then(async () => {
      const sessionId = sessionIdRef.current;
      if (!sessionId || !audioBlob || audioBlob.size === 0) return;

      const started = performance.now();
      setLastChunkSize(audioBlob.size);
      console.log('[LIVE-STT] Sending chunk', {
        sessionId,
        sizeBytes: audioBlob.size,
        mimeType: audioBlob.type,
        isFinal,
      });

      const chunkResult = await sendLiveSttChunk(sessionId, audioBlob, isFinal);
      const elapsed = Math.round(performance.now() - started);
      setLastChunkMs(elapsed);

      if (!chunkResult.success) {
        console.error('[LIVE-STT] Chunk failed', {
          sessionId,
          elapsedMs: elapsed,
          error: chunkResult.error,
        });
        setError(chunkResult.error || 'Chunk upload mislukt');
        return;
      }

      setChunkCount((prev) => prev + 1);
      setLastChunkText(chunkResult.chunkText || '');
      console.log('[LIVE-STT] Chunk success', {
        sessionId,
        elapsedMs: elapsed,
        chunkText: chunkResult.chunkText,
        partialTextLen: (chunkResult.partialText || '').length,
      });

      if (chunkResult.partialText) {
        setPartialText(chunkResult.partialText);
      }
    });

    return uploadQueueRef.current;
  };

  // NEW: Enqueue chunk with AI response generation
  const enqueueChunkWithResponse = (audioBlob, isFinal = false) => {
    uploadQueueRef.current = uploadQueueRef.current.then(async () => {
      const sessionId = sessionIdRef.current;
      if (!sessionId || !audioBlob || audioBlob.size === 0) return;

      const started = performance.now();
      setLastChunkSize(audioBlob.size);
      console.log('[LIVE-STT-RESPONSE] Sending chunk with response', {
        sessionId,
        sizeBytes: audioBlob.size,
        isFinal,
      });

      const chunkResult = await sendLiveSttChunkWithResponse(sessionId, audioBlob, isFinal);
      const elapsed = Math.round(performance.now() - started);
      setLastChunkMs(elapsed);

      if (!chunkResult.success) {
        console.error('[LIVE-STT-RESPONSE] Chunk failed', {
          sessionId,
          elapsedMs: elapsed,
          error: chunkResult.error,
        });
        setError(chunkResult.error || 'Chunk upload mislukt');
        return;
      }

      setChunkCount((prev) => prev + 1);
      setLastChunkText(chunkResult.chunkText || '');
      console.log('[LIVE-STT-RESPONSE] Chunk success', {
        sessionId,
        elapsedMs: elapsed,
        chunkText: chunkResult.chunkText,
        partialTextLen: (chunkResult.partialText || '').length,
        responseLen: (chunkResult.response || '').length,
        responseReady: chunkResult.responseReady,
      });

      if (chunkResult.partialText) {
        setPartialText(chunkResult.partialText);
      }

      if (chunkResult.response) {
        setResponseLiveText(chunkResult.response);
        setResponseReady(chunkResult.responseReady);
      }

      if (chunkResult.responseError) {
        setResponseError(chunkResult.responseError);
      }
    });

    return uploadQueueRef.current;
  };

  // ============================================================================
  // NEW: Setup Web Audio API for proper WAV streaming (avoids WebM concat issues)
  // ============================================================================
  const setupWebAudioRecording = async (stream) => {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    audioContextRef.current = audioContext;

    const source = audioContext.createMediaStreamSource(stream);
    const scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
    scriptProcessorRef.current = scriptProcessor;

    let chunkBuffer = [];
    const chunkDurationMs = 800;
    const chunkSampleCount = Math.floor((audioContext.sampleRate * chunkDurationMs) / 1000);

    source.connect(scriptProcessor);
    scriptProcessor.connect(audioContext.destination);

    // Choose enqueue function based on response generation mode
    const enqueueFunc = enableResponseGeneration ? enqueueChunkWithResponse : enqueueChunk;

    scriptProcessor.onaudioprocess = async (event) => {
      const inputData = event.inputBuffer.getChannelData(0);
      chunkBuffer.push(...inputData);

      // Send chunk when buffer reaches minimum size
      if (chunkBuffer.length >= chunkSampleCount) {
        const chunkData = chunkBuffer.splice(0, chunkSampleCount);
        const audioBuffer = audioContext.createBuffer(1, chunkData.length, audioContext.sampleRate);
        audioBuffer.getChannelData(0).set(chunkData);

        const wavBlob = audioBufferToWav(audioBuffer);
        console.log('[LIVE-STT-WAUDIO] Sending WAV chunk:', wavBlob.size, 'bytes');
        await enqueueFunc(wavBlob, false);
      }
    };

    console.log('[LIVE-STT-WAUDIO] Web Audio setup complete, sample rate:', audioContext.sampleRate);
    return audioContext;
  };

  const startRecording = async () => {
    setError('');
    setFinalText('');
    setPartialText('');
    setChunkCount(0);
    setLastChunkSize(0);
    setLastChunkMs(0);
    setLastChunkText('');
    recordedBlobsRef.current = [];
    
    // NEW: Clear response state
    setResponseLiveText('');
    setResponseReady(false);
    setResponseError('');
    
    setStatus('Live STT sessie starten...');

    const sessionResult = await startLiveSttSession();
    if (!sessionResult.success) {
      setError(sessionResult.error || 'Kon live STT sessie niet starten');
      setStatus('Mislukt');
      return;
    }

    sessionIdRef.current = sessionResult.sessionId;
    console.log('[LIVE-STT] Session started in browser', { sessionId: sessionIdRef.current });

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // NEW: Use Web Audio API for proper WAV streaming (backend expects WAV, not WebM)
      useWebAudioRef.current = true;
      if (useWebAudioRef.current) {
        console.log('[LIVE-STT] Using Web Audio API for WAV streaming');
        await setupWebAudioRecording(stream);
        const statusMsg = enableResponseGeneration 
          ? 'Luisteren... (live transcript + AI antwoord gegenereren)' 
          : 'Luisteren... (live transcript actief)';
        setStatus(statusMsg);
        setRecording(true);
        return;
      }

      let mimeType = 'audio/webm;codecs=opus';
      if (typeof MediaRecorder !== 'undefined' && !MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm';
      }

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = async (event) => {
        if (event.data && event.data.size > 0) {
          // MediaRecorder WebM chunks are often not independently decodable.
          // Send a cumulative blob (including initial headers) for reliable decoding.
          recordedBlobsRef.current.push(event.data);
          const cumulativeBlob = new Blob(recordedBlobsRef.current, { type: event.data.type || 'audio/webm' });
          await enqueueChunk(cumulativeBlob, false);
        }
      };

      recorder.onerror = (event) => {
        setError(`Recorder fout: ${event?.error?.message || 'Onbekend'}`);
      };

      recorder.onstart = () => {
        setStatus('Luisteren... (live transcript actief)');
        setRecording(true);
        console.log('[LIVE-STT] Recorder started');
      };

      recorder.onstop = async () => {
        setRecording(false);
        setStatus('Afronden transcript...');

        await uploadQueueRef.current;

        const sid = sessionIdRef.current;
        if (sid) {
          const finalizeResult = await finalizeLiveSttSession(sid);
          if (finalizeResult.success) {
            console.log('[LIVE-STT] Finalized', { sessionId: sid, finalText: finalizeResult.finalText });
            setFinalText(finalizeResult.finalText || partialText || '');
            setStatus('Klaar');
          } else {
            setError(finalizeResult.error || 'Finaliseren mislukt');
            setStatus('Mislukt');
          }
          sessionIdRef.current = '';
        }

        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }
      };

      // Emit chunks every 800ms for minimal live behavior.
      recorder.start(800);
    } catch (err) {
      console.error('[LIVE-STT] startRecording failed', err);
      setError(err.message || 'Microfoon fout');
      setStatus('Mislukt');
      if (sessionIdRef.current) {
        await abortLiveSttSession(sessionIdRef.current);
        sessionIdRef.current = '';
      }
    }
  };

  const stopRecording = async () => {
    setStatus('Stoppen...');
    console.log('[LIVE-STT] Stop requested');

    // NEW: Handle Web Audio cleanup if using Web Audio mode
    if (useWebAudioRef.current && scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect();
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        await audioContextRef.current.close();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      useWebAudioRef.current = false;

      // Finalize and show results
      await uploadQueueRef.current;
      const sid = sessionIdRef.current;
      if (sid) {
        const finalizeResult = await finalizeLiveSttSession(sid);
        if (finalizeResult.success) {
          console.log('[LIVE-STT] Finalized', { sessionId: sid, finalText: finalizeResult.finalText });
          setFinalText(finalizeResult.finalText || partialText || '');
          setRecording(false);
          setStatus('Klaar');
        } else {
          setError(finalizeResult.error || 'Finaliseren mislukt');
          setStatus('Mislukt');
        }
        sessionIdRef.current = '';
      }
      return;
    }

    // Existing MediaRecorder cleanup
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
  };

  return (
    <div className="w-full max-w-4xl p-6">
      <div className="bg-white rounded-lg border border-app-border p-6">
        <h2 className="text-2xl font-semibold mb-2">Live STT (Minimaal)</h2>
        <p className="text-sm text-app-text-secondary mb-4">
          Deze pagina stuurt microfoon-audio in kleine chunks en toont live transcriptie.
        </p>

        {/* NEW: Response generation mode toggle */}
        <div className="mb-4 p-3 rounded border border-blue-200 bg-blue-50">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={enableResponseGeneration}
              onChange={(e) => setEnableResponseGeneration(e.target.checked)}
              disabled={recording}
              className="w-4 h-4"
            />
            <span className="text-sm font-medium text-blue-900">
              🤖 Experimenteel: AI-antwoorden in real-time gegenereren
            </span>
          </label>
          <p className="text-xs text-blue-700 mt-2">
            {enableResponseGeneration 
              ? '✓ Aan: AI genereert antwoorden terwijl u spreekt (nieuw!)' 
              : 'Uit: Alleen transcriptie (standaard)'}
          </p>
        </div>

        <div className="flex items-center gap-3 mb-4">
          <button
            className={`px-4 py-2 rounded text-white flex items-center gap-2 ${recording ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'}`}
            onClick={recording ? stopRecording : startRecording}
          >
            {recording ? <MicOff size={16} /> : <Mic size={16} />}
            {recording ? 'Stop live STT' : 'Start live STT'}
          </button>
          <span className="text-sm text-app-text-secondary">Status: {status}</span>
        </div>

        <div className="mb-4 grid grid-cols-1 md:grid-cols-4 gap-2 text-xs">
          <div className="p-2 rounded border border-app-border bg-gray-50">Chunks verzonden: <strong>{chunkCount}</strong></div>
          <div className="p-2 rounded border border-app-border bg-gray-50">Laatste chunk: <strong>{lastChunkSize} bytes</strong></div>
          <div className="p-2 rounded border border-app-border bg-gray-50">Laatste round-trip: <strong>{lastChunkMs} ms</strong></div>
          <div className="p-2 rounded border border-app-border bg-gray-50">Laatste chunk tekst: <strong>{lastChunkText || '-'}</strong></div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded border border-red-200 bg-red-50 text-red-700 text-sm">
            {error}
          </div>
        )}

        {enableResponseGeneration ? (
          // NEW: Three-column layout for response generation mode
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="border border-app-border rounded p-3 min-h-[200px] bg-gray-50">
              <h3 className="text-sm font-semibold mb-2">Live transcript (interim)</h3>
              <p className="text-sm whitespace-pre-wrap">{partialText || 'Nog geen transcript...'}</p>
            </div>

            <div className="border border-app-border rounded p-3 min-h-[200px] bg-blue-50">
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                🤖 AI Antwoord
                {responseReady && <span className="text-xs bg-green-500 text-white px-2 py-0.5 rounded">gereed</span>}
              </h3>
              {responseError && (
                <p className="text-xs text-red-600 mb-2">Fout: {responseError}</p>
              )}
              <p className="text-sm whitespace-pre-wrap">{responseLiveText || 'Genereren...'}</p>
            </div>

            <div className="border border-app-border rounded p-3 min-h-[200px] bg-gray-50">
              <h3 className="text-sm font-semibold mb-2">Final transcript</h3>
              <p className="text-sm whitespace-pre-wrap">{finalText || 'Nog geen final transcript...'}</p>
            </div>
          </div>
        ) : (
          // Original: Two-column layout for transcript-only mode
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-app-border rounded p-3 min-h-[180px] bg-gray-50">
              <h3 className="text-sm font-semibold mb-2">Live transcript (interim)</h3>
              <p className="text-sm whitespace-pre-wrap">{partialText || 'Nog geen transcript...'}</p>
            </div>

            <div className="border border-app-border rounded p-3 min-h-[180px] bg-gray-50">
              <h3 className="text-sm font-semibold mb-2">Final transcript</h3>
              <p className="text-sm whitespace-pre-wrap">{finalText || 'Nog geen final transcript...'}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
