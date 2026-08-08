import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Alert, Button, Field, Select, Spinner, TextArea, TextInput } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { emptyToNull } from '@/lib/format';
import { useCreatePatient, usePatient, useUpdatePatient } from '@/lib/patientQueries';
import { SEX_LABELS } from '@/types';
import type { PatientPayload, Sex } from '@/types';

interface FormState {
  code: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  sex: Sex;
  phone: string;
  email: string;
  address: string;
  medical_history: string;
  notes: string;
}

const EMPTY_FORM: FormState = {
  code: '',
  first_name: '',
  last_name: '',
  birth_date: '',
  sex: 'F',
  phone: '',
  email: '',
  address: '',
  medical_history: '',
  notes: '',
};

function toPayload(form: FormState): PatientPayload {
  return {
    code: form.code.trim(),
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    birth_date: emptyToNull(form.birth_date),
    sex: form.sex,
    phone: emptyToNull(form.phone),
    email: emptyToNull(form.email),
    address: emptyToNull(form.address),
    medical_history: emptyToNull(form.medical_history),
    notes: emptyToNull(form.notes),
  };
}

export default function PatientFormPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const isEditing = Boolean(patientId);
  const navigate = useNavigate();

  const { data: patient, isPending: loadingPatient } = usePatient(patientId);
  const createPatient = useCreatePatient();
  const updatePatient = useUpdatePatient(patientId ?? '');

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  // Le formulaire n'est renseigné qu'une fois le dossier chargé : initialiser
  // l'état avec des valeurs vides puis les remplacer évite un champ contrôlé
  // qui passerait de `undefined` à une valeur, ce que React refuse.
  useEffect(() => {
    if (!patient) return;
    setForm({
      code: patient.code,
      first_name: patient.first_name,
      last_name: patient.last_name,
      birth_date: patient.birth_date ?? '',
      sex: patient.sex,
      phone: patient.phone ?? '',
      email: patient.email ?? '',
      address: patient.address ?? '',
      medical_history: patient.medical_history ?? '',
      notes: patient.notes ?? '',
    });
  }, [patient]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    try {
      if (isEditing && patientId) {
        await updatePatient.mutateAsync(toPayload(form));
        navigate(`/patients/${patientId}`);
      } else {
        const created = await createPatient.mutateAsync(toPayload(form));
        navigate(`/patients/${created.id}`);
      }
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Enregistrement impossible.',
      );
    }
  }

  if (isEditing && loadingPatient) {
    return <Spinner label="Chargement du dossier…" />;
  }

  const submitting = createPatient.isPending || updatePatient.isPending;
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-6">
      <nav aria-label="Fil d'Ariane" className="text-sm text-slate-500">
        <Link to="/patients" className="underline">
          Patients
        </Link>
        <span aria-hidden="true"> / </span>
        <span className="text-slate-700">
          {isEditing ? 'Modifier le dossier' : 'Nouveau dossier'}
        </span>
      </nav>

      <h1 className="text-2xl font-bold text-slate-900">
        {isEditing ? 'Modifier le dossier' : 'Nouveau dossier patient'}
      </h1>

      <form onSubmit={handleSubmit} className="space-y-6" noValidate>
        {error && <Alert variant="error">{error}</Alert>}

        <fieldset className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
          <legend className="px-1 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Identité
          </legend>

          <Field
            label="Code dossier"
            htmlFor="code"
            required
            hint="Identifiant utilisé par la structure de soins, par exemple TCD-2026-0142."
          >
            <TextInput
              id="code"
              name="code"
              required
              maxLength={50}
              value={form.code}
              onChange={(event) => update('code', event.target.value)}
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Prénom" htmlFor="first_name" required>
              <TextInput
                id="first_name"
                name="first_name"
                required
                maxLength={100}
                value={form.first_name}
                onChange={(event) => update('first_name', event.target.value)}
              />
            </Field>

            <Field label="Nom" htmlFor="last_name" required>
              <TextInput
                id="last_name"
                name="last_name"
                required
                maxLength={100}
                value={form.last_name}
                onChange={(event) => update('last_name', event.target.value)}
              />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Date de naissance" htmlFor="birth_date">
              <TextInput
                id="birth_date"
                name="birth_date"
                type="date"
                // Le serveur refuse une date future ; l'attribut évite la
                // majorité des saisies erronées sans s'y substituer.
                max={today}
                value={form.birth_date}
                onChange={(event) => update('birth_date', event.target.value)}
              />
            </Field>

            <Field
              label="Sexe"
              htmlFor="sex"
              required
              hint="Le cancer du sein masculin est rare mais réel."
            >
              <Select
                id="sex"
                name="sex"
                value={form.sex}
                onChange={(event) => update('sex', event.target.value as Sex)}
              >
                {Object.entries(SEX_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </fieldset>

        <fieldset className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
          <legend className="px-1 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Contact
          </legend>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Téléphone" htmlFor="phone">
              <TextInput
                id="phone"
                name="phone"
                type="tel"
                maxLength={30}
                value={form.phone}
                onChange={(event) => update('phone', event.target.value)}
              />
            </Field>

            <Field label="Adresse e-mail" htmlFor="email">
              <TextInput
                id="email"
                name="email"
                type="email"
                value={form.email}
                onChange={(event) => update('email', event.target.value)}
              />
            </Field>
          </div>

          <Field label="Adresse" htmlFor="address">
            <TextInput
              id="address"
              name="address"
              maxLength={255}
              value={form.address}
              onChange={(event) => update('address', event.target.value)}
            />
          </Field>
        </fieldset>

        <fieldset className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
          <legend className="px-1 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Historique médical
          </legend>

          <Field
            label="Antécédents et facteurs de risque"
            htmlFor="medical_history"
            hint="Antécédents familiaux, traitements en cours, interventions antérieures."
          >
            <TextArea
              id="medical_history"
              name="medical_history"
              rows={6}
              value={form.medical_history}
              onChange={(event) => update('medical_history', event.target.value)}
            />
          </Field>

          <Field label="Notes" htmlFor="notes">
            <TextArea
              id="notes"
              name="notes"
              rows={3}
              value={form.notes}
              onChange={(event) => update('notes', event.target.value)}
            />
          </Field>
        </fieldset>

        <div className="flex gap-3">
          <Button type="submit" loading={submitting}>
            {isEditing ? 'Enregistrer les modifications' : 'Créer le dossier'}
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => navigate(isEditing ? `/patients/${patientId}` : '/patients')}
          >
            Annuler
          </Button>
        </div>
      </form>
    </div>
  );
}
