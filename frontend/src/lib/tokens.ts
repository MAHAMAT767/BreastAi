/**
 * Conservation des jetons côté navigateur.
 *
 * `sessionStorage` et non `localStorage` : les jetons disparaissent à la
 * fermeture de l'onglet, ce qui limite l'exposition sur un poste partagé —
 * situation courante dans un service de radiologie.
 *
 * Cela reste un compromis. La solution correcte est un cookie `HttpOnly`,
 * inaccessible au JavaScript et donc insensible au vol par XSS ; elle suppose
 * que le backend pose et lise ce cookie, ce qu'il ne fait pas encore. La limite
 * est consignée dans docs/PRODUCTION_CHECKLIST.md.
 */

const ACCESS_TOKEN_KEY = 'breastai.access_token';
const REFRESH_TOKEN_KEY = 'breastai.refresh_token';

/**
 * Réserve en mémoire, utilisée quand `sessionStorage` est indisponible.
 *
 * Un navigateur en navigation privée stricte, une politique d'entreprise ou un
 * environnement sans `window` peuvent refuser l'accès au stockage. Sans cette
 * réserve, la connexion réussissait mais le jeton était perdu aussitôt : chaque
 * requête suivante repartait sans autorisation, et l'utilisateur se retrouvait
 * déconnecté sans explication. La session ne survit alors pas au rechargement
 * de la page — c'est acceptable, la perdre à chaque requête ne l'était pas.
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
    // Lecture refusée : on retombe sur la réserve en mémoire.
  }
  return memoryStore.get(key) ?? null;
}

function write(key: string, value: string): void {
  memoryStore.set(key, value);
  try {
    sessionStore()?.setItem(key, value);
  } catch {
    // Écriture refusée : la réserve en mémoire fait foi pour cette session.
  }
}

function remove(key: string): void {
  memoryStore.delete(key);
  try {
    sessionStore()?.removeItem(key);
  } catch {
    // Rien à faire : la réserve en mémoire est déjà vidée.
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
