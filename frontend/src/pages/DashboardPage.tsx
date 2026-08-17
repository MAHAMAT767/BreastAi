import ModelProvenanceWarning from '@/components/ModelProvenanceWarning';
import {
  MonthlyAnalysesChart,
  PredictionSplit,
  StatTile,
  formatNumber,
} from '@/components/charts';
import { Alert, Spinner } from '@/components/ui';
import { useDashboardStats } from '@/lib/analysisQueries';

function formatDuration(milliseconds: number | null): string {
  if (milliseconds == null) return '—';
  return milliseconds >= 1000
    ? `${(milliseconds / 1000).toFixed(1)} s`
    : `${Math.round(milliseconds)} ms`;
}

function formatRate(rate: number | null): string {
  return rate == null ? '—' : `${(rate * 100).toFixed(0)} %`;
}

export default function DashboardPage() {
  const { data, isPending, isError, error, isFetching } = useDashboardStats();

  if (isPending) return <Spinner label="Chargement du tableau de bord…" />;

  if (isError || !data) {
    return (
      <Alert variant="error">
        {error instanceof Error ? error.message : 'Chargement impossible.'}
      </Alert>
    );
  }

  return (
    // Pendant un rafraîchissement, le rendu précédent reste affiché en retrait
    // plutôt que de laisser place à un squelette : pas de saut de mise en page.
    <div
      className={`space-y-6 transition-opacity ${isFetching ? 'opacity-60' : 'opacity-100'}`}
    >
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Tableau de bord</h1>
        <p className="mt-1 text-sm text-slate-600">
          Chiffres agrégés — aucune donnée nominative.
        </p>
      </header>

      {data.model_warning && (
        <ModelProvenanceWarning status={data.model_status} message={data.model_warning} />
      )}

      {/* Les quatre chiffres qui portent la page. Bénin et malin sont teintés
          parce que ce sont des résultats ; patients et analyses restent neutres
          parce que ce sont des volumes. */}
      <section aria-label="Indicateurs" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Patients suivis" value={formatNumber(data.total_patients)} />
        <StatTile
          label="Analyses déposées"
          value={formatNumber(data.total_analyses)}
          hint={
            data.pending_analyses || data.failed_analyses
              ? `${data.pending_analyses} en attente · ${data.failed_analyses} en échec`
              : undefined
          }
        />
        <StatTile
          label="Résultats bénins"
          value={formatNumber(data.benign_count)}
          hint="Sortie du modèle, non validée cliniquement"
          tone="benign"
        />
        <StatTile
          label="Résultats malins"
          value={formatNumber(data.malignant_count)}
          hint="Sortie du modèle, non validée cliniquement"
          tone="malignant"
        />
      </section>

      {/* Second rang : deux mesures de fonctionnement, pas des résultats. Elles
          descendent d'un cran typographique pour ne pas concurrencer les quatre
          chiffres ci-dessus. */}
      <section className="grid gap-x-8 gap-y-3 rounded-lg border border-slate-200 bg-white px-4 py-3 sm:grid-cols-2">
        <div className="flex items-baseline justify-between gap-4">
          <span className="text-sm text-slate-600">Temps moyen d'analyse</span>
          <span className="text-sm font-semibold tabular-nums text-slate-900">
            {formatDuration(data.average_inference_time_ms)}
          </span>
        </div>
        <div className="flex items-baseline justify-between gap-4">
          <span className="text-sm text-slate-600">Analyses relues par un médecin</span>
          <span className="text-sm font-semibold tabular-nums text-slate-900">
            {formatRate(data.doctor_validation_rate)}
          </span>
        </div>
        <p className="text-xs text-slate-500">Inférence seule, hors dépôt et prétraitement</p>
        <p className="text-xs text-slate-500">
          {formatNumber(data.doctor_validated_count)} sur{' '}
          {formatNumber(data.completed_analyses)} analyses terminées
        </p>
      </section>

      {/* Là où la spécification demandait « précision du modèle ». Afficher un
          taux sous ce nom laisserait croire que la justesse a été mesurée.
          Replié : l'explication doit rester accessible sans occuper en
          permanence la place d'un chiffre clé. */}
      <details className="rounded-lg border border-slate-200 bg-white text-sm">
        <summary className="cursor-pointer px-4 py-3 font-medium text-slate-700">
          Pourquoi aucun taux d'exactitude n'est affiché
        </summary>
        <p className="border-t border-slate-100 px-4 py-3 leading-relaxed text-slate-600">
          {data.accuracy_note}
        </p>
      </details>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <MonthlyAnalysesChart data={data.monthly} />
        </section>

        <section className="space-y-6 rounded-lg border border-slate-200 bg-white p-5">
          <PredictionSplit benign={data.benign_count} malignant={data.malignant_count} />

          {data.model_versions.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-800">Modèles utilisés</h3>
              {/* Lignes fines séparées par un filet, comme les listes des autres
                  pages : une version de modèle est une entrée de liste, pas une
                  carte. */}
              <ul className="mt-2 divide-y divide-slate-100 border-y border-slate-100">
                {data.model_versions.map((version) => (
                  <li key={version} className="py-1.5 font-mono text-xs text-slate-700">
                    {version}
                  </li>
                ))}
              </ul>
              {data.model_versions.length > 1 && (
                <p className="mt-2 text-xs text-slate-500">
                  Plusieurs versions coexistent : les analyses anciennes n'ont pas
                  été produites par le modèle courant.
                </p>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
