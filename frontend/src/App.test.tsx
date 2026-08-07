import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from '@/App';
import { MEDICAL_DISCLAIMER } from '@/components/MedicalDisclaimer';

function renderApp() {
  // Nouveau QueryClient par test : sinon le cache fuit d'un test à l'autre.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('App', () => {
  it("affiche le titre et le sous-titre de l'application", () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')));
    renderApp();

    expect(screen.getByRole('heading', { name: 'BreastAI' })).toBeInTheDocument();
    expect(screen.getByText(/aide au dépistage du cancer du sein/i)).toBeInTheDocument();
  });

  it("affiche l'avertissement médical sur la page d'accueil", () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')));
    renderApp();

    expect(screen.getByRole('note')).toHaveTextContent(MEDICAL_DISCLAIMER);
  });

  it('rend la dédicace à Mouna Abakar', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')));
    renderApp();

    expect(screen.getByText('Mouna Abakar')).toBeInTheDocument();
  });
});
