/**
 * Avertissement affiché tant qu'aucun modèle entraîné n'est déployé.
 *
 * Le texte vient du backend (`model_warning`) et n'est pas réécrit ici : le jour
 * où un vrai modèle est déployé, l'avertissement disparaît de lui-même partout,
 * sans qu'il faille penser à retirer quoi que ce soit.
 *
 * Aucun titre n'est ajouté par le composant : le message du serveur s'ouvre
 * déjà sur « MODÈLE DE DÉMONSTRATION — AUCUNE VALEUR CLINIQUE », et en poser un
 * second au-dessus affichait deux fois la même phrase.
 *
 * Ne pas atténuer ce bandeau. Les chiffres qu'il accompagne sont du bruit, et
 * un lecteur pressé lit un pourcentage bien avant une note de bas de page.
 */
export default function PlaceholderModelWarning({ message }: { message: string }) {
  return (
    <aside
      role="alert"
      className="rounded-lg border-2 border-red-600 bg-red-50 px-4 py-3 text-sm font-medium leading-relaxed text-red-900"
    >
      {message}
    </aside>
  );
}
