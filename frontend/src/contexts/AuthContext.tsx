import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import * as api from '@/lib/api';
import { clearTokens, getAccessToken } from '@/lib/tokens';
import type { User, UserRole } from '@/types';

interface AuthState {
  user: User | null;
  /** Vrai pendant la restauration de session au premier rendu. */
  isLoading: boolean;
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => Promise<User>;
  signOut: () => Promise<void>;
  hasRole: (...roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restauration de session : un jeton présent ne suffit pas, il peut avoir
  // expiré ou le compte avoir été désactivé entre-temps. Seul le serveur fait foi.
  useEffect(() => {
    let cancelled = false;

    async function restore() {
      if (!getAccessToken()) {
        setIsLoading(false);
        return;
      }
      try {
        const profile = await api.fetchCurrentUser();
        if (!cancelled) setUser(profile);
      } catch {
        clearTokens();
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    const profile = await api.fetchCurrentUser();
    setUser(profile);
    return profile;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // La déconnexion serveur n'est qu'une trace d'audit : si elle échoue
      // (réseau coupé, jeton déjà expiré), la session locale doit tout de même
      // être effacée. L'inverse laisserait un utilisateur connecté malgré lui.
    } finally {
      clearTokens();
      setUser(null);
    }
  }, []);

  const hasRole = useCallback(
    (...roles: UserRole[]) => (user ? roles.includes(user.role) : false),
    [user],
  );

  const value = useMemo<AuthState>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      signIn,
      signOut,
      hasRole,
    }),
    [user, isLoading, signIn, signOut, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth doit être utilisé à l'intérieur d'un AuthProvider.");
  }
  return context;
}
