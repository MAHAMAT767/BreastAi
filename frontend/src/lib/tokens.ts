/**
 * Conservation des jetons côté navigateur.
 *
 * `sessionStorage` et non `localStorage` : les jetons disparaissent à la
 * fermeture de l'onglet, ce qui limite la fenêtre d'exposition sur un poste
 * partagé — situation courante dans un service de radiologie.
 *
 * Cela reste un compromis. La solution correcte est un cookie `HttpOnly`,
 * inaccessible au JavaScript et donc insensible au vol par XSS ; elle suppose
 * que le backend pose et lise ce cookie, ce qu'il ne fait pas encore. La limite
 * est consignée dans docs/PRODUCTION_CHECKLIST.md.
 */

const ACCESS_TOKEN_KEY = 'breastai.access_token';
const REFRESH_TOKEN_KEY = 'breastai.refresh_token';

function storage(): Storage | null {
  // `sessionStorage` est absent en rendu serveur et peut être bloqué par la
  // politique de confidentialité du navigateur : ne jamais supposer sa présence.
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  return storage()?.getItem(ACCESS_TOKEN_KEY) ?? null;
}

export function getRefreshToken(): string | null {
  return storage()?.getItem(REFRESH_TOKEN_KEY) ?? null;
}

export function storeTokens(accessToken: string, refreshToken: string): void {
  const store = storage();
  store?.setItem(ACCESS_TOKEN_KEY, accessToken);
  store?.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  const store = storage();
  store?.removeItem(ACCESS_TOKEN_KEY);
  store?.removeItem(REFRESH_TOKEN_KEY);
}
