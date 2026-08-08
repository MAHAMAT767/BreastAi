import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';

import { useAuth } from '@/contexts/AuthContext';
import { Alert, Spinner } from '@/components/ui';
import { ROLE_LABELS } from '@/types';
import type { UserRole } from '@/types';

interface ProtectedRouteProps {
  children: ReactNode;
  /** Si renseigné, seuls ces rôles sont admis. */
  roles?: UserRole[];
}

export default function ProtectedRoute({ children, roles }: ProtectedRouteProps) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const location = useLocation();

  // Tant que la session est en cours de restauration, on ne redirige pas : sinon
  // un rafraîchissement de page renverrait vers la connexion alors que
  // l'utilisateur a un jeton valide.
  if (isLoading) {
    return (
      <div className="mx-auto max-w-lg px-6 py-20">
        <Spinner label="Vérification de la session…" />
      </div>
    );
  }

  if (!isAuthenticated) {
    // `state.from` permet de revenir à la page demandée après connexion.
    return <Navigate to="/connexion" replace state={{ from: location.pathname }} />;
  }

  if (roles && user && !roles.includes(user.role)) {
    // Pas de redirection : renvoyer vers l'accueil laisserait croire à un bug.
    // L'utilisateur doit comprendre que l'accès lui est refusé, et pourquoi.
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <Alert variant="warning">
          <p className="font-semibold">Accès refusé</p>
          <p className="mt-1">
            Cette section est réservée aux rôles suivants :{' '}
            {roles.map((role) => ROLE_LABELS[role]).join(', ')}. Votre compte est
            enregistré comme « {ROLE_LABELS[user.role]} ».
          </p>
        </Alert>
      </div>
    );
  }

  return <>{children}</>;
}
