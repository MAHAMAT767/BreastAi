/**
 * Tests d'intégration contre l'API réelle.
 *
 * Contrairement aux autres tests, `fetch` n'est pas simulé : les composants
 * parlent au backend qui tourne sur `VITE_API_URL`. C'est ce qui permet de
 * détecter les écarts qu'un faux serveur masque par construction — nom d'un
 * champ, forme d'une réponse d'erreur, encodage du formulaire de connexion.
 *
 * Le fichier s'ignore de lui-même si l'API n'est pas joignable, pour ne pas
 * transformer une absence de backend en échec de tests.
 *
 * Prérequis :
 *     backend démarré, base migrée, compte administrateur créé
 *     VITE_TEST_EMAIL / VITE_TEST_PASSWORD pour les identifiants
 *     LOGIN_RATE_LIMIT relevé côté serveur — le quota par défaut est de 10
 *     connexions par minute et par IP, et deux exécutions rapprochées de cette
 *     suite le dépassent. La limitation elle-même est couverte par les tests
 *     backend, pas ici.
 *
 * La session est ouverte une seule fois puis réutilisée : chaque connexion
 * consomme du quota et coûte un hachage bcrypt côté serveur.
 */

import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it } from 'vitest';

import App from '@/App';
import { API_URL } from '@/lib/api';
import * as api from '@/lib/api';
import { clearTokens, getAccessToken } from '@/lib/tokens';
import { renderWithProviders } from '@/test-utils';

const EMAIL = import.meta.env.VITE_TEST_EMAIL ?? 'admin@breastai.local';
const PASSWORD = import.meta.env.VITE_TEST_PASSWORD ?? 'BreastAI-Dev-2026!';

async function apiIsReachable(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`, {
      signal: AbortSignal.timeout(3000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

const reachable = await apiIsReachable();

/** Code unique par exécution : les tests écrivent dans une vraie base. */
function uniqueCode(): string {
  return `TCD-IT-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
}

const createdPatientIds: string[] = [];

/** Ouvre une session seulement si le test précédent l'a fermée. */
async function ensureSession(): Promise<void> {
  if (!getAccessToken()) {
    await api.login(EMAIL, PASSWORD);
  }
}

describe.skipIf(!reachable)("Intégration avec l'API réelle", () => {
  beforeAll(async () => {
    clearTokens();
    await ensureSession();
  });

  afterEach(async () => {
    // Certains tests coupent volontairement la session : la rouvrir ici évite
    // que le nettoyage échoue et que le test suivant reparte sans jeton.
    await ensureSession();

    // La suppression est logique côté serveur, mais laisser s'accumuler des
    // dossiers de test fausserait les comptages manuels.
    for (const id of createdPatientIds.splice(0)) {
      try {
        await api.deletePatient(id);
      } catch {
        // Le dossier a peut-être déjà été supprimé par le test lui-même.
      }
    }
  });

  it('répond sur /health', async () => {
    const health = await api.getHealth();

    expect(health.status).toBe('ok');
    expect(health.app_name).toBe('BreastAI');
  });

  it('refuse des identifiants invalides', async () => {
    await expect(api.login(EMAIL, 'mot-de-passe-manifestement-faux')).rejects.toMatchObject({
      status: 401,
    });
  });

  it('connecte, restitue le profil, puis déconnecte', async () => {
    const tokens = await api.login(EMAIL, PASSWORD);
    expect(tokens.access_token).toBeTruthy();

    const profile = await api.fetchCurrentUser();
    expect(profile.email).toBe(EMAIL.toLowerCase());
    expect(['admin', 'doctor', 'researcher']).toContain(profile.role);

    await expect(api.logout()).resolves.toHaveProperty('message');
  });

  it('refuse un accès sans jeton', async () => {
    clearTokens();

    await expect(api.fetchPatients()).rejects.toMatchObject({ status: 401 });
  });

  it('crée, lit, recherche, modifie puis supprime un dossier', async () => {
    const code = uniqueCode();

    // --- création ---
    const created = await api.createPatient({
      code,
      first_name: 'Amina',
      last_name: 'Integration',
      birth_date: '1980-05-12',
      sex: 'F',
      phone: null,
      email: null,
      address: null,
      medical_history: 'Antécédent familial au premier degré.',
      notes: null,
    });
    createdPatientIds.push(created.id);

    expect(created.code).toBe(code);
    expect(created.full_name).toBe('Amina Integration');

    // --- lecture ---
    const fetched = await api.fetchPatient(created.id);
    expect(fetched.medical_history).toBe('Antécédent familial au premier degré.');

    // --- recherche ---
    const found = await api.fetchPatients({ search: code });
    expect(found.items.map((patient) => patient.id)).toContain(created.id);

    // --- modification ---
    const updated = await api.updatePatient(created.id, { phone: '+235 66 00 00 00' });
    expect(updated.phone).toBe('+235 66 00 00 00');
    expect(updated.first_name).toBe('Amina');

    // --- suppression logique ---
    await api.deletePatient(created.id);
    createdPatientIds.pop();
    await expect(api.fetchPatient(created.id)).rejects.toMatchObject({ status: 404 });
  });

  it('refuse un code de dossier déjà utilisé', async () => {
    const code = uniqueCode();

    const payload = {
      code,
      first_name: 'Zara',
      last_name: 'Integration',
      birth_date: null,
      sex: 'F' as const,
      phone: null,
      email: null,
      address: null,
      medical_history: null,
      notes: null,
    };

    const created = await api.createPatient(payload);
    createdPatientIds.push(created.id);

    await expect(api.createPatient(payload)).rejects.toMatchObject({ status: 409 });
  });

  it('refuse une date de naissance future', async () => {
    await expect(
      api.createPatient({
        code: uniqueCode(),
        first_name: 'Test',
        last_name: 'Integration',
        birth_date: '2999-01-01',
        sex: 'F',
        phone: null,
        email: null,
        address: null,
        medical_history: null,
        notes: null,
      }),
    ).rejects.toMatchObject({ status: 422 });
  });

  it("répond la même chose pour une adresse inconnue à la récupération de mot de passe", async () => {
    const response = await api.requestPasswordReset('personne-inexistante@breastai.td');

    expect(response.message).toMatch(/Si un compte existe/);
  });

  // Délai relevé : ce test enchaîne connexion (bcrypt côté serveur), profil,
  // navigation et création — largement au-delà des 5 s par défaut de Vitest.
  it("traverse l'interface : connexion puis création de dossier", { timeout: 30_000 }, async () => {
    // Le seul test qui passe par les composants React et non par le client seul :
    // il valide l'enchaînement complet tel qu'un utilisateur le vit.
    clearTokens();
    const code = uniqueCode();

    renderWithProviders(<App />, { route: '/connexion' });

    const user = userEvent.setup();
    await user.type(await screen.findByLabelText(/Adresse e-mail/), EMAIL);
    await user.type(screen.getByLabelText(/Mot de passe/), PASSWORD);
    await user.click(screen.getByRole('button', { name: 'Se connecter' }));

    await screen.findByText(/Bonjour/, {}, { timeout: 10_000 });

    await user.click(screen.getByRole('link', { name: 'Créer un dossier' }));
    await screen.findByRole('heading', { name: 'Nouveau dossier patient' });

    await user.type(screen.getByLabelText(/Code dossier/), code);
    await user.type(screen.getByLabelText(/^Prénom/), 'Interface');
    await user.type(screen.getByLabelText(/^Nom/), 'Integration');
    await user.click(screen.getByRole('button', { name: 'Créer le dossier' }));

    // Redirection vers la fiche du dossier créé.
    await waitFor(
      () => expect(screen.getByRole('heading', { name: 'Interface Integration' })).toBeInTheDocument(),
      { timeout: 10_000 },
    );
    // Le code figure à la fois dans l'en-tête et dans la liste de définitions.
    expect(screen.getAllByText(code).length).toBeGreaterThan(0);

    const page = await api.fetchPatients({ search: code });
    createdPatientIds.push(...page.items.map((patient) => patient.id));
    expect(page.total).toBe(1);
  });
});

describe.skipIf(reachable)('Intégration avec l’API réelle', () => {
  it('est ignorée : API injoignable', () => {
    // Trace explicite dans le rapport de tests, pour qu'une exécution sans
    // backend ne passe pas pour une exécution complète.
    expect(reachable).toBe(false);
  });
});
