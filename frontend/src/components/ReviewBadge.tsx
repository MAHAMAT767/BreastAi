/**
 * État de relecture médicale d'une analyse.
 *
 * Vert pour « validée », gris pour « non relue » — et non vert contre rouge :
 * une analyse pas encore relue n'est pas en faute, elle attend. Lui donner une
 * couleur d'alerte ferait lire un retard de traitement comme un problème
 * clinique.
 *
 * Le vert ne rentre pas en concurrence avec les teintes de résultat : il répond
 * à une autre question (« un médecin a-t-il relu ? ») et n'apparaît jamais dans
 * la même colonne qu'un bénin/malin.
 */
export default function ReviewBadge({ validated }: { validated: boolean }) {
  return validated ? (
    <span className="inline-flex items-center rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">
      Validée
    </span>
  ) : (
    <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
      Non relue
    </span>
  );
}
