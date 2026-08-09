/** Hooks React Query pour les analyses et le tableau de bord. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '@/lib/api';
import type { AnalysisFilters, AnalysisReview } from '@/types';

export const ANALYSES_PAGE_SIZE = 10;

/** Taille de page de l'historique : plus large que la liste d'un dossier. */
export const PAGE_SIZE = 20;

export const analysisKeys = {
  all: ['analyses'] as const,
  lists: () => [...analysisKeys.all, 'list'] as const,
  list: (patientId: string | undefined, offset: number) =>
    [...analysisKeys.lists(), { patientId, offset }] as const,
  search: (filters: AnalysisFilters, offset: number) =>
    [...analysisKeys.lists(), 'search', { ...filters, offset }] as const,
  detail: (id: string) => [...analysisKeys.all, 'detail', id] as const,
  stats: ['stats', 'dashboard'] as const,
};

export function useAnalyses(patientId: string | undefined, offset = 0) {
  return useQuery({
    queryKey: analysisKeys.list(patientId, offset),
    queryFn: () =>
      api.fetchAnalyses({ patientId, limit: ANALYSES_PAGE_SIZE, offset }),
    placeholderData: (previous) => previous,
  });
}

export function useAnalysisSearch(filters: AnalysisFilters, offset = 0) {
  return useQuery({
    queryKey: analysisKeys.search(filters, offset),
    queryFn: () =>
      api.fetchAnalyses({
        // Les chaînes vides deviennent `undefined` : le client ne doit pas
        // envoyer `prediction=` au serveur, qui refuserait la valeur.
        search: filters.search || undefined,
        prediction: filters.prediction || undefined,
        status: filters.status || undefined,
        dateFrom: filters.dateFrom || undefined,
        dateTo: filters.dateTo || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    // Garde la page précédente pendant le chargement : sinon le tableau se vide
    // à chaque frappe dans la recherche.
    placeholderData: (previous) => previous,
  });
}

export function useAnalysis(id: string | undefined) {
  return useQuery({
    queryKey: analysisKeys.detail(id ?? ''),
    queryFn: () => api.fetchAnalysis(id as string),
    enabled: Boolean(id),
  });
}

export function useUploadAnalysis(patientId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => api.uploadAnalysis(patientId, file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: analysisKeys.lists() });
      // Le dépôt change aussi les compteurs du tableau de bord.
      void queryClient.invalidateQueries({ queryKey: analysisKeys.stats });
    },
  });
}

export function useReviewAnalysis(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (review: AnalysisReview) => api.reviewAnalysis(id, review),
    onSuccess: (analysis) => {
      queryClient.setQueryData(analysisKeys.detail(id), analysis);
      void queryClient.invalidateQueries({ queryKey: analysisKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: analysisKeys.stats });
    },
  });
}

export function useRerunInference(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.rerunInference(id),
    onSuccess: (analysis) => {
      queryClient.setQueryData(analysisKeys.detail(id), analysis);
      void queryClient.invalidateQueries({ queryKey: analysisKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: analysisKeys.stats });
    },
  });
}

export function useDashboardStats() {
  return useQuery({
    queryKey: analysisKeys.stats,
    queryFn: api.fetchDashboardStats,
  });
}
