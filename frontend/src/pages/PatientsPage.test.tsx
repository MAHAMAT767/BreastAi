import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '@/App';
import { clearTokens } from '@/lib/tokens';
import { makePatient, makeUser, mockApi, renderWithProviders } from '@/test-utils';

const ME = { 'GET /auth/me': { body: makeUser() } };

function pageOf(items: ReturnType<typeof makePatient>[], total = items.length) {
  return { items, total, limit: 20, offset: 0 };
}

beforeEach(() => clearTokens());
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearTokens();
});

describe('Liste des patients', () => {
  it('affiche les dossiers renvoyés par l’API', async () => {
    mockApi({
      ...ME,
      'GET /patients': {
        body: pageOf([
          makePatient(),
          makePatient({ id: 'patient-2', code: 'TCD-2026-0002', full_name: 'Zara Oumar' }),
        ]),
      },
    });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });

    expect(await screen.findByText('Amina Ali')).toBeInTheDocument();
    expect(screen.getByText('Zara Oumar')).toBeInTheDocument();
    expect(screen.getByText('TCD-2026-0001')).toBeInTheDocument();
  });

  it("affiche l'âge à côté de la date de naissance", async () => {
    // L'âge conditionne l'interprétation d'une mammographie : le calculer de
    // tête à chaque dossier est une perte de temps.
    mockApi({ ...ME, 'GET /patients': { body: pageOf([makePatient({ birth_date: '1980-05-12' })]) } });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });

    expect(await screen.findByText(/12\/05\/1980 \(\d+ ans\)/)).toBeInTheDocument();
  });

  it('indique quand aucun dossier n’est enregistré', async () => {
    mockApi({ ...ME, 'GET /patients': { body: pageOf([]) } });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });

    expect(await screen.findByText('Aucun dossier enregistré')).toBeInTheDocument();
  });

  it('remonte une erreur de chargement', async () => {
    mockApi({ ...ME, 'GET /patients': { status: 500, body: { detail: 'Panne serveur.' } } });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });

    expect(await screen.findByRole('alert')).toHaveTextContent('Panne serveur.');
  });

  it('propose un lien vers chaque fiche', async () => {
    mockApi({ ...ME, 'GET /patients': { body: pageOf([makePatient()]) } });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });

    const row = (await screen.findByText('Amina Ali')).closest('tr');
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByRole('link', { name: 'Ouvrir' })).toHaveAttribute(
      'href',
      '/patients/patient-1',
    );
  });
});

describe('Recherche', () => {
  it('transmet le terme saisi à l’API', async () => {
    const { calls } = mockApi({
      ...ME,
      'GET /patients': { body: pageOf([makePatient()]) },
    });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });
    await screen.findByText('Amina Ali');

    await userEvent.setup().type(screen.getByLabelText('Rechercher un patient'), 'Ali');

    await waitFor(() => {
      const searchCall = calls.find((call) => call.url.includes('search=Ali'));
      expect(searchCall).toBeDefined();
    });
  });

  it('ne déclenche pas une requête par frappe', async () => {
    // Sans anti-rebond, dix caractères tapés produiraient dix appels dont neuf
    // déjà obsolètes en arrivant.
    const { calls } = mockApi({ ...ME, 'GET /patients': { body: pageOf([makePatient()]) } });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });
    await screen.findByText('Amina Ali');

    const before = calls.filter((call) => call.url.includes('/patients?')).length;
    await userEvent.setup().type(screen.getByLabelText('Rechercher un patient'), 'Abakar');

    await waitFor(() => {
      const after = calls.filter((call) => call.url.includes('/patients?')).length;
      expect(after - before).toBeLessThan(6);
    });
  });

  it('explique une recherche sans résultat', async () => {
    mockApi({ ...ME, 'GET /patients': { body: pageOf([]) } });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });
    await screen.findByText('Aucun dossier enregistré');

    await userEvent.setup().type(screen.getByLabelText('Rechercher un patient'), 'introuvable');

    expect(await screen.findByText('Aucun dossier ne correspond')).toBeInTheDocument();
  });
});

describe('Pagination', () => {
  it("n'affiche pas de pagination sous le seuil d'une page", async () => {
    mockApi({ ...ME, 'GET /patients': { body: pageOf([makePatient()], 1) } });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });
    await screen.findByText('Amina Ali');

    expect(screen.queryByRole('navigation', { name: 'Pagination' })).not.toBeInTheDocument();
  });

  it('affiche la pagination au-delà d’une page et désactive « Précédent »', async () => {
    mockApi({ ...ME, 'GET /patients': { body: pageOf([makePatient()], 45) } });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });
    await screen.findByText('Amina Ali');

    expect(screen.getByRole('navigation', { name: 'Pagination' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Précédent' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Suivant' })).toBeEnabled();
  });

  it('demande la page suivante avec le bon décalage', async () => {
    const { calls } = mockApi({ ...ME, 'GET /patients': { body: pageOf([makePatient()], 45) } });
    renderWithProviders(<App />, { route: '/patients', authenticated: true });
    await screen.findByText('Amina Ali');

    await userEvent.setup().click(screen.getByRole('button', { name: 'Suivant' }));

    await waitFor(() => {
      expect(calls.some((call) => call.url.includes('offset=20'))).toBe(true);
    });
  });
});

describe('Fiche patient', () => {
  it("affiche l'historique médical", async () => {
    mockApi({
      ...ME,
      'GET /patients/patient-1': {
        body: makePatient({
          medical_history: 'Antécédent familial au premier degré.\nNulliparité.',
        }),
      },
    });
    renderWithProviders(<App />, { route: '/patients/patient-1', authenticated: true });

    expect(await screen.findByText(/Antécédent familial au premier degré/)).toBeInTheDocument();
  });

  it("signale l'absence d'antécédents plutôt que de laisser un vide", async () => {
    mockApi({ ...ME, 'GET /patients/patient-1': { body: makePatient() } });
    renderWithProviders(<App />, { route: '/patients/patient-1', authenticated: true });

    expect(await screen.findByText('Aucun antécédent renseigné.')).toBeInTheDocument();
  });

  it('demande confirmation avant suppression', async () => {
    const { calls } = mockApi({
      ...ME,
      'GET /patients/patient-1': { body: makePatient() },
      'DELETE /patients/patient-1': { body: { message: 'Dossier patient supprimé.' } },
    });
    renderWithProviders(<App />, { route: '/patients/patient-1', authenticated: true });
    await screen.findByRole('heading', { name: 'Amina Ali' });

    await userEvent.setup().click(screen.getByRole('button', { name: 'Supprimer' }));

    expect(await screen.findByText('Supprimer ce dossier ?')).toBeInTheDocument();
    expect(calls.filter((call) => call.method === 'DELETE')).toHaveLength(0);
  });

  it('précise que la suppression est logique', async () => {
    mockApi({ ...ME, 'GET /patients/patient-1': { body: makePatient() } });
    renderWithProviders(<App />, { route: '/patients/patient-1', authenticated: true });
    await screen.findByRole('heading', { name: 'Amina Ali' });

    await userEvent.setup().click(screen.getByRole('button', { name: 'Supprimer' }));

    expect(await screen.findByText(/aucune donnée n'est\s+effacée de la base/)).toBeInTheDocument();
  });

  it('supprime après confirmation', async () => {
    const { calls } = mockApi({
      ...ME,
      'GET /patients/patient-1': { body: makePatient() },
      'DELETE /patients/patient-1': { body: { message: 'Dossier patient supprimé.' } },
      'GET /patients': { body: pageOf([]) },
    });
    renderWithProviders(<App />, { route: '/patients/patient-1', authenticated: true });
    await screen.findByRole('heading', { name: 'Amina Ali' });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Supprimer' }));
    await user.click(screen.getByRole('button', { name: 'Confirmer la suppression' }));

    await waitFor(() => {
      expect(calls.some((call) => call.method === 'DELETE')).toBe(true);
    });
  });
});

describe('Formulaire patient', () => {
  it('crée un dossier et redirige vers sa fiche', async () => {
    const created = makePatient({ id: 'patient-9', code: 'TCD-2026-0042' });
    const { calls } = mockApi({
      ...ME,
      'POST /patients': { status: 201, body: created },
      'GET /patients/patient-9': { body: created },
    });
    renderWithProviders(<App />, { route: '/patients/nouveau', authenticated: true });

    // La restauration de session doit aboutir avant que le formulaire ne soit
    // monté : sans cette attente, le rendu n'affiche encore que le spinner.
    await screen.findByRole('heading', { name: 'Nouveau dossier patient' });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Code dossier/), 'TCD-2026-0042');
    await user.type(screen.getByLabelText(/^Prénom/), 'Amina');
    await user.type(screen.getByLabelText(/^Nom/), 'Ali');
    await user.click(screen.getByRole('button', { name: 'Créer le dossier' }));

    await waitFor(() => {
      const post = calls.find((call) => call.method === 'POST' && call.url.includes('/patients'));
      expect(post?.body).toMatchObject({ code: 'TCD-2026-0042', first_name: 'Amina' });
    });
  });

  it('envoie null pour les champs laissés vides', async () => {
    // L'API attend `null`, pas une chaîne vide : une chaîne vide serait
    // enregistrée telle quelle et fausserait ensuite les affichages.
    const { calls } = mockApi({
      ...ME,
      'POST /patients': { status: 201, body: makePatient({ id: 'patient-9' }) },
      'GET /patients/patient-9': { body: makePatient({ id: 'patient-9' }) },
    });
    renderWithProviders(<App />, { route: '/patients/nouveau', authenticated: true });

    // La restauration de session doit aboutir avant que le formulaire ne soit
    // monté : sans cette attente, le rendu n'affiche encore que le spinner.
    await screen.findByRole('heading', { name: 'Nouveau dossier patient' });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Code dossier/), 'TCD-2026-0042');
    await user.type(screen.getByLabelText(/^Prénom/), 'Amina');
    await user.type(screen.getByLabelText(/^Nom/), 'Ali');
    await user.click(screen.getByRole('button', { name: 'Créer le dossier' }));

    await waitFor(() => {
      const post = calls.find((call) => call.method === 'POST' && call.url.includes('/patients'));
      expect(post?.body).toMatchObject({ phone: null, medical_history: null });
    });
  });

  it('affiche le conflit renvoyé sur un code déjà utilisé', async () => {
    mockApi({
      ...ME,
      'POST /patients': {
        status: 409,
        body: { detail: 'Un dossier existe déjà pour ce code patient.' },
      },
    });
    renderWithProviders(<App />, { route: '/patients/nouveau', authenticated: true });
    await screen.findByRole('heading', { name: 'Nouveau dossier patient' });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Code dossier/), 'TCD-2026-0001');
    await user.type(screen.getByLabelText(/^Prénom/), 'Amina');
    await user.type(screen.getByLabelText(/^Nom/), 'Ali');
    await user.click(screen.getByRole('button', { name: 'Créer le dossier' }));

    expect(await screen.findByText(/Un dossier existe déjà pour ce code/)).toBeInTheDocument();
  });

  it('pré-remplit le formulaire en modification', async () => {
    mockApi({
      ...ME,
      'GET /patients/patient-1': {
        body: makePatient({ phone: '+235 66 00 00 00', medical_history: 'Antécédent familial.' }),
      },
    });
    renderWithProviders(<App />, { route: '/patients/patient-1/modifier', authenticated: true });

    await waitFor(() => {
      expect(screen.getByLabelText(/Code dossier/)).toHaveValue('TCD-2026-0001');
    });
    expect(screen.getByLabelText(/Téléphone/)).toHaveValue('+235 66 00 00 00');
    expect(screen.getByLabelText(/Antécédents/)).toHaveValue('Antécédent familial.');
  });

  it('propose les trois sexes, dont masculin', async () => {
    mockApi(ME);
    renderWithProviders(<App />, { route: '/patients/nouveau', authenticated: true });

    const select = await screen.findByLabelText(/^Sexe/);
    expect(within(select).getByRole('option', { name: 'Masculin' })).toBeInTheDocument();
  });
});
