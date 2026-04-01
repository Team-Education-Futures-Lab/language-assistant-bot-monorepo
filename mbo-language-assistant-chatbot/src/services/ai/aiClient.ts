import { aiConfig } from './aiConfig';

type ApiEnvelope<T> = {
  success: boolean;
  data?: T;
  error?: {
    message?: string;
    details?: unknown;
  };
};

type ResponseType = 'json' | 'blob';

type RequestOptions = {
  responseType?: ResponseType;
  credentials?: RequestCredentials;
};

export class AIClientError extends Error {
  public readonly status: number;
  public readonly details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = 'AIClientError';
    this.status = status;
    this.details = details;
  }
}

const buildUrl = (endpoint: string): string => `${aiConfig.baseUrl}${endpoint}`;

const toStructuredError = async (response: Response): Promise<AIClientError> => {
  const fallbackMessage = `Request failed with status ${response.status}.`;

  try {
    const contentType = response.headers.get('Content-Type') || '';

    if (contentType.includes('application/json')) {
      const payload = (await response.json()) as ApiEnvelope<unknown>;
      return new AIClientError(
        payload.error?.message || fallbackMessage,
        response.status,
        payload.error?.details
      );
    }

    const text = await response.text();
    return new AIClientError(text || fallbackMessage, response.status);
  } catch {
    return new AIClientError(fallbackMessage, response.status);
  }
};

const request = async <T>(
  endpoint: string,
  init: RequestInit,
  options: RequestOptions = {}
): Promise<T> => {
  const responseType = options.responseType ?? 'json';

  let response: Response;
  try {
    response = await fetch(buildUrl(endpoint), {
      credentials: options.credentials ?? 'include',
      ...init
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Network request failed.';
    throw new AIClientError(message, 0);
  }

  if (!response.ok) {
    throw await toStructuredError(response);
  }

  if (responseType === 'blob') {
    return (await response.blob()) as T;
  }

  const payload = (await response.json()) as ApiEnvelope<T>;
  if (!payload.success || typeof payload.data === 'undefined') {
    throw new AIClientError(payload.error?.message || 'Request failed.', response.status, payload.error?.details);
  }

  return payload.data;
};

export const get = <T>(endpoint: string, options?: RequestOptions): Promise<T> => {
  return request<T>(endpoint, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json'
    }
  }, options);
};

export const postJson = <T>(
  endpoint: string,
  body: unknown,
  options?: RequestOptions
): Promise<T> => {
  return request<T>(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  }, options);
};

export const postForm = <T>(
  endpoint: string,
  formData: FormData,
  options?: RequestOptions
): Promise<T> => {
  return request<T>(endpoint, {
    method: 'POST',
    body: formData
  }, options);
};