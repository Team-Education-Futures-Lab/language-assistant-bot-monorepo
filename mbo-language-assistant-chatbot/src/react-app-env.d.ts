/// <reference types="react-scripts" />

declare global {
  interface Window {
    __APP_ENV__?: Partial<Record<
      'VITE_AI_API_BASE_URL' |
      'VITE_AI_TRANSCRIBE_ENDPOINT' |
      'VITE_AI_GENERATE_ENDPOINT' |
      'VITE_AI_TTS_ENDPOINT',
      string
    >>;
  }

  namespace NodeJS {
    interface ProcessEnv {
      VITE_AI_API_BASE_URL?: string;
      VITE_AI_TRANSCRIBE_ENDPOINT?: string;
      VITE_AI_GENERATE_ENDPOINT?: string;
      VITE_AI_TTS_ENDPOINT?: string;
    }
  }
}

export {};