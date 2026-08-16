import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import ribbonLogo from '@/assets/ribbon-logo.png';
import MedicalDisclaimer from '@/components/MedicalDisclaimer';
import { Button } from '@/components/ui';
import { useAuth } from '@/contexts/AuthContext';
import { CLINICAL_ROLES, ROLE_LABELS } from '@/types';

const NAV_LINK_BASE =
  'rounded-md px-3 py-2 text-sm font-medium transition focus-visible:outline-none ' +
  'focus-visible:ring-2 focus-visible:ring-brand-500/40';

function navLinkClasses({ isActive }: { isActive: boolean }): string {
  return isActive
    ? `${NAV_LINK_BASE} bg-brand-50 text-brand-700`
    : `${NAV_LINK_BASE} text-slate-600 hover:bg-slate-100`;
}

export default function AppLayout() {
  const { user, signOut, hasRole } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOut();
    navigate('/connexion', { replace: true });
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-6 py-3">
          <NavLink
            to="/"
            className="flex items-center gap-2 text-xl font-bold tracking-tight text-brand-700"
          >
            {/* `alt` vide, volontairement : le mot « BreastAI » qui suit nomme
                déjà l'application. Décrire le ruban le ferait annoncer deux
                fois par un lecteur d'écran, sans rien apprendre de plus. */}
            <img src={ribbonLogo} alt="" className="h-8 w-auto" />
            BreastAI
          </NavLink>

          <nav aria-label="Navigation principale" className="flex items-center gap-1">
            <NavLink to="/" end className={navLinkClasses}>
              Accueil
            </NavLink>
            {/* Le lien n'apparaît pas pour un chercheur : l'API lui répondrait
                403, autant ne pas lui proposer une porte fermée. */}
            {hasRole(...CLINICAL_ROLES) && (
              <>
                <NavLink to="/patients" className={navLinkClasses}>
                  Patients
                </NavLink>
                <NavLink to="/analyses" end className={navLinkClasses}>
                  Analyses
                </NavLink>
              </>
            )}
            {/* Ouvert à tous les rôles : le tableau de bord n'expose que des
                chiffres agrégés. */}
            <NavLink to="/tableau-de-bord" className={navLinkClasses}>
              Tableau de bord
            </NavLink>
          </nav>

          <div className="ml-auto flex items-center gap-3">
            {user && (
              <div className="text-right leading-tight">
                <p className="text-sm font-medium text-slate-800">{user.full_name}</p>
                <p className="text-xs text-slate-500">{ROLE_LABELS[user.role]}</p>
              </div>
            )}
            <Button variant="secondary" onClick={handleSignOut}>
              Déconnexion
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl space-y-4 px-6 py-6">
          {/* L'avertissement médical reste présent sur toutes les pages de
              l'application, pas seulement sur les écrans de résultat. */}
          <MedicalDisclaimer />
          <div className="space-y-1 text-xs text-slate-500">
            <p>
              Dédié à la mémoire de <strong className="text-slate-700">Mouna Abakar</strong>.
            </p>
            {/* « Réalisé par » plutôt que le nom seul : placé juste sous une
                ligne d'hommage, un nom nu se lirait comme en faisant partie. */}
            <p>
              Réalisé par{' '}
              <strong className="text-slate-700">Mahamat Haroun Ibrahim</strong>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
