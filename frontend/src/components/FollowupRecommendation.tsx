import type { FollowupUrgency } from '@/types';

/**
 * Délai de prise en charge suggéré.
 *
 * Uniquement sur le détail d'une analyse, jamais dans une liste ni sur le
 * tableau de bord : un délai lu hors de son contexte — sans la probabilité, sans
 * le bandeau de provenance, sans la lecture du médecin — se réduit à une
 * consigne, ce qu'il n'est pas.
 *
 * Le libellé et la mention viennent du serveur (`app/followup.py`) et ne sont
 * pas réécrits ici : la grille vit à un seul endroit, sinon l'écran et le
 * rapport PDF finiraient par annoncer deux délais différents.
 *
 * ## Traitement visuel
 *
 * Volontairement plus discret que `ModelProvenanceWarning`. La hiérarchie est
 * délibérée : ce bandeau-là dit que les chiffres ne valent rien cliniquement, et
 * doit rester le plus fort de la page. Une recommandation de délai qui crierait
 * plus fort qu'un avertissement de non-validation inverserait ce qui compte.
 *
 * Aucune teinte de résultat non plus : bleu et orange désignent bénin et malin,
 * les réutiliser pour une urgence brouillerait les deux vocabulaires. Le niveau
 * se lit dans le texte, pas dans la couleur.
 */
const URGENCY_TONES: Record<FollowupUrgency, string> = {
  urgent: 'border-l-slate-700',
  rapproche: 'border-l-slate-500',
  surveillance: 'border-l-slate-400',
  routine: 'border-l-slate-300',
};

export default function FollowupRecommendation({
  urgency,
  label,
  notice,
}: {
  urgency: FollowupUrgency | null;
  label: string | null;
  notice: string | null;
}) {
  // Pas de résultat, pas de délai. Un encadré vide laisserait croire à une
  // information manquante plutôt qu'à une analyse encore sans résultat.
  if (!urgency || !label) return null;

  return (
    <aside
      data-followup-urgency={urgency}
      className={`rounded-md border border-slate-200 border-l-4 bg-slate-50 px-3 py-2 ${URGENCY_TONES[urgency]}`}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        Délai de prise en charge suggéré
      </p>
      <p className="mt-0.5 text-sm font-medium text-slate-900">{label}</p>
      {notice && <p className="mt-1 text-xs leading-snug text-slate-600">{notice}</p>}
    </aside>
  );
}
