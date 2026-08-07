"""Chaîne de prétraitement complète, de l'octet reçu au tenseur d'entrée."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np

from app.ai import IMAGE_SIZE
from app.ai.preprocessing.loaders import ImageFormat, load_image
from app.ai.preprocessing.transforms import (
    denoise,
    enhance_contrast,
    normalize,
    resize_with_padding,
    to_grayscale,
)

#: Version de la chaîne de prétraitement, enregistrée avec chaque analyse.
#: Toute modification de l'ordre ou des paramètres des étapes doit l'incrémenter :
#: un modèle entraîné sous une version ne vaut plus rien sous une autre.
PREPROCESSING_VERSION: Final[str] = "v1"


@dataclass(frozen=True, slots=True)
class PreprocessedImage:
    """Résultat du prétraitement.

    `tensor` alimente le réseau. `display` est l'image 8 bits qui sert de fond à
    la superposition Grad-CAM et au rapport PDF : c'est la même image que celle
    vue par le modèle, ce qui évite d'afficher une carte de chaleur sur un
    support différent de celui qui l'a produite.
    """

    tensor: np.ndarray
    display: np.ndarray
    image_format: ImageFormat
    original_size: tuple[int, int]
    duration_ms: float
    version: str = PREPROCESSING_VERSION


def preprocess_array(image: np.ndarray, size: tuple[int, int] = IMAGE_SIZE) -> np.ndarray:
    """Applique les étapes de traitement d'image à un tableau déjà décodé.

    Ordre : niveaux de gris → débruitage → CLAHE → redimensionnement.
    Le débruitage précède le rehaussement de contraste, sinon CLAHE amplifierait
    le bruit avant qu'on ne le retire.
    """
    grayscale = to_grayscale(image)
    denoised = denoise(grayscale)
    enhanced = enhance_contrast(denoised)
    return resize_with_padding(enhanced, size)


def preprocess_for_inference(
    data: bytes, size: tuple[int, int] = IMAGE_SIZE
) -> PreprocessedImage:
    """Décode et prétraite une mammographie reçue sous forme d'octets.

    Cette fonction est le point d'entrée unique : la même chaîne doit être
    utilisée à l'entraînement, sous peine de prédictions faussées sans erreur
    visible.
    """
    started = time.perf_counter()

    raw, image_format = load_image(data)
    original_height, original_width = raw.shape[:2]
    processed = preprocess_array(raw, size)
    tensor = normalize(processed)

    return PreprocessedImage(
        tensor=tensor,
        display=processed,
        image_format=image_format,
        original_size=(original_height, original_width),
        duration_ms=(time.perf_counter() - started) * 1000,
    )


def encode_png(image: np.ndarray) -> bytes:
    """Encode une image 8 bits en PNG, pour l'archivage et l'affichage.

    PNG et non JPEG : la compression avec pertes introduirait des artefacts sur
    une image médicale déjà traitée.
    """
    success, buffer = cv2.imencode(".png", image)
    if not success:
        raise ValueError("Échec de l'encodage PNG.")
    return buffer.tobytes()
