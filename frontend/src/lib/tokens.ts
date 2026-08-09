/**
 * Conservation des jetons côté navigateur.
 *
 * `sessionStorage` et non `localStorage` : les jetons disparaissent à la
 * fermeture de l'onglet, ce qui limite l'exposition sur un poste partagé.
 *
 * Cela reste un compromis : la solution correcte est un cookie `HttpOnly`,
 * insensible au vol par XSS, que le backend ne pose pas encore. Consigné dans
 * docs/PRODUCTION_CHECKLIST.md.
 */

const ACCESS_TOKEN_KEY = 'breastai.access_token';
const REFRESH_TOKEN_KEY = 'breastai.refresh_token';

/**
 * Réserve utilisée quand `sessionStorage` est refusé : navigation privée
 * stricte, politique d'entreprise, environnement sans `window`. Sans elle, la
 * connexion réussit mais le jeton disparaît aussitôt et l'utilisateur se
 * retrouve déconnecté sans explication.
 */
const memoryStore = new Map<string, string>();

function sessionStore(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

function read(key: string): string | null {
  try {
    const stored = sessionStore()?.getItem(key);
    if (stored != null) return stored;
  } catch {
  }
  return memoryStore.get(key) ?? null;
}

function write(key: string, value: string): void {
  memoryStore.set(key, value);
  try {
    sessionStore()?.setItem(key, value);
  } catch {
  }
}

function remove(key: string): void {
  memoryStore.delete(key);
  try {
    sessionStore()?.removeItem(key);
  } catch {
  }
}

export function getAccessToken(): string | null {
  return read(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return read(REFRESH_TOKEN_KEY);
}

export function storeTokens(accessToken: string, refreshToken: string): void {
  write(ACCESS_TOKEN_KEY, accessToken);
  write(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  remove(ACCESS_TOKEN_KEY);
  remove(REFRESH_TOKEN_KEY);
}
