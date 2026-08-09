"""Prétraitement des mammographies.

Chaîne appliquée à chaque image avant l'inférence :

1. Décodage       — DICOM (pydicom, avec VOI LUT et inversion MONOCHROME1) ou
                    image standard (PNG/JPG via OpenCV)
2. Niveaux de gris
3. Débruitage     — filtre médian 3×3
4. Contraste      — CLAHE (égalisation adaptative à contraste limité)
5. Redimensionnement — vers `app.ai.IMAGE_SIZE`, ratio conservé, fond noir
6. Normalisation  — statistiques ImageNet, 3 canaux répliqués

La même chaîne doit être appliquée à l'entraînement et à l'inférence : c'est le
rôle de `PREPROCESSING_VERSION`, enregistrée avec chaque analyse. L'augmentation
ne concerne que l'entraînement.
"""

from app.ai.preprocessing.loaders import (
    ALLOWED_EXTENSIONS,
    ImageFormat,
    ImageLoadError,
    UnsupportedFormatError,
    detect_format,
    load_image,
)
from app.ai.preprocessing.pipeline import (
    PREPROCESSING_VERSION,
    PreprocessedImage,
    encode_png,
    preprocess_array,
    preprocess_for_inference,
)
from app.ai.preprocessing.transforms import (
    denoise,
    enhance_contrast,
    normalize,
    resize_with_padding,
    to_grayscale,
)

__all__ = [
    "ALLOWED_EXTENSIONS",
    "PREPROCESSING_VERSION",
    "ImageFormat",
    "ImageLoadError",
    "PreprocessedImage",
    "UnsupportedFormatError",
    "denoise",
    "detect_format",
    "encode_png",
    "enhance_contrast",
    "load_image",
    "normalize",
    "preprocess_array",
    "preprocess_for_inference",
    "resize_with_padding",
    "to_grayscale",
]
