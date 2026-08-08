import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { Alert, Button, EmptyState, Spinner, TextInput, buttonClasses } from '@/components/ui';
import { formatBirthDate, formatDate } from '@/lib/format';
import { PAGE_SIZE, usePatientList } from '@/lib/patientQueries';
import { useDebounce } from '@/lib/useDebounce';
import { SEX_LABELS } from '@/types';

export default function PatientsPage() {
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const debouncedSearch = useDebounce(search);

  // Revenir à la première page dès que la recherche change : rester à
  // l'offset 60 sur un résultat qui n'a que 3 lignes afficherait une page vide.
  useEffect(() => {
    setOffset(0);
  }, [debouncedSearch]);

  const { data, isPending, isError, error, isFetching } = usePatientList(
    debouncedSearch,
    offset,
  );

  const total = data?.total ?? 0;
  const patients = data?.items ?? [];
  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Patients</h1>
          <p className="text-sm text-slate-600">
            {total} dossier{total > 1 ? 's' : ''} enregistré{total > 1 ? 's' : ''}
          </p>
        </div>
        <Link to="/patients/nouveau" className={buttonClasses('primary')}>
          Nouveau dossier
        </Link>
      </header>

      <div className="flex items-center gap-3">
        <div className="w-full max-w-sm">
          <label htmlFor="search" className="sr-only">
            Rechercher un patient
          </label>
          <TextInput
            id="search"
            type="search"
            placeholder="Code, prénom ou nom…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        {isFetching && !isPending && (
          <span className="text-xs text-slate-500" role="status">
            Recherche…
          </span>
        )}
      </div>

      {isError && (
        <Alert variant="error">
          {error instanceof Error ? error.message : 'Chargement impossible.'}
        </Alert>
      )}

      {isPending && <Spinner label="Chargement des dossiers…" />}

      {!isPending && !isError && patients.length === 0 && (
        <EmptyState
          title={
            debouncedSearch ? 'Aucun dossier ne correspond' : 'Aucun dossier enregistré'
          }
          hint={
            debouncedSearch
              ? 'Vérifiez le code, le prénom ou le nom saisi.'
              : 'Créez un premier dossier pour commencer.'
          }
        />
      )}

      {patients.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Liste des dossiers patients</caption>
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Code
                </th>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Nom
                </th>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Naissance
                </th>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Sexe
                </th>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Créé le
                </th>
                <th scope="col" className="px-4 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {patients.map((patient) => (
                <tr key={patient.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-700">
                    {patient.code}
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    {patient.full_name}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {formatBirthDate(patient.birth_date)}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{SEX_LABELS[patient.sex]}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {formatDate(patient.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/patients/${patient.id}`}
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
            {pageStart}–{pageEnd} sur {total}
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
