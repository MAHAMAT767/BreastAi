import { useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';

import ModelProvenanceWarning from '@/components/ModelProvenanceWarning';
import { Alert, Button, TextArea } from '@/components/ui';
import { ApiError, askAssistant, fetchAssistantStatus } from '@/lib/api';
import type { AssistantAnswer, AssistantMessage } from '@/types';

/** Amorces proposées : elles montrent ce que l'assistant sait traiter. */
const SUGGESTIONS = [
  'Pourquoi cette image est-elle suspecte ?',
  'Que signifie ce score de confiance ?',
  'La zone colorée du Grad-CAM correspond-elle à une lésion ?',
] as const;

interface Turn {
  question: string;
  answer: AssistantAnswer | null;
  error: string | null;
}

/**
 * Teinte de section, sur le principe de `ModelProvenanceWarning` : un fond
 * coloré signale un registre différent de celui des cartes neutres voisines
 * (imagerie, lecture médicale), sans monter le volume pour autant.
 *
 * La teinte reste très diluée et le titre garde l'échelle typographique de ses
 * voisins : ce qui distingue la section est la couleur, pas la taille. Un bloc
 * qui crierait plus fort que le bandeau de provenance du modèle déplacerait
 * l'attention au mauvais endroit — l'assistant est un confort de lecture, pas
 * un avertissement.
 */
const SECTION_CLASSES = 'rounded-lg border border-brand-100 bg-brand-50/60 p-5';

/** En-tête de la section, identique que l'assistant soit disponible ou non. */
function AssistantHeading({ notice }: { notice: string }) {
  return (
    <div className="flex items-start gap-3">
      <span
        // Décoratif : le titre « Assistant » juste à côté porte déjà le sens.
        aria-hidden="true"
        className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white"
      >
        {/* SVG en ligne plutôt qu'une librairie d'icônes : le projet n'en a
            aucune, et une dépendance pour un seul pictogramme se paierait à
            chaque installation. */}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="size-5"
        >
          <path d="M21 11.5a8.5 8.5 0 0 1-9.1 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.1a8.4 8.4 0 0 1-.9-3.8A8.5 8.5 0 0 1 12.5 3a8.5 8.5 0 0 1 8.5 8.5Z" />
        </svg>
      </span>
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-brand-700">
          Assistant
        </h2>
        <p className="mt-1 text-sm text-slate-600">{notice}</p>
      </div>
    </div>
  );
}

function AnswerBlock({ answer }: { answer: AssistantAnswer }) {
  return (
    <div className="space-y-3">
      {/* Les avertissements sont affichés séparément grâce à `answer_body`,
          plutôt que noyés dans le bloc de texte. Ils restent présents dans
          `answer` si la réponse est copiée ailleurs. */}
      {answer.model_warning && (
        <ModelProvenanceWarning status={answer.model_status} message={answer.model_warning} />
      )}

      <p className="whitespace-pre-line text-sm leading-relaxed text-slate-800">
        {answer.answer_body}
      </p>

      <Alert variant="warning">{answer.disclaimer}</Alert>

      <details className="text-xs text-slate-500">
        <summary className="cursor-pointer">
          Contexte transmis au service ({answer.model})
        </summary>
        <p className="mt-2 whitespace-pre-line rounded bg-white p-3 font-mono text-[11px] leading-relaxed">
          {answer.context_sent}
        </p>
      </details>
    </div>
  );
}

export default function AssistantPanel({ analysisId }: { analysisId: string }) {
  const status = useQuery({ queryKey: ['assistant', 'status'], queryFn: fetchAssistantStatus });

  const [question, setQuestion] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);

  // L'historique n'est conservé que dans ce composant : le serveur ne stocke
  // aucune conversation, et fermer la page l'efface.
  const history: AssistantMessage[] = turns.flatMap((turn) =>
    turn.answer
      ? [
          { role: 'user' as const, content: turn.question },
          { role: 'assistant' as const, content: turn.answer.answer_body },
        ]
      : [],
  );

  const ask = useMutation({
    mutationFn: (asked: string) => askAssistant(analysisId, asked, history),
  });

  function submit(asked: string) {
    const cleaned = asked.trim();
    if (!cleaned || ask.isPending) return;

    setQuestion('');
    ask.mutate(cleaned, {
      onSuccess: (answer) =>
        setTurns((previous) => [...previous, { question: cleaned, answer, error: null }]),
      onError: (error) =>
        setTurns((previous) => [
          ...previous,
          {
            question: cleaned,
            answer: null,
            error:
              error instanceof ApiError ? error.message : "L'assistant est indisponible.",
          },
        ]),
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit(question);
  }

  if (status.isPending) return null;

  if (!status.data?.enabled) {
    return (
      <section className={SECTION_CLASSES}>
        <AssistantHeading
          notice={status.data?.notice ?? "L'assistant n'est pas disponible."}
        />
      </section>
    );
  }

  return (
    <section className={`space-y-4 ${SECTION_CLASSES}`}>
      <AssistantHeading notice={status.data.notice} />

      {turns.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => submit(suggestion)}
              disabled={ask.isPending}
              // Fond blanc et bordure brand : sur la teinte rosée, un gris sur
              // gris deviendrait terne et les puces se fondraient dans le fond.
              className="rounded-full border border-brand-300 bg-white px-3 py-1.5 text-xs text-brand-700 transition hover:bg-brand-50 disabled:opacity-60"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <ol className="space-y-5">
        {turns.map((turn, index) => (
          <li key={`${index}-${turn.question}`} className="space-y-3">
            <p className="rounded-md border border-brand-100 bg-white px-3 py-2 text-sm font-medium text-slate-800">
              {turn.question}
            </p>
            {turn.answer && <AnswerBlock answer={turn.answer} />}
            {turn.error && <Alert variant="error">{turn.error}</Alert>}
          </li>
        ))}
      </ol>

      {ask.isPending && (
        <p className="text-sm text-slate-500" role="status">
          L'assistant rédige sa réponse…
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-2">
        <label htmlFor="assistant-question" className="text-sm font-medium text-slate-700">
          Poser une question sur cette analyse
        </label>
        <TextArea
          id="assistant-question"
          rows={3}
          maxLength={1000}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Par exemple : que signifie la probabilité affichée ?"
        />
        <Button type="submit" loading={ask.isPending} disabled={!question.trim()}>
          Envoyer
        </Button>
      </form>
    </section>
  );
}
