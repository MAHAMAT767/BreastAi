import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '@/App';
import { clearTokens } from '@/lib/tokens';
import { makeAnalysis, makeUser, mockApi, renderWithProviders } from '@/test-utils';

const ME = { 'GET /auth/me': { body: makeUser() } };

function page(items: ReturnType<typeof makeAnalysis>[], total = items.length) {
  return { items, total, limit: 20, offset: 0 };
}

beforeEach(() => clearTokens());
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearTokens();
});

function openHistory(body: unknown = page([makeAnalysis()])) {
  const mocked = mockApi({ ...ME, 'GET /analyses': { body } });
  renderWithProviders(<App />, { route: '/analyses', authenticated: true });
  return mocked;
}

/** Dernier appel à /analyses, pour lire les paramètres transmis. */
function lastQuery(calls: { url: string; method: string }[]): URLSearchParams {
  const call = [...calls].reverse().find((entry) => entry.url.includes('/analyses?'));
  return new URLSearchParams(call?.url.split('?')[1] ?? '');
}

describe('Historique', () => {
  it('liste les analyses', async () => {
    openHistory(
      page([
        makeAnalysis({ id: 'a1', original_filename: 'mammo-1.dcm' }),
        makeAnalysis({ id: 'a2', original_filename: 'mammo-2.png' }),
      ]),
    );

    expect(await screen.findByText('mammo-1.dcm')).toBeInTheDocument();
    expect(screen.getByText('mammo-2.png')).toBeInTheDocument();
  });

  it('affiche le résultat et la relecture', async () => {
    openHistory(
      page([makeAnalysis({ prediction: 'malignant', probability: 0.87, doctor_validated: true })]),
    );

    const row = (await screen.findByText('mammo.png')).closest('tr') as HTMLElement;
    expect(within(row).getByText(/Malin/)).toBeInTheDocument();
    // La relecture est rendue par un badge, au même vocabulaire visuel que le
    // résultat, plutôt que par un « Oui » / « Non » en texte brut.
    expect(within(row).getByText('Validée')).toBeInTheDocument();
  });

  it('propose un lien vers chaque analyse', async () => {
    openHistory(page([makeAnalysis({ id: 'analysis-7' })]));

    const row = (await screen.findByText('mammo.png')).closest('tr') as HTMLElement;
    expect(within(row).getByRole('link', { name: 'Ouvrir' })).toHaveAttribute(
      'href',
      '/analyses/analysis-7',
    );
  });

  it('signale une base vide', async () => {
    openHistory(page([]));

    expect(await screen.findByText('Aucune analyse enregistrée')).toBeInTheDocument();
  });
});

describe('Recherche', () => {
  it('filtre par patient', async () => {
    const { calls } = openHistory();
    await screen.findByText('mammo.png');

    await userEvent.setup().type(screen.getByLabelText('Patient'), 'Abakar');

    await waitFor(() => expect(lastQuery(calls).get('search')).toBe('Abakar'));
  });

  it('filtre par diagnostic', async () => {
    const { calls } = openHistory();
    await screen.findByText('mammo.png');

    await userEvent.setup().selectOptions(screen.getByLabelText('Diagnostic'), 'malignant');

    await waitFor(() => expect(lastQuery(calls).get('prediction')).toBe('malignant'));
  });

  it('filtre par statut', async () => {
    const { calls } = openHistory();
    await screen.findByText('mammo.png');

    await userEvent.setup().selectOptions(screen.getByLabelText('Statut'), 'failed');

    await waitFor(() => expect(lastQuery(calls).get('status')).toBe('failed'));
  });

  it('filtre par période', async () => {
    const { calls } = openHistory();
    await screen.findByText('mammo.png');

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Du'), '2026-05-01');
    await user.type(screen.getByLabelText('Au'), '2026-05-31');

    await waitFor(() => {
      const query = lastQuery(calls);
      expect(query.get('date_from')).toBe('2026-05-01');
      expect(query.get('date_to')).toBe('2026-05-31');
    });
  });

  it("n'envoie jamais un critère vide", async () => {
    // `prediction=` serait refusé par le serveur : il n'accepte que
    // `benign` ou `malignant`.
    const { calls } = openHistory();
    await screen.findByText('mammo.png');

    const query = lastQuery(calls);
    expect(query.has('prediction')).toBe(false);
    expect(query.has('search')).toBe(false);
    expect(query.has('date_from')).toBe(false);
  });

  it('combine les critères', async () => {
    const { calls } = openHistory();
    await screen.findByText('mammo.png');

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Patient'), 'Abakar');
    await user.selectOptions(screen.getByLabelText('Diagnostic'), 'benign');

    await waitFor(() => {
      const query = lastQuery(calls);
      expect(query.get('search')).toBe('Abakar');
      expect(query.get('prediction')).toBe('benign');
    });
  });

  it('explique une recherche sans résultat', async () => {
    const { fetchMock } = openHistory(page([]));
    await screen.findByText('Aucune analyse enregistrée');
    void fetchMock;

    await userEvent.setup().selectOptions(screen.getByLabelText('Diagnostic'), 'malignant');

    expect(await screen.findByText('Aucune analyse ne correspond')).toBeInTheDocument();
  });

  it('permet de réinitialiser les filtres', async () => {
    openHistory();
    await screen.findByText('mammo.png');

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText('Diagnostic'), 'malignant');
    await user.click(await screen.findByRole('button', { name: 'Réinitialiser les filtres' }));

    await waitFor(() => expect(screen.getByLabelText('Diagnostic')).toHaveValue(''));
  });

  it('borne la période pour empêcher un intervalle inversé', async () => {
    openHistory();
    await screen.findByText('mammo.png');

    await userEvent.setup().type(screen.getByLabelText('Du'), '2026-05-10');

    await waitFor(() => expect(screen.getByLabelText('Au')).toHaveAttribute('min', '2026-05-10'));
  });
});

describe('Pagination', () => {
  it('revient à la première page quand un filtre change', async () => {
    // Rester à l'offset 40 sur un résultat qui n'a que 3 lignes afficherait
    // une page vide.
    const { calls } = openHistory(page([makeAnalysis()], 60));
    await screen.findByText('mammo.png');

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Suivant' }));
    await waitFor(() => expect(lastQuery(calls).get('offset')).toBe('20'));

    await user.selectOptions(screen.getByLabelText('Diagnostic'), 'benign');

    await waitFor(() => {
      const query = lastQuery(calls);
      expect(query.get('prediction')).toBe('benign');
      expect(query.get('offset')).toBe('0');
    });
  });

  it("n'affiche pas de pagination sous une page", async () => {
    openHistory(page([makeAnalysis()], 1));
    await screen.findByText('mammo.png');

    expect(screen.queryByRole('navigation', { name: 'Pagination' })).not.toBeInTheDocument();
  });
});

describe('Accès', () => {
  it('est refusé au rôle chercheur', async () => {
    mockApi({ 'GET /auth/me': { body: makeUser({ role: 'researcher' }) } });
    renderWithProviders(<App />, { route: '/analyses', authenticated: true });

    expect(await screen.findByText('Accès refusé')).toBeInTheDocument();
  });
});
