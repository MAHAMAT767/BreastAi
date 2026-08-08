/** Hooks React Query pour les dossiers patients. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '@/lib/api';
import type { PatientPayload } from '@/types';

export const PAGE_SIZE = 20;

/**
 * Clés de cache, centralisées.
 *
 * Les écrire à la main dans chaque composant finit toujours par produire une
 * invalidation qui ne correspond à aucune requête, et une liste qui ne se
 * rafraîchit pas après création.
 */
export const patientKeys = {
  all: ['patients'] as const,
  lists: () => [...patientKeys.all, 'list'] as const,
  list: (search: string, offset: number) => [...patientKeys.lists(), { search, offset }] as const,
  detail: (id: string) => [...patientKeys.all, 'detail', id] as const,
};

export function usePatientList(search: string, offset: number) {
  return useQuery({
    queryKey: patientKeys.list(search, offset),
    queryFn: () => api.fetchPatients({ search, limit: PAGE_SIZE, offset }),
    // Conserve la page précédente pendant le chargement de la suivante :
    // sans cela, le tableau se vide à chaque frappe dans la recherche.
    placeholderData: (previous) => previous,
  });
}

export function usePatient(id: string | undefined) {
  return useQuery({
    queryKey: patientKeys.detail(id ?? ''),
    queryFn: () => api.fetchPatient(id as string),
    enabled: Boolean(id),
  });
}

export function useCreatePatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: PatientPayload) => api.createPatient(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: patientKeys.lists() });
    },
  });
}

export function useUpdatePatient(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: Partial<PatientPayload>) => api.updatePatient(id, payload),
    onSuccess: (patient) => {
      queryClient.setQueryData(patientKeys.detail(id), patient);
      void queryClient.invalidateQueries({ queryKey: patientKeys.lists() });
    },
  });
}

export function useDeletePatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.deletePatient(id),
    onSuccess: (_result, id) => {
      queryClient.removeQueries({ queryKey: patientKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: patientKeys.lists() });
    },
  });
}
