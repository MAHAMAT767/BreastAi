"""Fabriques d'images de test.

Les fichiers produits ici sont de vrais PNG, JPEG et DICOM : les tests d'upload
traversent donc le décodage réel, pas un simulacre. Aucune donnée patient
réelle n'est utilisée — les images sont du bruit synthétique.
"""

from __future__ import annotations

import io

import cv2
import numpy as np
import pydicom
from pydicom.dataset import FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian


def _synthetic_breast(height: int, width: int, seed: int = 0) -> np.ndarray:
    """Image grossièrement plausible : fond noir et zone dense plus claire.

    Une image uniforme passerait à côté des étapes de contraste ; ce motif donne
    à CLAHE et au filtre médian quelque chose à traiter.
    """
    rng = np.random.default_rng(seed)
    image = rng.integers(0, 40, size=(height, width), dtype=np.uint16)

    center_y, center_x = height // 2, width // 2
    radius = min(height, width) // 3
    yy, xx = np.ogrid[:height, :width]
    mask = (yy - center_y) ** 2 + (xx - center_x) ** 2 <= radius**2
    image[mask] = rng.integers(600, 3000, size=int(mask.sum()), dtype=np.uint16)

    return image


def make_png_bytes(height: int = 512, width: int = 400, seed: int = 0) -> bytes:
    """PNG 8 bits."""
    image = (_synthetic_breast(height, width, seed) // 16).astype(np.uint8)
    success, buffer = cv2.imencode(".png", image)
    assert success
    return buffer.tobytes()


def make_png16_bytes(height: int = 256, width: int = 256, seed: int = 1) -> bytes:
    """PNG 16 bits — courant en imagerie médicale exportée."""
    image = _synthetic_breast(height, width, seed).astype(np.uint16)
    success, buffer = cv2.imencode(".png", image)
    assert success
    return buffer.tobytes()


def make_jpeg_bytes(height: int = 300, width: int = 300, seed: int = 2) -> bytes:
    image = (_synthetic_breast(height, width, seed) // 16).astype(np.uint8)
    success, buffer = cv2.imencode(".jpg", image)
    assert success
    return buffer.tobytes()


def make_dicom_bytes(
    height: int = 300,
    width: int = 250,
    seed: int = 3,
    photometric: str = "MONOCHROME2",
) -> bytes:
    """DICOM conforme à la partie 10 : préambule de 128 octets puis « DICM »."""
    pixels = _synthetic_breast(height, width, seed).astype(np.uint16)

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1.2"  # mammographie numérique
    meta.MediaStorageSOPInstanceUID = "1.2.826.0.1.3680043.8.498.1"
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = "1.2.826.0.1.3680043.8.498.2"

    dataset = pydicom.Dataset()
    dataset.file_meta = meta
    dataset.PatientName = "ANONYME^TEST"
    dataset.PatientID = "TCD-TEST"
    dataset.Modality = "MG"
    dataset.Rows, dataset.Columns = pixels.shape
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = photometric
    dataset.BitsAllocated = 16
    dataset.BitsStored = 12
    dataset.HighBit = 11
    dataset.PixelRepresentation = 0
    dataset.PixelData = pixels.tobytes()

    buffer = io.BytesIO()
    dataset.save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()


def make_corrupted_png_bytes() -> bytes:
    """Signature PNG valide mais contenu illisible.

    Sert à vérifier que la validation ne s'arrête pas aux octets magiques.
    """
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
