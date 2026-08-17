import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { Alert, Button, EmptyState, Spinner, TextInput, buttonClasses } from '@/components/ui';
import { formatBirthDate, formatDate, initials } from '@/lib/format';
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
        // Liste et non tableau : une entrée de dossier n'est pas une grille de
        // cellules indépendantes mais un bloc d'identité — initiales, nom,
        // caractéristiques — qu'on lit d'un seul tenant. L'historique des
        // analyses, lui, reste un vrai tableau : ses colonnes se comparent.
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
          {patients.map((patient) => (
            <li key={patient.id}>
              {/* Toute la ligne est cliquable : viser un lien « Ouvrir » de
                  quarante pixels dans une liste dense est une cible inutilement
                  petite. */}
              <Link
                to={`/patients/${patient.id}`}
                // Sans libellé explicite, le nom du lien serait la
                // concaténation de tout ce que contient la ligne, ponctuation
                // comprise. Il reste construit sur le nom affiché.
                aria-label={`Dossier de ${patient.full_name}`}
                className="flex items-center gap-3 px-4 py-2.5 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500/40"
              >
                {/* Teinte de marque, pas une teinte de résultat : ces deux-là
                    sont réservées au bénin et au malin. Décoratif — le nom
                    juste à côté porte l'information. */}
                <span
                  aria-hidden="true"
                  className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700"
                >
                  {initials(patient.first_name, patient.last_name)}
                </span>

                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-slate-900">
                    {patient.full_name}
                  </span>
                  <span className="block truncate text-xs text-slate-500">
                    {formatBirthDate(patient.birth_date)} · {SEX_LABELS[patient.sex]}
                  </span>
                </span>

                <span className="hidden shrink-0 font-mono text-xs text-slate-500 sm:block">
                  {patient.code}
                </span>

                <span className="hidden shrink-0 text-xs tabular-nums text-slate-400 sm:block">
                  {formatDate(patient.created_at)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
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
