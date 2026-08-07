import { useQuery } from '@tanstack/react-query';

import MedicalDisclaimer from '@/components/MedicalDisclaimer';
import { getHealth } from '@/lib/api';

/** Étapes du pipeline, affichées telles quelles jusqu'à leur implémentation. */
const PIPELINE = [
  'Upload',
  'Prétraitement',
  'EfficientNet',
  'Classification',
  'Grad-CAM',
  'Rapport PDF',
];

function ApiStatus() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
  });

  if (isPending) {
    return <span className="text-slate-500">Connexion à l'API…</span>;
  }

  if (isError) {
    return (
      <span className="text-malignant">
        API injoignable — vérifiez que le backend tourne sur le port 8000.
      </span>
    );
  }

  return (
    <span className="text-benign">
      API connectée — {data.app_name} v{data.version} ({data.environment})
    </span>
  );
}

export default function HomePage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="mb-10">
        <h1 className="text-4xl font-bold tracking-tight text-brand-700">BreastAI</h1>
        <p className="mt-2 text-lg text-slate-600">
          Aide au dépistage du cancer du sein par intelligence artificielle.
        </p>
      </header>

      <section className="mb-8 rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          État du système
        </h2>
        <p className="text-sm">
          <ApiStatus />
        </p>
      </section>

      <section className="mb-8 rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Pipeline d'analyse
        </h2>
        <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-sm text-slate-700">
          {PIPELINE.map((step, index) => (
            <li key={step} className="flex items-center gap-2">
              <span className="rounded bg-brand-50 px-2 py-1 font-medium text-brand-700">
                {step}
              </span>
              {index < PIPELINE.length - 1 && <span aria-hidden="true">→</span>}
            </li>
          ))}
        </ol>
      </section>

      <MedicalDisclaimer />

      <footer className="mt-12 border-t border-slate-200 pt-6 text-sm text-slate-500">
        <p>
          Dédié à la mémoire de <strong className="text-slate-700">Mouna Abakar</strong>.
        </p>
      </footer>
    </main>
  );
}
