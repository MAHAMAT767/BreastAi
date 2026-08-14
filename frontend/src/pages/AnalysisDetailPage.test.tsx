import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '@/App';
import { clearTokens } from '@/lib/tokens';
import { makeAnalysis, makePatient, makeUser, mockApi, renderWithProviders } from '@/test-utils';

const ME = { 'GET /auth/me': { body: makeUser() } };
const PATIENT = { 'GET /patients/patient-1': { body: makePatient() } };

beforeEach(() => {
  clearTokens();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearTokens();
});

function openAnalysis(overrides = {}) {
  const analysis = makeAnalysis(overrides);
  const mocked = mockApi({
    ...ME,
    ...PATIENT,
    'GET /analyses/analysis-1': { body: analysis },
    'GET /analyses/analysis-1/image': { body: {} },
    'PATCH /analyses/analysis-1/review': { body: analysis },
    'POST /analyses/analysis-1/infer': { body: analysis },
  });
  renderWithProviders(<App />, { route: '/analyses/analysis-1', authenticated: true });
  return { analysis, ...mocked };
}

describe("Résultat d'analyse", () => {
  it('affiche la classification et la probabilité', async () => {
    openAnalysis({ prediction: 'malignant', probability: 0.873, confidence: 0.873 });

    expect(await screen.findByText('Probabilité de malignité')).toBeInTheDocument();
    expect(screen.getAllByText('87.3 %').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Malin/).length).toBeGreaterThan(0);
  });

  it("affiche le temps d'inférence et la version du modèle", async () => {
    openAnalysis({ inference_time_ms: 842.4, model_version: 'placeholder-efficientnet_b0-imagenet' });

    expect(await screen.findByText('842 ms')).toBeInTheDocument();
    expect(screen.getByText('placeholder-efficientnet_b0-imagenet')).toBeInTheDocument();
  });

  it("affiche l'avertissement de modèle de démonstration en tête", async () => {
    openAnalysis({
      is_placeholder_model: true,
      model_status: 'placeholder',
      model_warning: '⚠️ MODÈLE DE DÉMONSTRATION — AUCUNE VALEUR CLINIQUE. Bruit.',
    });

    const alerts = await screen.findAllByRole('alert');
    expect(alerts[0]).toHaveTextContent(/AUCUNE VALEUR CLINIQUE/);
    // Le message n'est affiché qu'une fois : le composant n'ajoute pas de titre
    // qui redirait la même phrase.
    expect(alerts[0].textContent?.match(/AUCUNE VALEUR CLINIQUE/g)).toHaveLength(1);
  });

  // Le cas qui a motivé la séparation des deux notions : un modèle réellement
  // entraîné, mais dont la valeur clinique n'a jamais été établie, ne doit pas
  // passer pour un modèle validé sous prétexte qu'il n'est plus un placeholder.
  it("avertit pour un modèle entraîné mais non validé cliniquement", async () => {
    openAnalysis({
      is_placeholder_model: false,
      clinically_validated: false,
      model_status: 'trained_unvalidated',
      model_warning:
        '⚠️ MODÈLE ENTRAÎNÉ MAIS NON VALIDÉ CLINIQUEMENT — à visée académique.',
      model_version: 'efficientnet_b0-mini-mias-v1',
    });

    const alerts = await screen.findAllByRole('alert');
    expect(alerts[0]).toHaveTextContent(/NON VALIDÉ CLINIQUEMENT/);
    // Et surtout : ce n'est pas l'avertissement du placeholder qui s'affiche.
    expect(alerts[0]).not.toHaveTextContent(/AUCUNE VALEUR CLINIQUE/);
  });

  it("n'affiche aucun avertissement de provenance pour un modèle validé", async () => {
    openAnalysis({
      is_placeholder_model: false,
      clinically_validated: true,
      model_status: 'validated',
      model_warning: null,
      model_version: 'efficientnet_b0-cbis-ddsm-v1',
    });

    await screen.findByText('efficientnet_b0-cbis-ddsm-v1');
    expect(screen.queryByText(/AUCUNE VALEUR CLINIQUE/)).not.toBeInTheDocument();
    expect(screen.queryByText(/NON VALIDÉ CLINIQUEMENT/)).not.toBeInTheDocument();
  });

  it('rappelle la limite du Grad-CAM', async () => {
    openAnalysis({
      has_gradcam: true,
      gradcam_disclaimer:
        "La carte indique les régions ayant influencé la décision, et non l'emplacement d'une lésion.",
    });

    expect(await screen.findByText(/non l'emplacement d'une lésion/)).toBeInTheDocument();
  });

  it('situe la zone suspecte', async () => {
    openAnalysis({ suspicious_region: { x: 120, y: 40, width: 90, height: 110 } });

    expect(await screen.findByText(/90 × 110 pixels/)).toBeInTheDocument();
  });

  it('affiche les deux images de l’analyse', async () => {
    openAnalysis({ has_gradcam: true });

    await waitFor(() => {
      expect(
        screen.getByAltText('Image prétraitée, telle que vue par le modèle'),
      ).toBeInTheDocument();
    });
    expect(screen.getByAltText('Superposition Grad-CAM')).toBeInTheDocument();
  });

  it('signale une analyse en échec sans perdre le cliché', async () => {
    openAnalysis({ status: 'failed', error_message: 'Décodage impossible.', prediction: null });

    expect(await screen.findByText("L'analyse a échoué")).toBeInTheDocument();
    expect(screen.getByText(/le cliché reste archivé/i)).toBeInTheDocument();
  });
});

describe('Lecture médicale', () => {
  it('enregistre le commentaire et la validation', async () => {
    const { calls } = openAnalysis();
    await screen.findByText('Lecture médicale');

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Commentaire'), 'Sein dense, contrôle à 12 mois.');
    await user.click(screen.getByLabelText(/je valide ce compte rendu/));
    await user.click(screen.getByRole('button', { name: 'Enregistrer la lecture' }));

    await waitFor(() => {
      const patch = calls.find((call) => call.method === 'PATCH');
      expect(patch?.body).toMatchObject({
        doctor_comment: 'Sein dense, contrôle à 12 mois.',
        doctor_validated: true,
      });
    });
  });

  it('précise que la lecture du médecin prime sur le modèle', async () => {
    openAnalysis();

    expect(
      await screen.findByText(/fait foi cliniquement, et non la sortie du modèle/),
    ).toBeInTheDocument();
  });
});

describe('Compte rendu', () => {
  it('désactive le téléchargement tant que l’analyse n’est pas terminée', async () => {
    openAnalysis({ status: 'pending', prediction: null });

    const button = await screen.findByRole('button', { name: 'Télécharger le PDF' });
    expect(button).toBeDisabled();
  });

  it('permet le téléchargement pour une analyse terminée', async () => {
    openAnalysis({ status: 'completed' });

    const button = await screen.findByRole('button', { name: 'Télécharger le PDF' });
    expect(button).toBeEnabled();
  });

  it("affiche l'empreinte du rapport quand il existe", async () => {
    openAnalysis({
      has_report: true,
      report_generated_at: '2026-08-08T10:00:00Z',
      report_signature: 'a'.repeat(64),
    });

    expect(await screen.findByText(/empreinte/)).toBeInTheDocument();
  });
});

describe('Relance', () => {
  it("rejoue l'inférence", async () => {
    const { calls } = openAnalysis();
    const button = await screen.findByRole('button', { name: "Relancer l'analyse" });

    await userEvent.setup().click(button);

    await waitFor(() => {
      expect(calls.some((call) => call.url.includes('/infer'))).toBe(true);
    });
  });
});

describe('Dépôt de mammographie', () => {
  function openPatient() {
    return mockApi({
      ...ME,
      ...PATIENT,
      'GET /analyses': { body: { items: [], total: 0, limit: 10, offset: 0 } },
    });
  }

  it('refuse un format non accepté sans appeler le serveur', async () => {
    const { calls } = openPatient();
    renderWithProviders(<App />, { route: '/patients/patient-1', authenticated: true });
    await screen.findByText('Déposer une mammographie');

    const input = screen.getByLabelText('Fichier de mammographie');
    // `applyAccept: false` : l'attribut `accept` filtre déjà le sélecteur de
    // fichiers du navigateur, mais il ne protège de rien — un glisser-déposer
    // ou un `accept` ignoré peut apporter n'importe quoi. C'est le contrôle
    // applicatif qu'on veut vérifier ici.
    const user = userEvent.setup({ applyAccept: false });
    await user.upload(
      input,
      new File(['contenu'], 'rapport.pdf', { type: 'application/pdf' }),
    );

    expect(await screen.findByText(/Format non accepté/)).toBeInTheDocument();
    expect(calls.filter((call) => call.method === 'POST')).toHaveLength(0);
  });

  it('accepte un DICOM et propose de lancer l’analyse', async () => {
    openPatient();
    renderWithProviders(<App />, { route: '/patients/patient-1', authenticated: true });
    await screen.findByText('Déposer une mammographie');

    const input = screen.getByLabelText('Fichier de mammographie');
    await userEvent
      .setup()
      .upload(input, new File(['pixels'], 'mammo.dcm', { type: 'application/dicom' }));

    expect(await screen.findByText('mammo.dcm')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: "Lancer l'analyse" })).toBeEnabled();
  });

  it('liste les analyses du dossier', async () => {
    mockApi({
      ...ME,
      ...PATIENT,
      'GET /analyses': {
        body: {
          items: [makeAnalysis({ prediction: 'benign', probability: 0.21 })],
          total: 1,
          limit: 10,
          offset: 0,
        },
      },
    });
    renderWithProviders(<App />, { route: '/patients/patient-1', authenticated: true });

    const table = await screen.findByRole('table', { name: /Analyses du dossier/ });
    expect(within(table).getByText('mammo.png')).toBeInTheDocument();
    expect(within(table).getByText(/Bénin/)).toBeInTheDocument();
  });
});
