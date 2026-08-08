import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

import { buttonClasses } from '@/components/ui';
import { useAuth } from '@/contexts/AuthContext';
import { getHealth } from '@/lib/api';
import { CLINICAL_ROLES } from '@/types';

/** Étapes du pipeline. Celles qui ne sont pas encore accessibles sont marquées. */
const PIPELINE = [
  { label: 'Upload', ready: true },
  { label: 'Prétraitement', ready: true },
  { label: 'EfficientNet', ready: true },
  { label: 'Grad-CAM', ready: true },
  { label: 'Rapport PDF', ready: true },
  { label: 'Assistant IA', ready: false },
] as const;

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

export default function HomePage() {
  const { user, hasRole } = useAuth();

  return (
    <section className="space-y-8">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">
          Bonjour {user?.full_name ?? ''}
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Plateforme d'aide au dépistage du cancer du sein.
        </p>
      </header>

      <div className="flex flex-wrap gap-3">
        {hasRole(...CLINICAL_ROLES) && (
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

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            État du système
          </h2>
          <p className="text-sm">
            <ApiStatus />
          </p>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Pipeline d'analyse
          </h2>
          <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-sm text-slate-700">
            {PIPELINE.map((step, index) => (
              <li key={step.label} className="flex items-center gap-2">
                <span
                  className={
                    step.ready
                      ? 'rounded bg-brand-50 px-2 py-1 font-medium text-brand-700'
                      : 'rounded bg-slate-100 px-2 py-1 font-medium text-slate-400'
                  }
                  title={step.ready ? undefined : 'À venir'}
                >
                  {step.label}
                </span>
                {index < PIPELINE.length - 1 && <span aria-hidden="true">→</span>}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </section>
  );
}
