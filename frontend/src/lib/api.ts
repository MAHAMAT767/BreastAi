/** Client HTTP minimal vers l'API BreastAI. Étendu en Phase 2 (JWT). */

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Requête ${path} échouée (${response.status})`, response.status);
  }

  return (await response.json()) as T;
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  app_name: string;
}

export const getHealth = () => apiFetch<HealthResponse>('/api/v1/health');
