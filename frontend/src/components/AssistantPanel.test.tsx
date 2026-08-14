import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AssistantPanel from '@/components/AssistantPanel';
import { clearTokens, storeTokens } from '@/lib/tokens';
import { mockApi, renderWithProviders } from '@/test-utils';

const STATUS_ON = {
  enabled: true,
  model: 'Qwen/Qwen2.5-7B-Instruct',
  provider: 'Hugging Face Inference Providers',
  disclaimer: "Ses résultats ne remplacent pas l'avis d'un professionnel de santé qualifié.",
  notice: "Le contexte transmis contient les sorties du modèle, l'âge et le sexe.",
};

const ANSWER = {
  answer: 'AVERTISSEMENT\n\nLa probabilité est une sortie de classifieur.\n\nDISCLAIMER',
  answer_body: 'La probabilité est une sortie de classifieur.',
  model: 'Qwen/Qwen2.5-7B-Instruct',
  disclaimer:
    "BreastAI est un outil d'aide à la décision. Ses résultats ne remplacent pas l'avis d'un professionnel de santé qualifié.",
  is_placeholder_model: true,
  clinically_validated: false,
  model_status: 'placeholder' as const,
  model_warning: '⚠️ MODÈLE DE DÉMONSTRATION — AUCUNE VALEUR CLINIQUE.',
  context_sent: 'Contexte de l’analyse :\n- Patiente : 52 ans\n- Classification : bénin',
  usage: { total_tokens: 773 },
};

beforeEach(() => {
  clearTokens();
  storeTokens('acces', 'refresh');
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearTokens();
});

function render(routes: Record<string, unknown> = {}) {
  const mocked = mockApi({
    'GET /assistant/status': { body: STATUS_ON },
    'POST /assistant/analyses/analysis-1': { body: ANSWER },
    ...routes,
  });
  renderWithProviders(<AssistantPanel analysisId="analysis-1" />, { authenticated: true });
  return mocked;
}

async function ask(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/Poser une question/), text);
  await user.click(screen.getByRole('button', { name: 'Envoyer' }));
}

describe('Assistant', () => {
  it("affiche la réponse du modèle", async () => {
    render();
    await screen.findByLabelText(/Poser une question/);

    await ask('Que signifie ce score ?');

    expect(
      await screen.findByText('La probabilité est une sortie de classifieur.'),
    ).toBeInTheDocument();
  });

  it("rappelle systématiquement l'avertissement médical", async () => {
    render();
    await screen.findByLabelText(/Poser une question/);

    await ask('Pourquoi ?');

    expect(await screen.findByText(/ne remplacent pas l'avis/)).toBeInTheDocument();
  });

  it("affiche l'avertissement de modèle de démonstration avec la réponse", async () => {
    render();
    await screen.findByLabelText(/Poser une question/);

    await ask('Pourquoi ?');

    expect(await screen.findByText(/AUCUNE VALEUR CLINIQUE/)).toBeInTheDocument();
  });

  it("permet de vérifier ce qui a été transmis au service", async () => {
    render();
    await screen.findByLabelText(/Poser une question/);

    await ask('Pourquoi ?');
    await screen.findByText(/sortie de classifieur/);

    expect(screen.getByText(/Contexte transmis au service/)).toBeInTheDocument();
    expect(screen.getByText(/Patiente : 52 ans/)).toBeInTheDocument();
  });

  it('rappelle la question posée au-dessus de la réponse', async () => {
    render();
    await screen.findByLabelText(/Poser une question/);

    await ask('Que signifie ce score ?');

    expect(await screen.findByText('Que signifie ce score ?')).toBeInTheDocument();
  });

  it('propose des amorces de question', async () => {
    render();

    expect(
      await screen.findByRole('button', { name: 'Pourquoi cette image est-elle suspecte ?' }),
    ).toBeInTheDocument();
  });

  it('transmet le fil de la conversation', async () => {
    // Le serveur ne stocke rien : c'est le client qui renvoie l'historique.
    const { calls } = render();
    await screen.findByLabelText(/Poser une question/);

    await ask('Première question');
    await screen.findByText(/sortie de classifieur/);
    await ask('Deuxième question');

    await waitFor(() => {
      const posts = calls.filter((call) => call.method === 'POST');
      expect(posts).toHaveLength(2);
      const history = (posts[1].body as { history: unknown[] }).history;
      expect(history).toHaveLength(2);
    });
  });

  it('affiche une erreur de quota sans casser la page', async () => {
    render({
      'POST /assistant/analyses/analysis-1': {
        status: 503,
        body: { detail: "Le quota du service d'assistance est épuisé." },
      },
    });
    await screen.findByLabelText(/Poser une question/);

    await ask('Pourquoi ?');

    expect(await screen.findByText(/quota du service/)).toBeInTheDocument();
    // Le formulaire reste utilisable.
    expect(screen.getByRole('button', { name: 'Envoyer' })).toBeInTheDocument();
  });

  it('se masque quand le serveur ne le propose pas', async () => {
    render({
      'GET /assistant/status': {
        body: {
          ...STATUS_ON,
          enabled: false,
          model: null,
          notice: "L'assistant n'est pas configuré sur ce serveur.",
        },
      },
    });

    expect(await screen.findByText(/n'est pas configuré sur ce serveur/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Poser une question/)).not.toBeInTheDocument();
  });

  it("n'envoie pas une question vide", async () => {
    const { calls } = render();
    await screen.findByLabelText(/Poser une question/);

    expect(screen.getByRole('button', { name: 'Envoyer' })).toBeDisabled();
    expect(calls.filter((call) => call.method === 'POST')).toHaveLength(0);
  });
});
