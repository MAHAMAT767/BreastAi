"""Superposition de la carte Grad-CAM sur la mammographie."""

from __future__ import annotations

import cv2
import numpy as np

from app.ai.explainability.heatmap import to_colormap
from app.ai.inference.schemas import SuspiciousRegion

#: Poids de la carte dans le mélange. Au-delà, la couleur masque le tissu et le
#: médecin ne peut plus juger de ce qu'il y a sous la carte de chaleur.
DEFAULT_ALPHA: float = 0.4

#: Vert : ne se confond avec aucune couleur de la palette JET.
REGION_COLOR: tuple[int, int, int] = (0, 255, 0)


def overlay_heatmap(
    grayscale: np.ndarray,
    cam: np.ndarray,
    alpha: float = DEFAULT_ALPHA,
    region: SuspiciousRegion | None = None,
) -> np.ndarray:
    """Superpose la carte à l'image prétraitée. Renvoie une image BGR.

    L'image de fond est celle **vue par le modèle**, pas l'originale : afficher
    la carte sur un autre support laisserait croire à une correspondance
    géométrique qui n'existe pas.
    """
    if grayscale.ndim != 2:
        raise ValueError("L'image de fond doit être en niveaux de gris.")
    if cam.shape != grayscale.shape:
        cam = cv2.resize(cam, (grayscale.shape[1], grayscale.shape[0]))

    background = cv2.cvtColor(grayscale, cv2.COLOR_GRAY2BGR)
    blended = cv2.addWeighted(background, 1.0 - alpha, to_colormap(cam), alpha, 0.0)

    if region is not None:
        cv2.rectangle(
            blended,
            (region.x, region.y),
            (region.x + region.width, region.y + region.height),
            REGION_COLOR,
            thickness=2,
        )

    return blended


def encode_png(image: np.ndarray) -> bytes:
    """Encode une image BGR ou niveaux de gris en PNG."""
    success, buffer = cv2.imencode(".png", image)
    if not success:
        raise ValueError("Échec de l'encodage PNG de la superposition.")
    return buffer.tobytes()
