import { screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '@/App';
import { clearTokens } from '@/lib/tokens';
import { makeUser, mockApi, renderWithProviders } from '@/test-utils';

beforeEach(() => {
  clearTokens();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearTokens();
});

describe('Protection des routes', () => {
  it('redirige un visiteur non connecté vers la page de connexion', async () => {
    mockApi({});
    renderWithProviders(<App />, { route: '/patients' });

    expect(await screen.findByRole('heading', { name: 'Connexion' })).toBeInTheDocument();
  });

  it("n'expose pas la liste des patients sans session", async () => {
    mockApi({});
    renderWithProviders(<App />, { route: '/patients' });

    await screen.findByRole('heading', { name: 'Connexion' });
    expect(screen.queryByRole('heading', { name: 'Patients' })).not.toBeInTheDocument();
  });

  it('laisse passer un médecin authentifié', async () => {
    mockApi({
      'GET /auth/me': { body: makeUser() },
      'GET /health': { body: { status: 'ok', version: '0.1.0', environment: 'test', app_name: 'BreastAI' } },
    });
    renderWithProviders(<App />, { route: '/', authenticated: true });

    expect(await screen.findByText(/Bonjour Dr Test/)).toBeInTheDocument();
  });

  it('refuse la section patients à un chercheur, en expliquant pourquoi', async () => {
    mockApi({ 'GET /auth/me': { body: makeUser({ role: 'researcher' }) } });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });

    expect(await screen.findByText('Accès refusé')).toBeInTheDocument();
    // Portée sur l'encadré : « Chercheur » apparaît dans plusieurs éléments
    // imbriqués, une recherche globale trouverait plusieurs correspondances.
    expect(screen.getByRole('alert')).toHaveTextContent('Chercheur');
  });

  it('ne propose pas le lien Patients à un chercheur', async () => {
    mockApi({
      'GET /auth/me': { body: makeUser({ role: 'researcher' }) },
      'GET /health': { body: { status: 'ok', version: '0.1.0', environment: 'test', app_name: 'BreastAI' } },
    });
    renderWithProviders(<App />, { route: '/', authenticated: true });

    await screen.findByText(/Bonjour/);
    expect(screen.queryByRole('link', { name: 'Patients' })).not.toBeInTheDocument();
  });

  it('efface la session si le serveur rejette le jeton conservé', async () => {
    // Un jeton en sessionStorage ne prouve rien : le compte peut avoir été
    // désactivé depuis. Seule la réponse du serveur fait foi.
    mockApi({ 'GET /auth/me': { status: 401, body: { detail: 'Session expirée.' } } });
    renderWithProviders(<App />, { route: '/', authenticated: true });

    expect(await screen.findByRole('heading', { name: 'Connexion' })).toBeInTheDocument();
  });
});

describe('Mentions permanentes', () => {
  it("affiche l'avertissement médical sur la page de connexion", async () => {
    mockApi({});
    renderWithProviders(<App />, { route: '/connexion' });

    await screen.findByRole('heading', { name: 'Connexion' });
    expect(screen.getByRole('note')).toHaveTextContent(/ne remplacent pas l'avis/);
  });

  it("affiche l'avertissement médical et la dédicace une fois connecté", async () => {
    mockApi({
      'GET /auth/me': { body: makeUser() },
      'GET /health': { body: { status: 'ok', version: '0.1.0', environment: 'test', app_name: 'BreastAI' } },
    });
    renderWithProviders(<App />, { route: '/', authenticated: true });

    await waitFor(() => expect(screen.getByRole('note')).toBeInTheDocument());
    expect(screen.getByRole('note')).toHaveTextContent(/ne remplacent pas l'avis/);
    expect(screen.getByText('Mouna Abakar')).toBeInTheDocument();
  });
});
