/**
 * Types miroirs des schémas Pydantic du backend (`backend/app/models/schemas.py`).
 *
 * Écrits à la main plutôt que générés depuis l'OpenAPI : la surface est petite
 * et une génération automatique ajouterait une étape de build à maintenir. En
 * contrepartie, toute évolution d'un schéma côté backend doit être répercutée
 * ici — c'est le seul point de vigilance.
 */

export type UserRole = 'admin' | 'doctor' | 'researcher';

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Administrateur',
  doctor: 'Médecin / Radiologue',
  researcher: 'Chercheur',
};

/** Rôles autorisés à consulter des dossiers nominatifs, comme côté backend. */
export const CLINICAL_ROLES: UserRole[] = ['admin', 'doctor'];

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export type Sex = 'F' | 'M' | 'O';

export const SEX_LABELS: Record<Sex, string> = {
  F: 'Féminin',
  M: 'Masculin',
  O: 'Autre',
};

export interface Patient {
  id: string;
  code: string;
  first_name: string;
  last_name: string;
  full_name: string;
  birth_date: string | null;
  sex: Sex;
  phone: string | null;
  email: string | null;
  address: string | null;
  medical_history: string | null;
  notes: string | null;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface PatientPayload {
  code: string;
  first_name: string;
  last_name: string;
  birth_date: string | null;
  sex: Sex;
  phone: string | null;
  email: string | null;
  address: string | null;
  medical_history: string | null;
  notes: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface MessageResponse {
  message: string;
}
