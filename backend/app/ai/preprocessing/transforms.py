"""Transformations appliquées aux mammographies avant l'inférence.

Chaque fonction prend et rend un tableau NumPy, sans effet de bord, pour rester
utilisable aussi bien depuis l'API que depuis un notebook d'exploration.
"""

from __future__ import annotations

from typing import Final

import cv2
import numpy as np

from app.ai import IMAGE_SIZE, IMAGENET_MEAN, IMAGENET_STD

#: Taille du noyau du filtre médian. Impair et petit : il retire le bruit
#: impulsionnel des capteurs sans effacer les microcalcifications, qui sont
#: précisément le signal que l'on cherche.
MEDIAN_KERNEL_SIZE: Final[int] = 3

#: Paramètres CLAHE. Un `clip_limit` plus élevé accentue le contraste mais
#: amplifie aussi le bruit de fond du sein.
CLAHE_CLIP_LIMIT: Final[float] = 2.0
CLAHE_TILE_GRID_SIZE: Final[tuple[int, int]] = (8, 8)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Réduit une image à un seul canal si elle n'en a pas déjà qu'un."""
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def denoise(image: np.ndarray, kernel_size: int = MEDIAN_KERNEL_SIZE) -> np.ndarray:
    """Supprime le bruit impulsionnel par filtre médian.

    Le médian est préféré à une moyenne ou à un flou gaussien : il n'étale pas
    les contours, ce qui compte pour des lésions dont la forme des bords est un
    critère diagnostique.
    """
    return cv2.medianBlur(image, kernel_size)


def enhance_contrast(
    image: np.ndarray,
    clip_limit: float = CLAHE_CLIP_LIMIT,
    tile_grid_size: tuple[int, int] = CLAHE_TILE_GRID_SIZE,
) -> np.ndarray:
    """Améliore le contraste local par CLAHE.

    L'égalisation d'histogramme globale écraserait les faibles différences de
    densité dans le tissu dense ; CLAHE travaille par tuiles et limite le gain,
    ce qui fait ressortir les structures locales sans saturer l'image.
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(image)


def resize_with_padding(
    image: np.ndarray, size: tuple[int, int] = IMAGE_SIZE
) -> np.ndarray:
    """Redimensionne à `size` en conservant les proportions, avec remplissage noir.

    Déformer l'image changerait la géométrie des lésions — or la forme et le
    rapport d'aspect d'une masse font partie des critères de lecture. Le
    remplissage est noir car c'est déjà la valeur du fond sur une mammographie.
    """
    target_height, target_width = size
    height, width = image.shape[:2]

    if height == 0 or width == 0:
        raise ValueError("Image vide : redimensionnement impossible.")

    scale = min(target_height / height, target_width / width)
    new_height = max(1, int(round(height * scale)))
    new_width = max(1, int(round(width * scale)))

    # INTER_AREA pour réduire (évite le crénelage), INTER_CUBIC pour agrandir.
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(image, (new_width, new_height), interpolation=interpolation)

    canvas = np.zeros((target_height, target_width), dtype=resized.dtype)
    top = (target_height - new_height) // 2
    left = (target_width - new_width) // 2
    canvas[top : top + new_height, left : left + new_width] = resized

    return canvas


def normalize(image: np.ndarray) -> np.ndarray:
    """Convertit une image 8 bits en tenseur CHW float32 normalisé ImageNet.

    Le canal unique est répliqué trois fois : les poids pré-entraînés
    d'EfficientNet attendent trois canaux RVB.
    """
    scaled = image.astype(np.float32) / 255.0
    stacked = np.stack([scaled, scaled, scaled], axis=0)

    mean = np.array(IMAGENET_MEAN, dtype=np.float32).reshape(3, 1, 1)
    std = np.array(IMAGENET_STD, dtype=np.float32).reshape(3, 1, 1)

    return (stacked - mean) / std
