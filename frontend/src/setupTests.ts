import '@testing-library/jest-dom/vitest';

/**
 * jsdom n'implémente pas `ResizeObserver`, dont dépend le `ResponsiveContainer`
 * de Recharts : sans cette prothèse, tout composant contenant un graphique lève
 * au montage. Volontairement inerte — les tests portent sur le contenu, pas sur
 * une géométrie que jsdom ne calcule pas.
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
 * images et les rapports PDF. Posée ici une fois pour toutes et non par test :
 * le nettoyage des effets React s'exécute après les `afterEach`, donc un
 * `unstubAllGlobals` retirerait `revokeObjectURL` juste avant son appel.
 */
if (typeof URL.createObjectURL !== 'function') {
  URL.createObjectURL = () => 'blob:test';
  URL.revokeObjectURL = () => {};
}
