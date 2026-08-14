import type { ModelStatus } from '@/types';

/**
 * Avertissement sur la provenance du modèle ayant produit un résultat.
 *
 * Trois états, et non deux. La distinction qui compte n'est pas « modèle
 * entraîné ou non » mais « valeur clinique établie ou non » :
 *
 * - `placeholder` — le réseau n'a jamais vu de mammographie, ses sorties sont
 *   du bruit ;
 * - `trained_unvalidated` — le modèle a bien appris, mais sa validité clinique
 *   n'a jamais été établie. Ses sorties dépendent réellement du cliché, donc
 *   elles sont plausibles, donc crédibles : le bandeau doit rester aussi visible
 *   que pour le cas précédent ;
 * - `validated` — aucun bandeau de provenance. `MedicalDisclaimer` reste affiché
 *   par ailleurs, dans les trois cas.
 *
 * Le texte vient du backend (`model_warning`) et n'est pas réécrit ici : une
 * seule fonction serveur décide de ce qui est dit, et l'interface ne peut pas en
 * dériver. Aucun titre n'est ajouté par le composant, le message du serveur
 * s'ouvre déjà sur sa propre en-tête en capitales.
 *
 * Ne pas atténuer ces bandeaux : un lecteur pressé lit un pourcentage bien avant
 * une note de bas de page.
 */
export default function ModelProvenanceWarning({
  status,
  message,
}: {
  status: ModelStatus;
  message: string | null;
}) {
  // Un modèle validé n'a pas de bandeau ; un message absent n'en a pas non plus.
  // Les deux conditions doivent tomber ensemble — si elles divergent, c'est le
  // serveur qui est incohérent, et se taire serait le mauvais choix par défaut.
  if (status === 'validated' || !message) return null;

  // Le cas « entraîné mais non validé » est ambré plutôt que rouge : distinguer
  // les deux d'un coup d'œil compte, mais l'encadré reste plein et contrasté,
  // jamais une simple note discrète.
  const tone =
    status === 'placeholder'
      ? 'border-red-600 bg-red-50 text-red-900'
      : 'border-amber-600 bg-amber-50 text-amber-900';

  return (
    <aside
      role="alert"
      data-model-status={status}
      className={`rounded-lg border-2 px-4 py-3 text-sm font-medium leading-relaxed ${tone}`}
    >
      {message}
    </aside>
  );
}
