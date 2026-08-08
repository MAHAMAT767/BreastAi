import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { Alert, Button, Field, TextInput } from '@/components/ui';
import { ApiError, confirmPasswordReset } from '@/lib/api';

/** Même minimum que côté serveur (`MIN_PASSWORD_LENGTH`). */
const MIN_PASSWORD_LENGTH = 12;

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setFieldError(null);

    // Contrôles côté client : ils évitent un aller-retour, mais le serveur
    // revalide de toute façon — ces vérifications ne sont pas une sécurité.
    if (password.length < MIN_PASSWORD_LENGTH) {
      setFieldError(`Le mot de passe doit contenir au moins ${MIN_PASSWORD_LENGTH} caractères.`);
      return;
    }
    if (password !== confirmation) {
      setFieldError('Les deux mots de passe ne correspondent pas.');
      return;
    }

    setSubmitting(true);
    try {
      await confirmPasswordReset(token, password);
      navigate('/connexion', {
        replace: true,
        state: { notice: 'Mot de passe réinitialisé. Vous pouvez vous connecter.' },
      });
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Réinitialisation impossible.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
          noValidate
        >
          <h1 className="text-lg font-semibold text-slate-800">
            Choisir un nouveau mot de passe
          </h1>

          {!token && (
            <Alert variant="error">
              Le lien de réinitialisation est incomplet : il ne contient aucun jeton.
              Refaites une demande depuis la page de connexion.
            </Alert>
          )}
          {error && <Alert variant="error">{error}</Alert>}

          <Field
            label="Nouveau mot de passe"
            htmlFor="password"
            required
            hint={`${MIN_PASSWORD_LENGTH} caractères minimum.`}
            error={fieldError ?? undefined}
          >
            <TextInput
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>

          <Field label="Confirmation" htmlFor="confirmation" required>
            <TextInput
              id="confirmation"
              name="confirmation"
              type="password"
              autoComplete="new-password"
              required
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </Field>

          <Button type="submit" loading={submitting} disabled={!token} className="w-full">
            Réinitialiser
          </Button>

          <p className="text-center text-sm">
            <Link to="/connexion" className="text-brand-700 underline">
              Retour à la connexion
            </Link>
          </p>
        </form>
      </main>
    </div>
  );
}
