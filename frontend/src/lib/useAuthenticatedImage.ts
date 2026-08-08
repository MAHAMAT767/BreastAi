import { useEffect, useState } from 'react';

import { fetchAnalysisImage } from '@/lib/api';
import type { AnalysisImageKind } from '@/types';

interface State {
  url: string | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Charge une image d'analyse et en fait une URL utilisable dans un `<img>`.
 *
 * Une balise `<img src="...">` n'envoie pas d'en-tête d'autorisation : poser
 * l'URL de l'API directement donnerait un 401. L'image est donc récupérée en
 * blob par le client HTTP, qui joint le jeton, puis exposée via `createObjectURL`.
 *
 * L'URL d'objet est révoquée au démontage : sans cela, chaque consultation
 * d'analyse retiendrait une mammographie en mémoire jusqu'au rechargement de
 * la page.
 */
export function useAuthenticatedImage(
  analysisId: string | undefined,
  kind: AnalysisImageKind,
  enabled = true,
): State {
  const [state, setState] = useState<State>({ url: null, isLoading: true, error: null });

  useEffect(() => {
    if (!analysisId || !enabled) {
      setState({ url: null, isLoading: false, error: null });
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;

    setState({ url: null, isLoading: true, error: null });

    fetchAnalysisImage(analysisId, kind)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setState({ url: objectUrl, isLoading: false, error: null });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState({
          url: null,
          isLoading: false,
          error: error instanceof Error ? error.message : 'Image indisponible.',
        });
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [analysisId, kind, enabled]);

  return state;
}
