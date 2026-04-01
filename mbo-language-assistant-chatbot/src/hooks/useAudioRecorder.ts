import { useEffect, useRef, useState } from 'react';

type UseAudioRecorderResult = {
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<void>;
  audioBlob: Blob | null;
  isRecording: boolean;
};

const preferredMimeTypes = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/wav'
];

const resolveMimeType = (): string => {
  if (typeof MediaRecorder === 'undefined') {
    return '';
  }

  const supportedMimeType = preferredMimeTypes.find((mimeType) => MediaRecorder.isTypeSupported(mimeType));
  return supportedMimeType ?? '';
};

export const useAudioRecorder = (): UseAudioRecorderResult => {
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const stopPromiseResolverRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }

      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const startRecording = async (): Promise<void> => {
    if (isRecording) {
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Audio recording is not supported in this browser.');
    }

    const mimeType = resolveMimeType();
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: true
    });

    chunksRef.current = [];
    setAudioBlob(null);
    streamRef.current = stream;

    const recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);

    recorder.ondataavailable = (event: BlobEvent) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data);
      }
    };

    recorder.onstop = () => {
      const nextAudioBlob = new Blob(chunksRef.current, {
        type: recorder.mimeType || 'audio/webm'
      });

      setAudioBlob(nextAudioBlob);
      setIsRecording(false);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      stopPromiseResolverRef.current?.();
      stopPromiseResolverRef.current = null;
    };

    recorder.onerror = () => {
      setIsRecording(false);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      stopPromiseResolverRef.current?.();
      stopPromiseResolverRef.current = null;
    };

    mediaRecorderRef.current = recorder;
    recorder.start();
    setIsRecording(true);
  };

  const stopRecording = async (): Promise<void> => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      return;
    }

    await new Promise<void>((resolve) => {
      stopPromiseResolverRef.current = resolve;
      recorder.stop();
    });
  };

  return {
    startRecording,
    stopRecording,
    audioBlob,
    isRecording
  };
};