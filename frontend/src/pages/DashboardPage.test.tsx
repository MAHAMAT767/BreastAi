import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '@/App';
import { formatMonth } from '@/components/charts';
import { clearTokens } from '@/lib/tokens';
import { makeStats, makeUser, mockApi, renderWithProviders } from '@/test-utils';

const ME = { 'GET /auth/me': { body: makeUser() } };

beforeEach(() => clearTokens());
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearTokens();
});

function openDashboard(overrides = {}) {
  const mocked = mockApi({
    ...ME,
    'GET /stats/dashboard': { body: makeStats(overrides) },
  });
  renderWithProviders(<App />, { route: '/tableau-de-bord', authenticated: true });
  return mocked;
}

/** Valeur portée par une tuile, cadrée sur elle : les chiffres se répètent ailleurs. */
function tileValue(label: string): string {
  const tile = screen.getByText(label).closest('div');
  if (!tile) throw new Error(`Tuile introuvable : ${label}`);
  const value = within(tile).getAllByText(/\S/)[1];
  return value.textContent ?? '';
}

describe('Indicateurs', () => {
  it('affiche les compteurs principaux', async () => {
    openDashboard();
    await screen.findByText('Patients suivis');

    expect(tileValue('Patients suivis')).toBe('12');
    expect(tileValue('Analyses déposées')).toBe('30');
    expect(tileValue('Résultats bénins')).toBe('20');
    expect(tileValue('Résultats malins')).toBe('8');
  });

  it('affiche le temps moyen en secondes au-delà de la seconde', async () => {
    openDashboard({ average_inference_time_ms: 1500 });

    expect(await screen.findByText('1.5 s')).toBeInTheDocument();
  });

  it('affiche le temps moyen en millisecondes en deçà', async () => {
    openDashboard({ average_inference_time_ms: 640 });

    expect(await screen.findByText('640 ms')).toBeInTheDocument();
  });

  it('remplace une valeur absente par un tiret', async () => {
    openDashboard({ average_inference_time_ms: null, doctor_validation_rate: null });

    expect(await screen.findByText('Temps moyen d\'analyse')).toBeInTheDocument();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
});

describe('Honnêteté des chiffres', () => {
  it("n'affiche aucune « précision du modèle »", async () => {
    // La spécification d'origine demandait une précision du modèle. L'afficher
    // laisserait croire que la justesse a été mesurée : elle ne l'est pas.
    openDashboard();
    await screen.findByText('Patients suivis');

    expect(screen.queryByText(/précision du modèle/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/exactitude du modèle/i)).not.toBeInTheDocument();
  });

  it('explique pourquoi aucun taux d’exactitude n’est publié', async () => {
    openDashboard();

    expect(
      await screen.findByText(/Pourquoi aucun taux d'exactitude n'est affiché/),
    ).toBeInTheDocument();
    expect(screen.getByText(/pas la justesse du modèle/)).toBeInTheDocument();
  });

  it('nomme le taux affiché « analyses relues », pas une performance', async () => {
    openDashboard();

    expect(await screen.findByText('Analyses relues par un médecin')).toBeInTheDocument();
    expect(screen.getByText(/14 sur 28 analyses terminées/)).toBeInTheDocument();
  });

  it('précise que les comptes bénin/malin ne sont pas validés cliniquement', async () => {
    openDashboard();
    await screen.findByText('Résultats malins');

    expect(
      screen.getAllByText('Sortie du modèle, non validée cliniquement'),
    ).toHaveLength(2);
  });

  it('affiche l’avertissement de modèle de démonstration', async () => {
    openDashboard({ is_placeholder_model: true, model_status: 'placeholder' });

    const alerts = await screen.findAllByRole('alert');
    expect(alerts[0]).toHaveTextContent(/AUCUNE VALEUR CLINIQUE/);
  });

  it('avertit pour un modèle entraîné mais non validé cliniquement', async () => {
    openDashboard({
      is_placeholder_model: false,
      clinically_validated: false,
      model_status: 'trained_unvalidated',
      model_warning:
        '⚠️ MODÈLE ENTRAÎNÉ MAIS NON VALIDÉ CLINIQUEMENT — à visée académique.',
      model_versions: ['efficientnet_b0-mini-mias-v1'],
    });

    const alerts = await screen.findAllByRole('alert');
    expect(alerts[0]).toHaveTextContent(/NON VALIDÉ CLINIQUEMENT/);
  });

  it('retire l’avertissement de provenance pour un modèle validé', async () => {
    openDashboard({
      is_placeholder_model: false,
      clinically_validated: true,
      model_status: 'validated',
      model_warning: null,
      model_versions: ['efficientnet_b0-cbis-ddsm-v1'],
    });
    await screen.findByText('Patients suivis');

    expect(screen.queryByText(/AUCUNE VALEUR CLINIQUE/)).not.toBeInTheDocument();
    expect(screen.queryByText(/NON VALIDÉ CLINIQUEMENT/)).not.toBeInTheDocument();
  });

  it('signale la coexistence de plusieurs versions de modèle', async () => {
    openDashboard({
      model_versions: ['efficientnet_b0-cbis-ddsm-v1', 'placeholder-efficientnet_b0-imagenet'],
    });

    expect(await screen.findByText(/Plusieurs versions coexistent/)).toBeInTheDocument();
  });
});

describe('Répartition des résultats', () => {
  it('affiche la légende avec les valeurs, pas seulement des couleurs', async () => {
    openDashboard({ benign_count: 20, malignant_count: 8 });

    expect(await screen.findByText(/Bénin — 20 \(71.4 %\)/)).toBeInTheDocument();
    expect(screen.getByText(/Malin — 8 \(28.6 %\)/)).toBeInTheDocument();
  });

  it('décrit la barre pour les lecteurs d’écran', async () => {
    openDashboard({ benign_count: 20, malignant_count: 8 });

    expect(
      await screen.findByRole('img', { name: 'Bénin 20 sur 28, malin 8 sur 28' }),
    ).toBeInTheDocument();
  });

  it('gère une absence totale d’analyse terminée', async () => {
    openDashboard({ benign_count: 0, malignant_count: 0, completed_analyses: 0 });

    expect(await screen.findByText('Aucune analyse terminée.')).toBeInTheDocument();
  });
});

describe('Analyses par mois', () => {
  it('propose les données sous forme de tableau', async () => {
    // Un graphique ne doit jamais être le seul accès à ses valeurs.
    openDashboard();
    await screen.findByText('Analyses par mois');

    await userEvent.setup().click(screen.getByText('Voir les données'));

    const table = screen.getByRole('table');
    expect(within(table).getByText(formatMonth('2026-07'))).toBeInTheDocument();
    expect(within(table).getByText('12')).toBeInTheDocument();
  });

  it('signale une période sans activité', async () => {
    openDashboard({
      monthly: [{ month: '2026-08', total: 0, benign: 0, malignant: 0 }],
    });

    expect(
      await screen.findByText('Aucune analyse terminée sur les douze derniers mois.'),
    ).toBeInTheDocument();
  });

  it('précise que les mois vides valent zéro', async () => {
    openDashboard();

    expect(await screen.findByText(/Un mois sans activité\s+vaut zéro/)).toBeInTheDocument();
  });
});

describe('Accès', () => {
  it('est ouvert au rôle chercheur', async () => {
    // Le tableau de bord n'expose que des agrégats : c'est précisément le
    // périmètre de ce rôle, à qui les dossiers nominatifs restent fermés.
    mockApi({
      'GET /auth/me': { body: makeUser({ role: 'researcher' }) },
      'GET /stats/dashboard': { body: makeStats() },
    });
    renderWithProviders(<App />, { route: '/tableau-de-bord', authenticated: true });

    expect(await screen.findByText('Patients suivis')).toBeInTheDocument();
    expect(screen.queryByText('Accès refusé')).not.toBeInTheDocument();
  });

  it('reste proposé dans la navigation pour un chercheur', async () => {
    mockApi({
      'GET /auth/me': { body: makeUser({ role: 'researcher' }) },
      'GET /stats/dashboard': { body: makeStats() },
    });
    renderWithProviders(<App />, { route: '/tableau-de-bord', authenticated: true });
    await screen.findByText('Patients suivis');

    expect(screen.getByRole('link', { name: 'Tableau de bord' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Patients' })).not.toBeInTheDocument();
  });
});

describe('Délai de prise en charge', () => {
  it("n'apparaît pas sur le tableau de bord", async () => {
    // Le tableau de bord agrège : un délai n'y désignerait aucune analyse.
    openDashboard();
    await screen.findByText('Patients suivis');

    expect(screen.queryByText('Délai de prise en charge suggéré')).not.toBeInTheDocument();
  });
});
