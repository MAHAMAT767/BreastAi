import { useEffect, useState } from 'react';

/**
 * Retarde la propagation d'une valeur.
 *
 * Sur la recherche de patients, sans cela, chaque frappe déclencherait une
 * requête : dix caractères tapés, dix appels à l'API dont neuf déjà obsolètes.
 */
export function useDebounce<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
