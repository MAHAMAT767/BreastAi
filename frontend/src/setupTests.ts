import '@testing-library/jest-dom/vitest';

/**
 * jsdom n'implémente pas `ResizeObserver`, dont dépend le `ResponsiveContainer`
 * de Recharts pour se dimensionner. Sans cette prothèse, tout composant
 * contenant un graphique lève au montage.
 *
 * L'implémentation est volontairement inerte : les tests portent sur le
 * contenu — libellés, légendes, tableau de données — et non sur la géométrie
 * calculée, que jsdom ne saurait de toute façon pas produire.
 */
if (!('ResizeObserver' in globalThis)) {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };
}

/**
 * jsdom n'implémente pas non plus les URL d'objet, par lesquelles passent les
 * images d'analyse et les rapports PDF — récupérés en blob avec le jeton, puis
 * remis au navigateur.
 *
 * La prothèse est posée ici, une fois pour toutes, et non par test : le nettoyage
 * des effets React s'exécute après les `afterEach`, donc un `unstubAllGlobals`
 * retirerait `revokeObjectURL` juste avant que le démontage ne l'appelle.
 */
if (typeof URL.createObjectURL !== 'function') {
  URL.createObjectURL = () => 'blob:test';
  URL.revokeObjectURL = () => {};
}
