type AIEnvKey =
  | 'VITE_AI_API_BASE_URL'
  | 'VITE_AI_TRANSCRIBE_ENDPOINT'
  | 'VITE_AI_GENERATE_ENDPOINT'
  | 'VITE_AI_TTS_ENDPOINT';

type EndpointConfig = {
  transcribe: string;
  generate: string;
  tts: string;
};

export type AIConfig = {
  baseUrl: string;
  endpoints: EndpointConfig;
};

const defaultConfig: AIConfig = {
  baseUrl: 'http://localhost:5000',
  endpoints: {
    transcribe: '/ai/transcribe',
    generate: '/ai/generate',
    tts: '/ai/tts'
  }
};

const readEnvValue = (key: AIEnvKey): string | undefined => {
  const runtimeValue = typeof window !== 'undefined' ? window.__APP_ENV__?.[key] : undefined;
  const processValue = typeof process !== 'undefined' ? process.env[key] : undefined;
  const value = runtimeValue ?? processValue;

  if (!value) {
    return undefined;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
};

const resolveUrl = (value: string, fallback: string): string => {
  const resolved = value || fallback;
  return resolved.replace(/\/$/, '');
};

const resolveEndpoint = (value: string, fallback: string): string => {
  const resolved = value || fallback;
  return resolved.startsWith('/') ? resolved : `/${resolved}`;
};

export const aiConfig: AIConfig = {
  baseUrl: resolveUrl(readEnvValue('VITE_AI_API_BASE_URL') ?? '', defaultConfig.baseUrl),
  endpoints: {
    transcribe: resolveEndpoint(readEnvValue('VITE_AI_TRANSCRIBE_ENDPOINT') ?? '', defaultConfig.endpoints.transcribe),
    generate: resolveEndpoint(readEnvValue('VITE_AI_GENERATE_ENDPOINT') ?? '', defaultConfig.endpoints.generate),
    tts: resolveEndpoint(readEnvValue('VITE_AI_TTS_ENDPOINT') ?? '', defaultConfig.endpoints.tts)
  }
};