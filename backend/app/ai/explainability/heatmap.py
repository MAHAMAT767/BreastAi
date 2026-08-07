"""Conversion d'une carte Grad-CAM en image colorée."""

from __future__ import annotations

import cv2
import numpy as np

#: JET reste la convention en imagerie médicale pour les cartes d'activation :
#: bleu froid pour les zones ignorées, rouge pour les zones déterminantes.
DEFAULT_COLORMAP: int = cv2.COLORMAP_JET


def to_colormap(cam: np.ndarray, colormap: int = DEFAULT_COLORMAP) -> np.ndarray:
    """Applique une palette à une carte normalisée dans [0, 1]. Renvoie du BGR."""
    if cam.dtype != np.uint8:
        cam = np.clip(cam, 0.0, 1.0)
        cam = (cam * 255).astype(np.uint8)
    return cv2.applyColorMap(cam, colormap)
