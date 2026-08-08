import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';

import MedicalDisclaimer from '@/components/MedicalDisclaimer';
import { Alert, Button, Field, TextInput } from '@/components/ui';
import { useAuth } from '@/contexts/AuthContext';
import { ApiError } from '@/lib/api';

interface LocationState {
  from?: string;
}

export default function LoginPage() {
  const { signIn, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!isLoading && isAuthenticated) {
    const target = (location.state as LocationState | null)?.from ?? '/';
    return <Navigate to={target} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await signIn(email, password);
      navigate((location.state as LocationState | null)?.from ?? '/', { replace: true });
    } catch (caught) {
      // Le backend renvoie volontairement le même message pour une adresse
      // inconnue et un mot de passe faux : on le relaie tel quel plutôt que de
      // le reformuler, sous peine de réintroduire l'énumération de comptes.
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Connexion impossible. Vérifiez que l'API est accessible.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <header className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-brand-700">BreastAI</h1>
          <p className="mt-1 text-sm text-slate-600">
            Aide au dépistage du cancer du sein
          </p>
        </header>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
          noValidate
        >
          <h2 className="text-lg font-semibold text-slate-800">Connexion</h2>

          {error && <Alert variant="error">{error}</Alert>}

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

          <Field label="Mot de passe" htmlFor="password" required>
            <TextInput
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>

          <Button type="submit" loading={submitting} className="w-full">
            Se connecter
          </Button>

          <p className="text-center text-sm">
            <Link to="/mot-de-passe-oublie" className="text-brand-700 underline">
              Mot de passe oublié ?
            </Link>
          </p>
        </form>

        <div className="mt-6">
          <MedicalDisclaimer />
        </div>
      </main>
    </div>
  );
}
