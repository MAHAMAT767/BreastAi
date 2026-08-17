import { PREDICTION_LABELS } from '@/types';
import type { Prediction } from '@/types';

/**
 * Pastille de résultat.
 *
 * La teinte du fond porte le résultat — bleu pour bénin, orange pour malin —
 * et reste la même partout où un résultat apparaît : historique, dossier,
 * activité récente. C'est le seul endroit de l'interface où ces deux teintes
 * sont employées comme aplat de fond ; les voir ailleurs voudrait dire qu'elles
 * ne signifient plus rien.
 *
 * La couleur ne porte jamais l'information seule : le libellé « Bénin » ou
 * « Malin » est toujours écrit. Une impression en noir et blanc, un lecteur
 * d'écran ou un lecteur daltonien lisent la même chose que tout le monde.
 */
const TONES: Record<Prediction, string> = {
  benign: 'bg-[var(--color-benign-soft)] text-[var(--color-benign-strong)]',
  malignant: 'bg-[var(--color-malignant-soft)] text-[var(--color-malignant-strong)]',
};

export default function PredictionBadge({
  prediction,
  probability,
}: {
  prediction: Prediction | null;
  probability?: number | null;
}) {
  if (!prediction) {
    return <span className="text-sm text-slate-400">—</span>;
  }

  return (
    <span
      className={`inline-flex items-baseline gap-1.5 rounded px-2 py-0.5 text-sm font-medium ${TONES[prediction]}`}
    >
      {PREDICTION_LABELS[prediction]}
      {probability != null && (
        // `tabular-nums` : les pourcentages s'empilent en colonne dans les
        // listes, des chiffres de largeurs différentes les feraient danser.
        <span className="text-xs tabular-nums opacity-80">
          {(probability * 100).toFixed(1)} %
        </span>
      )}
    </span>
  );
}
