/** Outils partagés par les tests de composants. */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { RenderResult } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

import { AuthProvider } from '@/contexts/AuthContext';
import { storeTokens } from '@/lib/tokens';
import type { Patient, User, UserRole } from '@/types';

export const API_BASE = 'http://localhost:8000/api/v1';

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'user-1',
    email: 'medecin@breastai.td',
    full_name: 'Dr Test',
    role: 'doctor',
    is_active: true,
    created_at: '2026-01-15T09:00:00Z',
    last_login_at: null,
    ...overrides,
  };
}

export function makePatient(overrides: Partial<Patient> = {}): Patient {
  return {
    id: 'patient-1',
    code: 'TCD-2026-0001',
    first_name: 'Amina',
    last_name: 'Ali',
    full_name: 'Amina Ali',
    birth_date: '1980-05-12',
    sex: 'F',
    phone: null,
    email: null,
    address: null,
    medical_history: null,
    notes: null,
    is_deleted: false,
    created_at: '2026-02-01T10:00:00Z',
    updated_at: '2026-02-01T10:00:00Z',
    ...overrides,
  };
}

// --------------------------------------------------------------------------- //
// Faux serveur
// --------------------------------------------------------------------------- //

type Handler = (request: { url: string; method: string; body: unknown }) => {
  status?: number;
  body?: unknown;
};

/**
 * Remplace `fetch` par un routeur de réponses préparées.
 *
 * Les clés sont de la forme `"GET /patients"`. La correspondance ignore la
 * chaîne de requête, pour qu'un test n'ait pas à reproduire l'ordre exact des
 * paramètres produits par `URLSearchParams`.
 */
export function mockApi(routes: Record<string, Handler | { status?: number; body?: unknown }>) {
  const calls: { url: string; method: string; body: unknown }[] = [];

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();
    const method = (init?.method ?? 'GET').toUpperCase();
    const path = url.replace(API_BASE, '').split('?')[0];

    let body: unknown = null;
    if (typeof init?.body === 'string') {
      try {
        body = JSON.parse(init.body);
      } catch {
        body = init.body;
      }
    }

    calls.push({ url, method, body });

    const route = routes[`${method} ${path}`];
    if (!route) {
      return new Response(JSON.stringify({ detail: `Route non simulée : ${method} ${path}` }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const result = typeof route === 'function' ? route({ url, method, body }) : route;
    return new Response(result.body === undefined ? '' : JSON.stringify(result.body), {
      status: result.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });

  vi.stubGlobal('fetch', fetchMock);
  return { calls, fetchMock };
}

// --------------------------------------------------------------------------- //
// Rendu
// --------------------------------------------------------------------------- //

interface RenderOptions {
  route?: string;
  /** Place des jetons en session avant le rendu, comme après une connexion. */
  authenticated?: boolean;
}

export function renderWithProviders(ui: ReactNode, options: RenderOptions = {}): RenderResult {
  const { route = '/', authenticated = false } = options;

  if (authenticated) {
    storeTokens('jeton-acces-de-test', 'jeton-refresh-de-test');
  }

  const queryClient = new QueryClient({
    defaultOptions: {
      // Pas de réessai en test : une erreur attendue mettrait plusieurs
      // secondes à remonter et rendrait les échecs illisibles.
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export function makeRoleUser(role: UserRole): User {
  return makeUser({ role, full_name: `Compte ${role}` });
}
