import { useState } from 'react';
import { Link } from 'react-router-dom';

import PredictionBadge from '@/components/PredictionBadge';
import { Alert, Button, EmptyState, Spinner } from '@/components/ui';
import { ANALYSES_PAGE_SIZE, useAnalyses } from '@/lib/analysisQueries';
import { formatDateTime } from '@/lib/format';
import { STATUS_LABELS } from '@/types';

export default function AnalysesList({ patientId }: { patientId: string }) {
  const [offset, setOffset] = useState(0);
  const { data, isPending, isError, error, isFetching } = useAnalyses(patientId, offset);

  const analyses = data?.items ?? [];
  const total = data?.total ?? 0;
  const pageEnd = Math.min(offset + ANALYSES_PAGE_SIZE, total);

  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Analyses ({total})
        </h2>
        {isFetching && !isPending && (
          <span className="text-xs text-slate-500" role="status">
            Actualisation…
          </span>
        )}
      </div>

      {isError && (
        <Alert variant="error">
          {error instanceof Error ? error.message : 'Chargement impossible.'}
        </Alert>
      )}

      {isPending && <Spinner label="Chargement des analyses…" />}

      {!isPending && !isError && analyses.length === 0 && (
        <EmptyState
          title="Aucune analyse pour ce dossier"
          hint="Déposez une mammographie pour lancer une première analyse."
        />
      )}

      {analyses.length > 0 && (
        // `overflow-x-auto` : sur mobile le tableau défile dans son cadre
        // plutôt que d'élargir la page entière.
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Analyses du dossier</caption>
            <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="py-2 pr-4 font-semibold">
                  Date
                </th>
                <th scope="col" className="py-2 pr-4 font-semibold">
                  Fichier
                </th>
                <th scope="col" className="py-2 pr-4 font-semibold">
                  Statut
                </th>
                <th scope="col" className="py-2 pr-4 font-semibold">
                  Résultat
                </th>
                <th scope="col" className="py-2">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {analyses.map((analysis) => (
                <tr key={analysis.id}>
                  <td className="py-3 pr-4 text-slate-600">
                    {formatDateTime(analysis.created_at)}
                  </td>
                  <td className="max-w-40 truncate py-3 pr-4 text-slate-800">
                    {analysis.original_filename}
                  </td>
                  <td className="py-3 pr-4 text-slate-600">
                    {STATUS_LABELS[analysis.status]}
                  </td>
                  <td className="py-3 pr-4">
                    <PredictionBadge
                      prediction={analysis.prediction}
                      probability={analysis.probability}
                    />
                  </td>
                  <td className="py-3 text-right">
                    <Link
                      to={`/analyses/${analysis.id}`}
                      className="font-medium text-brand-700 underline"
                    >
                      Ouvrir
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > ANALYSES_PAGE_SIZE && (
        <nav aria-label="Pagination des analyses" className="flex items-center justify-between">
          <p className="text-sm text-slate-600">
            {offset + 1}–{pageEnd} sur {total}
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - ANALYSES_PAGE_SIZE))}
            >
              Précédent
            </Button>
            <Button
              variant="secondary"
              disabled={pageEnd >= total}
              onClick={() => setOffset(offset + ANALYSES_PAGE_SIZE)}
            >
              Suivant
            </Button>
          </div>
        </nav>
      )}
    </section>
  );
}
