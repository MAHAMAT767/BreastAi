import { PREDICTION_LABELS } from '@/types';
import type { Prediction } from '@/types';

/**
 * Pastille de résultat.
 *
 * La pastille de couleur est décorative (`aria-hidden`) : le libellé porte
 * l'information. Un lecteur d'écran, une impression en noir et blanc ou un
 * lecteur daltonien lisent la même chose que tout le monde.
 */
export default function PredictionBadge({
  prediction,
  probability,
}: {
  prediction: Prediction | null;
  probability?: number | null;
}) {
  if (!prediction) {
    return <span className="text-sm text-slate-500">Aucun résultat</span>;
  }

  const color = prediction === 'malignant' ? 'var(--color-malignant)' : 'var(--color-benign)';

  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-800">
      <span
        aria-hidden="true"
        className="size-2.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {PREDICTION_LABELS[prediction]}
      {probability != null && (
        <span className="text-slate-600">· {(probability * 100).toFixed(1)} %</span>
      )}
    </span>
  );
}
