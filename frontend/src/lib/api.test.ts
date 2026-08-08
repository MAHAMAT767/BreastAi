import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, fetchCurrentUser, fetchPatients } from '@/lib/api';
import { clearTokens, getAccessToken, storeTokens } from '@/lib/tokens';
import { API_BASE, makeUser } from '@/test-utils';

beforeEach(() => clearTokens());
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearTokens();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('Messages d’erreur', () => {
  it('relaie un detail textuel de FastAPI', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'Dossier patient introuvable.' }, 404)),
    );

    await expect(fetchCurrentUser()).rejects.toThrow('Dossier patient introuvable.');
  });

  it('aplatit une erreur de validation Pydantic', async () => {
    // Pydantic renvoie une liste d'objets : sans traitement, l'interface
    // afficherait « [object Object] » au médecin.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(
          {
            detail: [
              { loc: ['body', 'code'], msg: 'Field required' },
              { loc: ['body', 'sex'], msg: 'Input should be F, M or O' },
            ],
          },
          422,
        ),
      ),
    );

    await expect(fetchCurrentUser()).rejects.toThrow(/Field required · Input should be/);
  });

  it('fournit un message par défaut quand le corps est vide', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 500 })));

    await expect(fetchCurrentUser()).rejects.toThrow(/Erreur du serveur/);
  });

  it('expose le code HTTP sur l’erreur', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ detail: 'Interdit.' }, 403)));

    await expect(fetchCurrentUser()).rejects.toMatchObject({ status: 403, isForbidden: true });
  });
});

describe('Renouvellement du jeton', () => {
  it('rejoue la requête après un 401 et un refresh réussi', async () => {
    storeTokens('acces-perime', 'refresh-valide');
    const user = makeUser();
    let meCalls = 0;

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = input.toString();

      if (url.includes('/auth/refresh')) {
        return jsonResponse({
          access_token: 'acces-neuf',
          refresh_token: 'refresh-neuf',
          token_type: 'bearer',
          expires_in: 1800,
        });
      }

      meCalls += 1;
      // Le premier appel échoue comme un jeton expiré, le second réussit.
      return meCalls === 1 ? jsonResponse({ detail: 'Session expirée.' }, 401) : jsonResponse(user);
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchCurrentUser()).resolves.toMatchObject({ id: 'user-1' });
    expect(getAccessToken()).toBe('acces-neuf');
    expect(meCalls).toBe(2);
  });

  it('ne tente qu’un seul refresh pour plusieurs requêtes simultanées', async () => {
    // Sans mutualisation, N requêtes expirées déclencheraient N refresh, dont
    // N-1 avec un jeton déjà consommé.
    storeTokens('acces-perime', 'refresh-valide');
    let refreshCalls = 0;
    let failFirst = true;

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();

        if (url.includes('/auth/refresh')) {
          refreshCalls += 1;
          failFirst = false;
          return jsonResponse({
            access_token: 'acces-neuf',
            refresh_token: 'refresh-neuf',
            token_type: 'bearer',
            expires_in: 1800,
          });
        }

        return failFirst
          ? jsonResponse({ detail: 'Session expirée.' }, 401)
          : jsonResponse({ items: [], total: 0, limit: 20, offset: 0 });
      }),
    );

    await Promise.all([fetchPatients(), fetchPatients(), fetchPatients()]);

    expect(refreshCalls).toBe(1);
  });

  it('efface la session quand le refresh échoue aussi', async () => {
    storeTokens('acces-perime', 'refresh-perime');

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) =>
        input.toString().includes('/auth/refresh')
          ? jsonResponse({ detail: 'Jeton invalide.' }, 401)
          : jsonResponse({ detail: 'Session expirée.' }, 401),
      ),
    );

    await expect(fetchCurrentUser()).rejects.toBeInstanceOf(ApiError);
    expect(getAccessToken()).toBeNull();
  });

  it('ne boucle pas si la requête rejouée échoue encore', async () => {
    storeTokens('acces-perime', 'refresh-valide');
    let calls = 0;

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes('/auth/refresh')) {
          return jsonResponse({
            access_token: 'acces-neuf',
            refresh_token: 'refresh-neuf',
            token_type: 'bearer',
            expires_in: 1800,
          });
        }
        calls += 1;
        return jsonResponse({ detail: 'Session expirée.' }, 401);
      }),
    );

    await expect(fetchCurrentUser()).rejects.toBeInstanceOf(ApiError);
    expect(calls).toBe(2);
  });
});

describe('Requêtes', () => {
  // Les paramètres sont déclarés explicitement : sans eux, TypeScript infère un
  // tuple d'arguments vide et `mock.calls[0][0]` devient inaccessible.
  function makeFetchMock(body: unknown) {
    return vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse(body));
  }

  it('joint le jeton d’accès en en-tête', async () => {
    storeTokens('acces-1', 'refresh-1');
    const fetchMock = makeFetchMock(makeUser());
    vi.stubGlobal('fetch', fetchMock);

    await fetchCurrentUser();

    const headers = fetchMock.mock.calls[0][1]?.headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer acces-1');
  });

  it('construit les paramètres de recherche et de pagination', async () => {
    storeTokens('acces-1', 'refresh-1');
    const fetchMock = makeFetchMock({ items: [], total: 0, limit: 20, offset: 0 });
    vi.stubGlobal('fetch', fetchMock);

    await fetchPatients({ search: '  Ali  ', limit: 10, offset: 30 });

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain(`${API_BASE}/patients?`);
    expect(url).toContain('search=Ali');
    expect(url).toContain('limit=10');
    expect(url).toContain('offset=30');
  });

  it('omet le paramètre de recherche quand il est vide', async () => {
    storeTokens('acces-1', 'refresh-1');
    const fetchMock = makeFetchMock({ items: [], total: 0, limit: 20, offset: 0 });
    vi.stubGlobal('fetch', fetchMock);

    await fetchPatients({ search: '   ' });

    expect(String(fetchMock.mock.calls[0][0])).not.toContain('search=');
  });
});
