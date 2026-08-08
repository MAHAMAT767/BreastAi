/** Mise en forme des données affichées. */

const DATE_FORMATTER = new Intl.DateTimeFormat('fr-FR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
});

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat('fr-FR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

export const PLACEHOLDER = '—';

export function formatDate(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? PLACEHOLDER : DATE_FORMATTER.format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? PLACEHOLDER : DATE_TIME_FORMATTER.format(date);
}

/**
 * Âge en années révolues à partir d'une date de naissance ISO.
 *
 * Affiché à côté de la date : l'âge conditionne l'interprétation d'une
 * mammographie et le calculer de tête à chaque dossier est une perte de temps.
 */
export function computeAge(birthDate: string | null | undefined): number | null {
  if (!birthDate) return null;

  const birth = new Date(birthDate);
  if (Number.isNaN(birth.getTime())) return null;

  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();

  const monthDelta = today.getMonth() - birth.getMonth();
  if (monthDelta < 0 || (monthDelta === 0 && today.getDate() < birth.getDate())) {
    age -= 1;
  }

  return age >= 0 ? age : null;
}

export function formatBirthDate(birthDate: string | null | undefined): string {
  const age = computeAge(birthDate);
  const formatted = formatDate(birthDate);
  return age === null ? formatted : `${formatted} (${age} ans)`;
}

/** Vide une chaîne de formulaire vers `null`, comme l'attend l'API. */
export function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}
