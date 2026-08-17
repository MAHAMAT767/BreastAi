/**
 * Types miroirs des schémas Pydantic du backend (`backend/app/models/schemas.py`).
 *
 * Écrits à la main : toute évolution d'un schéma côté backend doit être
 * répercutée ici.
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

// --------------------------------------------------------------------------- //
// Analyses
// --------------------------------------------------------------------------- //

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed';

export const STATUS_LABELS: Record<AnalysisStatus, string> = {
  pending: 'En attente',
  processing: 'En cours',
  completed: 'Terminée',
  failed: 'Échec',
};

export type Prediction = 'benign' | 'malignant';

export const PREDICTION_LABELS: Record<Prediction, string> = {
  benign: 'Bénin',
  malignant: 'Malin',
};

/**
 * Provenance du modèle, réduite par le serveur à un seul état.
 *
 * Calculée à partir de `is_placeholder_model` et `clinically_validated` — jamais
 * stockée, jamais recombinée côté client : c'est le backend qui tranche.
 */
export type ModelStatus = 'placeholder' | 'trained_unvalidated' | 'validated';

/**
 * Délai de prise en charge suggéré, du plus pressant au moins pressant.
 *
 * Dérivé côté serveur de la probabilité déjà calculée (`app/followup.py`) — ce
 * n'est pas une seconde prédiction. La grille n'est **pas validée
 * cliniquement** : `followup_notice` doit accompagner le délai partout où il
 * est affiché.
 *
 * Le libellé vient du serveur et n'est jamais reconstruit ici : la règle vit à
 * un seul endroit, sinon l'écran et le rapport PDF finissent par diverger.
 */
export type FollowupUrgency = 'urgent' | 'rapproche' | 'surveillance' | 'routine';

export interface SuspiciousRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Analysis {
  id: string;
  patient_id: string;
  original_filename: string;
  image_format: string | null;
  file_size_bytes: number | null;
  status: AnalysisStatus;

  prediction: Prediction | null;
  /** Probabilité de la classe **maligne**, quelle que soit la classe prédite. */
  probability: number | null;
  confidence: number | null;
  inference_time_ms: number | null;
  model_version: string | null;
  preprocessing_version: string | null;
  error_message: string | null;

  doctor_comment: string | null;
  doctor_validated: boolean;
  created_at: string;

  is_placeholder_model: boolean;
  clinically_validated: boolean;
  model_status: ModelStatus;
  model_warning: string | null;

  followup_urgency: FollowupUrgency | null;
  followup_label: string | null;
  followup_notice: string | null;

  has_gradcam: boolean;
  gradcam_disclaimer: string | null;
  suspicious_region: SuspiciousRegion | null;
  has_report: boolean;
  report_generated_at: string | null;
  report_signature: string | null;

  disclaimer: string;
}

export type AnalysisImageKind = 'original' | 'processed' | 'gradcam';

/** Filtres de l'historique. Chaînes vides = critère non appliqué. */
export interface AnalysisFilters {
  search: string;
  prediction: '' | Prediction;
  status: '' | AnalysisStatus;
  dateFrom: string;
  dateTo: string;
}

export interface AnalysisReview {
  doctor_comment?: string | null;
  doctor_validated?: boolean | null;
}

export interface ReportVerification {
  analysis_id: string;
  has_report: boolean;
  signature_valid: boolean;
  generated_at: string | null;
  detail: string;
}

/** Formats acceptés par l'API, alignés sur `ALLOWED_EXTENSIONS` côté backend. */
export const ACCEPTED_EXTENSIONS = ['.dcm', '.dicom', '.png', '.jpg', '.jpeg'] as const;
export const MAX_UPLOAD_SIZE_MB = 50;

// --------------------------------------------------------------------------- //
// Assistant conversationnel
// --------------------------------------------------------------------------- //

export interface AssistantMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AssistantAnswer {
  /** Texte complet, avertissements compris : à citer ou à copier. */
  answer: string;
  /** Réponse brute du modèle, sans les avertissements. */
  answer_body: string;
  model: string;
  disclaimer: string;
  is_placeholder_model: boolean;
  clinically_validated: boolean;
  model_status: ModelStatus;
  model_warning: string | null;
  /** Contexte exact transmis au fournisseur, pour vérification. */
  context_sent: string;
  usage: Record<string, number>;
}

export interface AssistantStatus {
  enabled: boolean;
  model: string | null;
  provider: string;
  disclaimer: string;
  notice: string;
}

// --------------------------------------------------------------------------- //
// Tableau de bord
// --------------------------------------------------------------------------- //

export interface MonthlyCount {
  month: string;
  total: number;
  benign: number;
  malignant: number;
}

export interface DashboardStats {
  total_patients: number;
  total_analyses: number;
  completed_analyses: number;
  pending_analyses: number;
  failed_analyses: number;
  benign_count: number;
  malignant_count: number;
  average_inference_time_ms: number | null;
  doctor_validated_count: number;
  doctor_validation_rate: number | null;
  monthly: MonthlyCount[];
  model_versions: string[];
  is_placeholder_model: boolean;
  clinically_validated: boolean;
  model_status: ModelStatus;
  model_warning: string | null;
  accuracy_available: boolean;
  accuracy_note: string;
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
