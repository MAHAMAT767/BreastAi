import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

import PredictionBadge from '@/components/PredictionBadge';
import { buttonClasses } from '@/components/ui';
import { useAuth } from '@/contexts/AuthContext';
import { getHealth } from '@/lib/api';
import { useAnalysisSearch } from '@/lib/analysisQueries';
import { formatRelativeTime } from '@/lib/format';
import { CLINICAL_ROLES } from '@/types';
import type { AnalysisFilters } from '@/types';

/**
 * Étapes du pipeline, dans l'ordre où une mammographie les traverse.
 *
 * L'assistant conversationnel n'y figure pas : il ne s'insère pas dans cette
 * chaîne, il commente son résultat une fois qu'elle est terminée. Le montrer
 * grisé en bout de file le faisait passer pour une étape en panne.
 */
const PIPELINE = [
  'Upload',
  'Prétraitement',
  'EfficientNet',
  'Grad-CAM',
  'Rapport PDF',
] as const;

/** Aucun filtre : la même clé de cache que l'historique à son premier écran. */
const NO_FILTERS: AnalysisFilters = {
  search: '',
  prediction: '',
  status: '',
  dateFrom: '',
  dateTo: '',
};

const RECENT_COUNT = 5;

function ApiStatus() {
  const { data, isPending, isError } = useQuery({ queryKey: ['health'], queryFn: getHealth });

  // Couleurs d'état, et non couleurs de séries : `--color-benign` et
  // `--color-malignant` désignent des classes de résultat, pas la santé d'un
  // service. Les réutiliser ici brouillerait leur signification.
  if (isPending) return <span className="text-slate-500">Connexion à l'API…</span>;
  if (isError) {
    return (
      <span className="text-red-700">
        API injoignable — vérifiez que le backend est démarré.
      </span>
    );
  }

  return (
    <span className="text-emerald-700">
      API connectée — {data.app_name} v{data.version} ({data.environment})
    </span>
  );
}

/**
 * Dernières analyses déposées.
 *
 * Réservé aux rôles cliniques : l'API refuserait la liste à un chercheur, et
 * lui montrer un bloc en erreur ne lui apprendrait rien.
 */
function RecentActivity() {
  const { data, isPending, isError } = useAnalysisSearch(NO_FILTERS, 0);
  const recent = (data?.items ?? []).slice(0, RECENT_COUNT);

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-baseline justify-between gap-4 border-b border-slate-100 px-4 py-2.5">
        <h2 className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Activité récente
        </h2>
        <Link to="/analyses" className="text-xs font-medium text-brand-700 hover:underline">
          Tout l'historique
        </Link>
      </div>

      {isPending && <p className="px-4 py-6 text-sm text-slate-500">Chargement…</p>}

      {isError && (
        <p className="px-4 py-6 text-sm text-slate-500">
          Activité indisponible pour le moment.
        </p>
      )}

      {!isPending && !isError && recent.length === 0 && (
        <p className="px-4 py-6 text-sm text-slate-500">
          Aucune analyse déposée pour l'instant.
        </p>
      )}

      {recent.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {recent.map((analysis) => (
            <li key={analysis.id}>
              <Link
                to={`/analyses/${analysis.id}`}
                aria-label={`Analyse ${analysis.original_filename}`}
                className="flex items-center gap-3 px-4 py-2 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500/40"
              >
                <span className="min-w-0 flex-1 truncate text-sm text-slate-800">
                  {analysis.original_filename}
                </span>
                <PredictionBadge prediction={analysis.prediction} />
                <span className="hidden shrink-0 text-xs text-slate-400 sm:block">
                  {formatRelativeTime(analysis.created_at)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function HomePage() {
  const { user, hasRole } = useAuth();
  const isClinical = hasRole(...CLINICAL_ROLES);

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">
          Bonjour {user?.full_name ?? ''}
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Plateforme d'aide au dépistage du cancer du sein.
        </p>
      </header>

      <div className="flex flex-wrap gap-3">
        {isClinical && (
          <>
            <Link to="/patients" className={buttonClasses('primary')}>
              Consulter les patients
            </Link>
            <Link to="/patients/nouveau" className={buttonClasses('secondary')}>
              Créer un dossier
            </Link>
          </>
        )}
        <Link to="/tableau-de-bord" className={buttonClasses('secondary')}>
          Tableau de bord
        </Link>
      </div>

      {isClinical && <RecentActivity />}

      {/* Deux encarts de référence, volontairement plus discrets que l'activité
          ci-dessus : on les consulte une fois, on ne les surveille pas. */}
      <div className="grid gap-3 sm:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <h2 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            État du système
          </h2>
          <p className="mt-1.5 text-sm">
            <ApiStatus />
          </p>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <h2 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Pipeline d'analyse
          </h2>
          <ol className="mt-1.5 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-slate-600">
            {PIPELINE.map((step, index) => (
              <li key={step} className="flex items-center gap-1.5">
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-700">
                  {step}
                </span>
                {index < PIPELINE.length - 1 && (
                  <span aria-hidden="true" className="text-slate-300">
                    →
                  </span>
                )}
              </li>
            ))}
          </ol>
          {/* Hors de la chaîne, et rattaché à elle par une phrase plutôt que
              par une flèche : c'est un service adjacent, pas une sixième
              étape. */}
          <p className="mt-2 border-t border-slate-100 pt-2 text-xs text-slate-500">
            Un assistant conversationnel commente le résultat depuis chaque analyse.
          </p>
        </section>
      </div>
    </section>
  );
}
