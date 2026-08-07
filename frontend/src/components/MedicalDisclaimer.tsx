/**
 * Avertissement médical.
 *
 * Doit rester visible partout où un résultat d'IA est présenté : résultat
 * d'analyse, rapport, réponse de l'assistant. Ne pas retirer ce composant d'un
 * écran de résultat.
 */
export const MEDICAL_DISCLAIMER =
  "BreastAI est un outil d'aide à la décision. Ses résultats ne constituent pas un " +
  "diagnostic et ne remplacent pas l'avis d'un professionnel de santé qualifié.";

export default function MedicalDisclaimer() {
  return (
    <aside
      role="note"
      className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <span className="font-semibold">Avertissement médical — </span>
      {MEDICAL_DISCLAIMER}
    </aside>
  );
}
