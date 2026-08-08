import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '@/App';
import { getAccessToken, clearTokens } from '@/lib/tokens';
import { makeUser, mockApi, renderWithProviders } from '@/test-utils';

const TOKENS = {
  access_token: 'acces-1',
  refresh_token: 'refresh-1',
  token_type: 'bearer',
  expires_in: 1800,
};

beforeEach(() => clearTokens());
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearTokens();
});

async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/Adresse e-mail/), email);
  await user.type(screen.getByLabelText(/Mot de passe/), password);
  await user.click(screen.getByRole('button', { name: 'Se connecter' }));
}

describe('Connexion', () => {
  it('connecte un utilisateur et affiche son accueil', async () => {
    mockApi({
      'POST /auth/login': { body: TOKENS },
      'GET /auth/me': { body: makeUser() },
      'GET /health': { body: { status: 'ok', version: '0.1.0', environment: 'test', app_name: 'BreastAI' } },
    });
    renderWithProviders(<App />, { route: '/connexion' });

    await fillAndSubmit('medecin@breastai.td', 'MotDePasseTest-2026');

    expect(await screen.findByText(/Bonjour Dr Test/)).toBeInTheDocument();
  });

  it('conserve les jetons renvoyés par le serveur', async () => {
    mockApi({
      'POST /auth/login': { body: TOKENS },
      'GET /auth/me': { body: makeUser() },
      'GET /health': { body: { status: 'ok', version: '0.1.0', environment: 'test', app_name: 'BreastAI' } },
    });
    renderWithProviders(<App />, { route: '/connexion' });

    await fillAndSubmit('medecin@breastai.td', 'MotDePasseTest-2026');

    await waitFor(() => expect(getAccessToken()).toBe('acces-1'));
  });

  it("envoie un formulaire OAuth2 avec le champ 'username'", async () => {
    // L'endpoint attend `application/x-www-form-urlencoded` et non du JSON :
    // envoyer du JSON produirait un 422 difficile à diagnostiquer.
    const { calls } = mockApi({
      'POST /auth/login': { body: TOKENS },
      'GET /auth/me': { body: makeUser() },
      'GET /health': { body: { status: 'ok', version: '0.1.0', environment: 'test', app_name: 'BreastAI' } },
    });
    renderWithProviders(<App />, { route: '/connexion' });

    await fillAndSubmit('medecin@breastai.td', 'MotDePasseTest-2026');

    await waitFor(() => {
      const loginCall = calls.find((call) => call.url.includes('/auth/login'));
      expect(loginCall?.body).toContain('username=medecin');
    });
  });

  it('affiche le message du serveur quand les identifiants sont faux', async () => {
    mockApi({
      'POST /auth/login': {
        status: 401,
        body: { detail: 'Adresse e-mail ou mot de passe incorrect.' },
      },
    });
    renderWithProviders(<App />, { route: '/connexion' });

    await fillAndSubmit('inconnu@breastai.td', 'mauvais-mot-de-passe');

    expect(
      await screen.findByText('Adresse e-mail ou mot de passe incorrect.'),
    ).toBeInTheDocument();
  });

  it('affiche un message compréhensible en cas de quota dépassé', async () => {
    mockApi({
      'POST /auth/login': {
        status: 429,
        body: { detail: 'Trop de tentatives. Patientez quelques instants avant de réessayer.' },
      },
    });
    renderWithProviders(<App />, { route: '/connexion' });

    await fillAndSubmit('medecin@breastai.td', 'MotDePasseTest-2026');

    expect(await screen.findByText(/Trop de tentatives/)).toBeInTheDocument();
  });

  it('reste sur la page de connexion après un échec', async () => {
    mockApi({ 'POST /auth/login': { status: 401, body: { detail: 'Identifiants invalides.' } } });
    renderWithProviders(<App />, { route: '/connexion' });

    await fillAndSubmit('inconnu@breastai.td', 'mauvais');

    await screen.findByRole('alert');
    expect(screen.getByRole('heading', { name: 'Connexion' })).toBeInTheDocument();
  });

  it('propose le lien de récupération de mot de passe', async () => {
    mockApi({});
    renderWithProviders(<App />, { route: '/connexion' });

    expect(
      await screen.findByRole('link', { name: 'Mot de passe oublié ?' }),
    ).toBeInTheDocument();
  });
});

describe('Mot de passe oublié', () => {
  it('affiche la réponse générique du serveur', async () => {
    // Le message ne doit pas varier selon que l'adresse existe ou non, faute de
    // quoi n'importe qui pourrait énumérer les comptes.
    mockApi({
      'POST /auth/password-reset/request': {
        body: {
          message:
            'Si un compte existe pour cette adresse, un lien de réinitialisation a été envoyé.',
        },
      },
    });
    renderWithProviders(<App />, { route: '/mot-de-passe-oublie' });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Adresse e-mail/), 'inconnu@breastai.td');
    await user.click(screen.getByRole('button', { name: 'Envoyer le lien' }));

    expect(await screen.findByText(/Si un compte existe pour cette adresse/)).toBeInTheDocument();
  });
});

describe('Réinitialisation du mot de passe', () => {
  it('refuse un lien sans jeton', async () => {
    mockApi({});
    renderWithProviders(<App />, { route: '/reinitialiser-mot-de-passe' });

    expect(await screen.findByText(/ne contient aucun jeton/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Réinitialiser' })).toBeDisabled();
  });

  it('refuse deux mots de passe différents sans appeler le serveur', async () => {
    const { calls } = mockApi({});
    renderWithProviders(<App />, { route: '/reinitialiser-mot-de-passe?token=jeton-valide' });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Nouveau mot de passe/), 'MotDePasseTest-2026');
    await user.type(screen.getByLabelText(/Confirmation/), 'AutreMotDePasse-2026');
    await user.click(screen.getByRole('button', { name: 'Réinitialiser' }));

    expect(await screen.findByText(/ne correspondent pas/)).toBeInTheDocument();
    expect(calls.filter((call) => call.url.includes('password-reset'))).toHaveLength(0);
  });

  it('refuse un mot de passe trop court', async () => {
    mockApi({});
    renderWithProviders(<App />, { route: '/reinitialiser-mot-de-passe?token=jeton-valide' });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Nouveau mot de passe/), 'court');
    await user.type(screen.getByLabelText(/Confirmation/), 'court');
    await user.click(screen.getByRole('button', { name: 'Réinitialiser' }));

    expect(await screen.findByText(/au moins 12 caractères/)).toBeInTheDocument();
  });

  it('renvoie vers la connexion après réinitialisation', async () => {
    mockApi({
      'POST /auth/password-reset/confirm': { body: { message: 'Mot de passe réinitialisé.' } },
    });
    renderWithProviders(<App />, { route: '/reinitialiser-mot-de-passe?token=jeton-valide' });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Nouveau mot de passe/), 'MotDePasseTest-2026');
    await user.type(screen.getByLabelText(/Confirmation/), 'MotDePasseTest-2026');
    await user.click(screen.getByRole('button', { name: 'Réinitialiser' }));

    expect(await screen.findByRole('heading', { name: 'Connexion' })).toBeInTheDocument();
  });
});
