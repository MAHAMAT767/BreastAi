import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import PredictionBadge from '@/components/PredictionBadge';
import { Alert, Button, EmptyState, Select, Spinner, TextInput } from '@/components/ui';
import { formatDateTime } from '@/lib/format';
import { PAGE_SIZE, useAnalysisSearch } from '@/lib/analysisQueries';
import { useDebounce } from '@/lib/useDebounce';
import { STATUS_LABELS } from '@/types';
import type { AnalysisFilters } from '@/types';

const EMPTY: AnalysisFilters = {
  search: '',
  prediction: '',
  status: '',
  dateFrom: '',
  dateTo: '',
};

export default function AnalysesHistoryPage() {
  const [filters, setFilters] = useState<AnalysisFilters>(EMPTY);
  const [offset, setOffset] = useState(0);

  // Seule la saisie libre est débouncée : les listes déroulantes et les dates
  // changent d'un coup, les retarder ne ferait que rendre l'interface molle.
  const debouncedSearch = useDebounce(filters.search);
  const applied = { ...filters, search: debouncedSearch };

  useEffect(() => {
    setOffset(0);
  }, [debouncedSearch, filters.prediction, filters.status, filters.dateFrom, filters.dateTo]);

  const { data, isPending, isError, error, isFetching } = useAnalysisSearch(applied, offset);

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const hasFilters = Object.values(applied).some((value) => value !== '');
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  function update<K extends keyof AnalysisFilters>(key: K, value: AnalysisFilters[K]) {
    setFilters((previous) => ({ ...previous, [key]: value }));
  }

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Historique des analyses</h1>
          <p className="text-sm text-slate-600">
            {total} analyse{total > 1 ? 's' : ''}
            {hasFilters ? ' correspondant aux filtres' : ' enregistrée' + (total > 1 ? 's' : '')}
          </p>
        </div>
      </header>

      {/* Une seule rangée de filtres au-dessus du tableau : tout se recalcule
          contre la même sélection. */}
      <div className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="flex flex-col gap-1">
          <label htmlFor="search" className="text-xs font-medium text-slate-600">
            Patient
          </label>
          <TextInput
            id="search"
            type="search"
            placeholder="Code, prénom ou nom…"
            value={filters.search}
            onChange={(event) => update('search', event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="prediction" className="text-xs font-medium text-slate-600">
            Diagnostic
          </label>
          <Select
            id="prediction"
            value={filters.prediction}
            onChange={(event) =>
              update('prediction', event.target.value as AnalysisFilters['prediction'])
            }
          >
            <option value="">Tous</option>
            <option value="benign">Bénin</option>
            <option value="malignant">Malin</option>
          </Select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="status" className="text-xs font-medium text-slate-600">
            Statut
          </label>
          <Select
            id="status"
            value={filters.status}
            onChange={(event) =>
              update('status', event.target.value as AnalysisFilters['status'])
            }
          >
            <option value="">Tous</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="date_from" className="text-xs font-medium text-slate-600">
            Du
          </label>
          <TextInput
            id="date_from"
            type="date"
            value={filters.dateFrom}
            max={filters.dateTo || undefined}
            onChange={(event) => update('dateFrom', event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="date_to" className="text-xs font-medium text-slate-600">
            Au
          </label>
          <TextInput
            id="date_to"
            type="date"
            value={filters.dateTo}
            min={filters.dateFrom || undefined}
            onChange={(event) => update('dateTo', event.target.value)}
          />
        </div>

        {hasFilters && (
          <div className="lg:col-span-5">
            <Button variant="ghost" onClick={() => setFilters(EMPTY)}>
              Réinitialiser les filtres
            </Button>
          </div>
        )}
      </div>

      {isError && (
        <Alert variant="error">
          {error instanceof Error ? error.message : 'Chargement impossible.'}
        </Alert>
      )}

      {isPending && <Spinner label="Chargement de l'historique…" />}

      {!isPending && !isError && items.length === 0 && (
        <EmptyState
          title={hasFilters ? 'Aucune analyse ne correspond' : 'Aucune analyse enregistrée'}
          hint={
            hasFilters
              ? 'Élargissez la période ou retirez un filtre.'
              : 'Déposez une mammographie depuis un dossier patient.'
          }
        />
      )}

      {items.length > 0 && (
        <div
          className={`overflow-x-auto rounded-lg border border-slate-200 bg-white transition-opacity ${
            isFetching ? 'opacity-60' : ''
          }`}
        >
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Historique des analyses</caption>
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3 font-semibold">Date</th>
                <th scope="col" className="px-4 py-3 font-semibold">Fichier</th>
                <th scope="col" className="px-4 py-3 font-semibold">Statut</th>
                <th scope="col" className="px-4 py-3 font-semibold">Résultat</th>
                <th scope="col" className="px-4 py-3 font-semibold">Relue</th>
                <th scope="col" className="px-4 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((analysis) => (
                <tr key={analysis.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-600">
                    {formatDateTime(analysis.created_at)}
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    {analysis.original_filename}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {STATUS_LABELS[analysis.status]}
                  </td>
                  <td className="px-4 py-3">
                    <PredictionBadge
                      prediction={analysis.prediction}
                      probability={analysis.probability}
                    />
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {analysis.doctor_validated ? 'Oui' : 'Non'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/analyses/${analysis.id}`}
                      className="text-sm font-medium text-brand-700 underline"
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

      {total > PAGE_SIZE && (
        <nav aria-label="Pagination" className="flex items-center justify-between gap-4">
          <p className="text-sm text-slate-600">
            {offset + 1}–{pageEnd} sur {total}
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Précédent
            </Button>
            <Button
              variant="secondary"
              disabled={pageEnd >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Suivant
            </Button>
          </div>
        </nav>
      )}
    </section>
  );
}
