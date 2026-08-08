import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { Alert, Button, Field, TextInput } from '@/components/ui';
import { ApiError, requestPasswordReset } from '@/lib/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setSubmitting(true);

    try {
      const response = await requestPasswordReset(email);
      // Le serveur répond la même chose que l'adresse existe ou non : ne rien
      // ajouter à ce message, sous peine de révéler quels comptes existent.
      setMessage(response.message);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Demande impossible pour le moment.',
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
          <h1 className="text-lg font-semibold text-slate-800">Mot de passe oublié</h1>
          <p className="text-sm text-slate-600">
            Indiquez votre adresse e-mail. Si un compte y correspond, un lien de
            réinitialisation vous sera transmis.
          </p>

          {error && <Alert variant="error">{error}</Alert>}
          {message && <Alert variant="success">{message}</Alert>}

          <Field label="Adresse e-mail" htmlFor="email" required>
            <TextInput
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </Field>

          <Button type="submit" loading={submitting} className="w-full">
            Envoyer le lien
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
