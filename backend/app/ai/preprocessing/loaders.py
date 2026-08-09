"""Décodage des mammographies : DICOM et images standard."""

from __future__ import annotations

import io
import logging
from enum import StrEnum
from typing import Final

import cv2
import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError
from pydicom.pixels import apply_voi_lut

logger = logging.getLogger(__name__)


class ImageFormat(StrEnum):
    """Formats acceptés à l'import."""

    DICOM = "dicom"
    PNG = "png"
    JPEG = "jpeg"


class ImageLoadError(Exception):
    """Le fichier ne peut pas être décodé en image exploitable."""


class UnsupportedFormatError(ImageLoadError):
    """Le contenu ne correspond à aucun format accepté."""


#: Signatures de début de fichier. Elles sont vérifiées sur le **contenu**, pas
#: sur l'extension : un fichier renommé en .png ne doit pas passer pour une image.
_PNG_SIGNATURE: Final[bytes] = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE: Final[bytes] = b"\xff\xd8\xff"

#: Un fichier DICOM conforme à la partie 10 du standard commence par un préambule
#: de 128 octets suivi de « DICM ».
_DICOM_PREAMBLE_LENGTH: Final[int] = 128
_DICOM_MAGIC: Final[bytes] = b"DICM"

#: Extensions annoncées à l'utilisateur. L'extension ne fait pas foi, mais elle
#: permet de refuser tôt un fichier manifestement hors sujet.
ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".dcm", ".dicom", ".png", ".jpg", ".jpeg"}
)


def detect_format(data: bytes) -> ImageFormat | None:
    """Identifie le format d'après les premiers octets. `None` si non reconnu."""
    if data.startswith(_PNG_SIGNATURE):
        return ImageFormat.PNG
    if data.startswith(_JPEG_SIGNATURE):
        return ImageFormat.JPEG
    if (
        len(data) >= _DICOM_PREAMBLE_LENGTH + len(_DICOM_MAGIC)
        and data[_DICOM_PREAMBLE_LENGTH : _DICOM_PREAMBLE_LENGTH + len(_DICOM_MAGIC)]
        == _DICOM_MAGIC
    ):
        return ImageFormat.DICOM
    return None


def to_uint8(array: np.ndarray) -> np.ndarray:
    """Ramène un tableau d'intensités quelconque sur 0-255.

    Les mammographies DICOM sont couramment codées sur 12 ou 16 bits : sans cette
    remise à l'échelle, l'image apparaîtrait presque noire.
    """
    array = array.astype(np.float32)
    minimum = float(array.min())
    maximum = float(array.max())

    if maximum - minimum < 1e-6:
        # Image uniforme : renvoyer du noir plutôt que de diviser par zéro.
        return np.zeros(array.shape, dtype=np.uint8)

    scaled = (array - minimum) / (maximum - minimum) * 255.0
    return scaled.astype(np.uint8)


def load_dicom(data: bytes) -> np.ndarray:
    """Décode un DICOM en image 2D niveaux de gris sur 8 bits.

    Applique la VOI LUT (fenêtrage) définie par le constructeur : c'est le
    réglage de contraste sous lequel le radiologue est censé lire le cliché.
    Inverse les images MONOCHROME1, où la valeur haute représente le noir.
    """
    try:
        dataset = pydicom.dcmread(io.BytesIO(data))
        pixels = dataset.pixel_array
    except InvalidDicomError as exc:
        raise ImageLoadError("Fichier DICOM invalide.") from exc
    except Exception as exc:  # pydicom lève des types variés selon le défaut
        # Les transfer syntax compressées passent par pylibjpeg : si ce message
        # apparaît, vérifier que les greffons sont installés.
        logger.warning("Échec de décodage DICOM : %s", exc)
        raise ImageLoadError("Impossible de décoder les pixels du fichier DICOM.") from exc

    if pixels.ndim > 2:
        # Série multi-frames : on ne traite que la première image.
        pixels = pixels[0]

    try:
        pixels = apply_voi_lut(pixels, dataset)
    except Exception:  # noqa: BLE001 - LUT absente ou malformée : on garde les pixels bruts
        logger.debug("VOI LUT non applicable, utilisation des pixels bruts.")

    if getattr(dataset, "PhotometricInterpretation", "") == "MONOCHROME1":
        pixels = np.max(pixels) - pixels

    return to_uint8(pixels)


def load_standard_image(data: bytes) -> np.ndarray:
    """Décode un PNG ou JPEG en image 2D niveaux de gris sur 8 bits."""
    buffer = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)

    if image is None:
        raise ImageLoadError("Image illisible ou corrompue.")

    if image.ndim == 3:
        channels = image.shape[2]
        if channels == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        else:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    if image.dtype != np.uint8:
        image = to_uint8(image)

    return image


def load_image(data: bytes) -> tuple[np.ndarray, ImageFormat]:
    """Décode des octets en image 2D niveaux de gris, quel que soit le format.

    Lève `UnsupportedFormatError` si la signature n'est pas reconnue et
    `ImageLoadError` si le décodage échoue.
    """
    image_format = detect_format(data)

    if image_format is None:
        raise UnsupportedFormatError(
            "Format non reconnu. Formats acceptés : DICOM, PNG, JPG, JPEG."
        )

    if image_format is ImageFormat.DICOM:
        return load_dicom(data), image_format

    return load_standard_image(data), image_format
