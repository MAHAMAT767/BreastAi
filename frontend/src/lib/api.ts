/** Client HTTP vers l'API BreastAI. */

import { clearTokens, getAccessToken, getRefreshToken, storeTokens } from '@/lib/tokens';
import type {
  MessageResponse,
  Page,
  Patient,
  PatientPayload,
  TokenPair,
  User,
} from '@/types';

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const PREFIX = '/api/v1';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /** Le compte n'est pas autorisé, par opposition à non authentifié. */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }
}

/** Messages par défaut : le `detail` brut de FastAPI n'est pas montrable à un médecin. */
const STATUS_MESSAGES: Record<number, string> = {
  400: 'Requête invalide.',
  401: 'Session expirée. Veuillez vous reconnecter.',
  403: "Votre rôle ne permet pas d'accéder à cette ressource.",
  404: 'Ressource introuvable.',
  409: 'Conflit avec une donnée existante.',
  422: 'Certains champs sont invalides.',
  429: 'Trop de tentatives. Patientez quelques instants avant de réessayer.',
  500: 'Erreur du serveur. Réessayez ou contactez un administrateur.',
};

/**
 * Extrait un message lisible d'une réponse d'erreur.
 *
 * FastAPI renvoie `detail` sous forme de chaîne pour une `HTTPException`, mais
 * sous forme de liste d'objets pour une erreur de validation Pydantic : les deux
 * formes doivent être traitées, sinon l'interface affiche `[object Object]`.
 */
function extractMessage(status: number, body: unknown): string {
  const fallback = STATUS_MESSAGES[status] ?? `Erreur ${status}.`;

  if (typeof body !== 'object' || body === null) return fallback;
  const detail = (body as { detail?: unknown }).detail;

  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item?.msg === 'string' ? item.msg : null))
      .filter((message): message is string => Boolean(message));
    if (messages.length > 0) return messages.join(' · ');
  }

  return fallback;
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  /** Requête sans en-tête d'autorisation (connexion, réinitialisation). */
  anonymous?: boolean;
  /** Interdit une seconde tentative après renouvellement, pour couper la récursion. */
  retried?: boolean;
}

/** Renouvellement en cours, partagé : N requêtes qui échouent en 401 en même
 *  temps ne doivent déclencher qu'un seul appel à `/auth/refresh`. */
let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  const response = await fetch(`${API_URL}${PREFIX}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    clearTokens();
    return false;
  }

  const tokens = (await response.json()) as TokenPair;
  storeTokens(tokens.access_token, tokens.refresh_token);
  return true;
}

function ensureSingleRefresh(): Promise<boolean> {
  refreshInFlight ??= refreshAccessToken().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, anonymous, retried, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  if (body !== undefined && !(body instanceof FormData)) {
    finalHeaders.set('Content-Type', 'application/json');
  }
  if (!anonymous) {
    const token = getAccessToken();
    if (token) finalHeaders.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${PREFIX}${path}`, {
    ...rest,
    headers: finalHeaders,
    body:
      body === undefined
        ? undefined
        : body instanceof FormData
          ? body
          : JSON.stringify(body),
  });

  if (response.status === 401 && !anonymous && !retried) {
    // Jeton d'accès expiré : on tente un renouvellement, puis on rejoue une
    // seule fois. `retried` empêche la boucle si le refresh échoue aussi.
    if (await ensureSingleRefresh()) {
      return request<T>(path, { ...options, retried: true });
    }
    clearTokens();
  }

  if (!response.ok) {
    const errorBody = await parseBody(response);
    throw new ApiError(extractMessage(response.status, errorBody), response.status, errorBody);
  }

  if (response.status === 204) return undefined as T;
  return (await parseBody(response)) as T;
}

// --------------------------------------------------------------------------- //
// Authentification
// --------------------------------------------------------------------------- //

export async function login(email: string, password: string): Promise<TokenPair> {
  // `/auth/login` attend un formulaire OAuth2, pas du JSON, et le champ
  // s'appelle `username` même s'il reçoit une adresse e-mail.
  const form = new URLSearchParams({ username: email, password });

  const response = await fetch(`${API_URL}${PREFIX}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });

  if (!response.ok) {
    const errorBody = await parseBody(response);
    throw new ApiError(extractMessage(response.status, errorBody), response.status, errorBody);
  }

  const tokens = (await response.json()) as TokenPair;
  storeTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
}

export function logout(): Promise<MessageResponse> {
  return request<MessageResponse>('/auth/logout', { method: 'POST' });
}

export function fetchCurrentUser(): Promise<User> {
  return request<User>('/auth/me');
}

export function requestPasswordReset(email: string): Promise<MessageResponse> {
  return request<MessageResponse>('/auth/password-reset/request', {
    method: 'POST',
    body: { email },
    anonymous: true,
  });
}

export function confirmPasswordReset(token: string, newPassword: string): Promise<MessageResponse> {
  return request<MessageResponse>('/auth/password-reset/confirm', {
    method: 'POST',
    body: { token, new_password: newPassword },
    anonymous: true,
  });
}

export function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<MessageResponse> {
  return request<MessageResponse>('/auth/password/change', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
  });
}

// --------------------------------------------------------------------------- //
// Patients
// --------------------------------------------------------------------------- //

export interface PatientQuery {
  search?: string;
  limit?: number;
  offset?: number;
}

export function fetchPatients(query: PatientQuery = {}): Promise<Page<Patient>> {
  const params = new URLSearchParams();
  if (query.search?.trim()) params.set('search', query.search.trim());
  params.set('limit', String(query.limit ?? 20));
  params.set('offset', String(query.offset ?? 0));

  return request<Page<Patient>>(`/patients?${params.toString()}`);
}

export function fetchPatient(id: string): Promise<Patient> {
  return request<Patient>(`/patients/${id}`);
}

export function createPatient(payload: PatientPayload): Promise<Patient> {
  return request<Patient>('/patients', { method: 'POST', body: payload });
}

export function updatePatient(id: string, payload: Partial<PatientPayload>): Promise<Patient> {
  return request<Patient>(`/patients/${id}`, { method: 'PATCH', body: payload });
}

export function deletePatient(id: string): Promise<MessageResponse> {
  return request<MessageResponse>(`/patients/${id}`, { method: 'DELETE' });
}

// --------------------------------------------------------------------------- //
// Diagnostic
// --------------------------------------------------------------------------- //

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  app_name: string;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { anonymous: true });
}
