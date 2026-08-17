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

/**
 * Initiales d'un patient, pour la pastille des listes.
 *
 * Purement décoratif : le nom complet est écrit juste à côté. Un dossier dont
 * le nom serait vide rend une chaîne vide plutôt qu'un caractère parasite.
 */
export function initials(firstName: string, lastName: string): string {
  return [firstName, lastName]
    .map((part) => part.trim().charAt(0).toUpperCase())
    .join('');
}

const RELATIVE_FORMATTER = new Intl.RelativeTimeFormat('fr-FR', { numeric: 'auto' });

const RELATIVE_STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['second', 60],
  ['minute', 60],
  ['hour', 24],
  ['day', 7],
  ['week', 4.35],
  ['month', 12],
];

/**
 * Ancienneté lisible (« il y a 3 heures »).
 *
 * Employée là où la date exacte n'apporte rien — une liste d'activité se lit
 * en repérant ce qui est récent, pas en comparant des horodatages. Les vues qui
 * servent à retrouver une analyse précise gardent `formatDateTime`.
 */
export function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;

  let amount = (date.getTime() - Date.now()) / 1000;
  for (const [unit, step] of RELATIVE_STEPS) {
    if (Math.abs(amount) < step) return RELATIVE_FORMATTER.format(Math.round(amount), unit);
    amount /= step;
  }
  return RELATIVE_FORMATTER.format(Math.round(amount), 'year');
}

/** Vide une chaîne de formulaire vers `null`, comme l'attend l'API. */
export function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}
