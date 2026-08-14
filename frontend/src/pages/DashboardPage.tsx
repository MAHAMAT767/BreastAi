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

      <section aria-label="Indicateurs" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
        />
        <StatTile
          label="Résultats malins"
          value={formatNumber(data.malignant_count)}
          hint="Sortie du modèle, non validée cliniquement"
        />
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <StatTile
          label="Temps moyen d'analyse"
          value={formatDuration(data.average_inference_time_ms)}
          hint="Inférence seule, hors dépôt et prétraitement"
        />
        <StatTile
          label="Analyses relues par un médecin"
          value={formatRate(data.doctor_validation_rate)}
          hint={`${formatNumber(data.doctor_validated_count)} sur ${formatNumber(
            data.completed_analyses,
          )} analyses terminées`}
        />
      </section>

      {/* Là où la spécification demandait « précision du modèle ». Afficher un
          taux sous ce nom laisserait croire que la justesse a été mesurée. */}
      <Alert variant="info">
        <p className="font-semibold">Pourquoi aucun taux d'exactitude n'est affiché</p>
        <p className="mt-1">{data.accuracy_note}</p>
      </Alert>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <MonthlyAnalysesChart data={data.monthly} />
        </section>

        <section className="space-y-6 rounded-lg border border-slate-200 bg-white p-5">
          <PredictionSplit benign={data.benign_count} malignant={data.malignant_count} />

          {data.model_versions.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-800">Modèles utilisés</h3>
              <ul className="mt-2 space-y-1 text-sm text-slate-700">
                {data.model_versions.map((version) => (
                  <li key={version} className="font-mono text-xs">
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
