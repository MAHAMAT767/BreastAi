import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import AnalysesList from '@/components/AnalysesList';
import UploadMammography from '@/components/UploadMammography';
import { Alert, Button, Spinner, buttonClasses } from '@/components/ui';
import { PLACEHOLDER, formatBirthDate, formatDateTime } from '@/lib/format';
import { useDeletePatient, usePatient } from '@/lib/patientQueries';
import { SEX_LABELS } from '@/types';
import type { Patient } from '@/types';

function DefinitionRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-1 gap-1 border-b border-slate-100 py-3 sm:grid-cols-3">
      <dt className="text-sm font-medium text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-900 sm:col-span-2">{value}</dd>
    </div>
  );
}

function MedicalHistory({ patient }: { patient: Patient }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
        Historique médical
      </h2>
      {patient.medical_history ? (
        // `whitespace-pre-line` conserve les retours à la ligne saisis par le
        // médecin : un historique reformaté en un seul bloc devient illisible.
        <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-800">
          {patient.medical_history}
        </p>
      ) : (
        <p className="mt-3 text-sm italic text-slate-500">Aucun antécédent renseigné.</p>
      )}

      {patient.notes && (
        <>
          <h3 className="mt-5 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Notes
          </h3>
          <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-800">
            {patient.notes}
          </p>
        </>
      )}
    </section>
  );
}

export default function PatientDetailPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const navigate = useNavigate();
  const { data: patient, isPending, isError, error } = usePatient(patientId);
  const deletePatient = useDeletePatient();

  const [confirmingDelete, setConfirmingDelete] = useState(false);

  function handleDelete() {
    if (!patientId) return;
    // `mutate` et non `mutateAsync` : l'échec est déjà affiché sous le bouton,
    // et un rejet sans `catch` remonterait en rejet non géré.
    deletePatient.mutate(patientId, {
      onSuccess: () => navigate('/patients', { replace: true }),
    });
  }

  if (isPending) return <Spinner label="Chargement du dossier…" />;

  if (isError || !patient) {
    return (
      <div className="space-y-4">
        <Alert variant="error">
          {error instanceof Error ? error.message : 'Dossier introuvable.'}
        </Alert>
        <Link to="/patients" className="text-sm text-brand-700 underline">
          Retour à la liste
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <nav aria-label="Fil d'Ariane" className="text-sm text-slate-500">
        <Link to="/patients" className="underline">
          Patients
        </Link>
        <span aria-hidden="true"> / </span>
        <span className="text-slate-700">{patient.full_name}</span>
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{patient.full_name}</h1>
          <p className="font-mono text-sm text-slate-500">{patient.code}</p>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/patients/${patient.id}/modifier`}
            className={buttonClasses('secondary')}
          >
            Modifier
          </Link>
          <Button variant="danger" onClick={() => setConfirmingDelete(true)}>
            Supprimer
          </Button>
        </div>
      </header>

      {confirmingDelete && (
        <Alert variant="warning">
          <p className="font-semibold">Supprimer ce dossier ?</p>
          <p className="mt-1">
            Le dossier n'apparaîtra plus dans les listes. Les analyses déjà rendues
            restent conservées : la suppression est logique, aucune donnée n'est
            effacée de la base.
          </p>
          <div className="mt-3 flex gap-2">
            <Button
              variant="danger"
              loading={deletePatient.isPending}
              onClick={handleDelete}
            >
              Confirmer la suppression
            </Button>
            <Button variant="secondary" onClick={() => setConfirmingDelete(false)}>
              Annuler
            </Button>
          </div>
          {deletePatient.isError && (
            <p className="mt-2 text-sm text-red-800">
              {deletePatient.error instanceof Error
                ? deletePatient.error.message
                : 'Suppression impossible.'}
            </p>
          )}
        </Alert>
      )}

      <section className="rounded-lg border border-slate-200 bg-white px-5 py-2">
        <h2 className="sr-only">Informations administratives</h2>
        <dl>
          <DefinitionRow label="Code dossier" value={patient.code} />
          <DefinitionRow label="Nom complet" value={patient.full_name} />
          <DefinitionRow
            label="Date de naissance"
            value={formatBirthDate(patient.birth_date)}
          />
          <DefinitionRow label="Sexe" value={SEX_LABELS[patient.sex]} />
          <DefinitionRow label="Téléphone" value={patient.phone ?? PLACEHOLDER} />
          <DefinitionRow label="Adresse e-mail" value={patient.email ?? PLACEHOLDER} />
          <DefinitionRow label="Adresse" value={patient.address ?? PLACEHOLDER} />
          <DefinitionRow label="Créé le" value={formatDateTime(patient.created_at)} />
          <DefinitionRow
            label="Dernière modification"
            value={formatDateTime(patient.updated_at)}
          />
        </dl>
      </section>

      <MedicalHistory patient={patient} />

      <UploadMammography patientId={patient.id} />
      <AnalysesList patientId={patient.id} />
    </div>
  );
}
