import { AIClientError, postForm, postJson } from './aiClient';
import { aiConfig } from './aiConfig';

export type TranscriptionResult = {
  text: string;
};

export type GenerationResult = {
  response: string;
};

export type AudioWorkflowResult = {
  transcription: string;
  responseText: string;
  audioBlob: Blob;
};

const createAudioFileName = (blob: Blob): string => {
  if (blob.type.includes('wav')) {
    return 'recording.wav';
  }

  if (blob.type.includes('webm')) {
    return 'recording.webm';
  }

  return 'recording.audio';
};

export const toReadableErrorMessage = (error: unknown): string => {
  if (error instanceof AIClientError && error.message) {
    return error.message;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return 'Audio processing failed. Please try again.';
};

export const transcribeAudio = async (file: Blob): Promise<TranscriptionResult> => {
  const formData = new FormData();
  formData.append('audio', file, createAudioFileName(file));

  return postForm<TranscriptionResult>(aiConfig.endpoints.transcribe, formData);
};

export const generateResponse = async (text: string): Promise<GenerationResult> => {
  return postJson<GenerationResult>(aiConfig.endpoints.generate, {
    prompt: text
  });
};

export const generateSpeech = async (text: string): Promise<Blob> => {
  return postJson<Blob>(
    aiConfig.endpoints.tts,
    { text },
    { responseType: 'blob' }
  );
};

export const runFullAudioWorkflow = async (audioFile: Blob): Promise<AudioWorkflowResult> => {
  const transcriptionResult = await transcribeAudio(audioFile);
  const generationResult = await generateResponse(transcriptionResult.text);
  const audioBlob = await generateSpeech(generationResult.response);

  return {
    transcription: transcriptionResult.text,
    responseText: generationResult.response,
    audioBlob
  };
};