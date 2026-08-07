"""Tests de la chaîne de prétraitement des mammographies."""

from __future__ import annotations

import numpy as np
import pytest

from app.ai import IMAGE_SIZE, IMAGENET_MEAN, IMAGENET_STD
from app.ai.preprocessing import (
    ImageFormat,
    ImageLoadError,
    UnsupportedFormatError,
    denoise,
    detect_format,
    encode_png,
    enhance_contrast,
    load_image,
    normalize,
    preprocess_for_inference,
    resize_with_padding,
)
from app.ai.preprocessing.loaders import to_uint8
from tests.factories import (
    make_corrupted_png_bytes,
    make_dicom_bytes,
    make_jpeg2000_dicom_bytes,
    make_jpeg_bytes,
    make_png16_bytes,
    make_png_bytes,
    make_rle_dicom_bytes,
)

# --------------------------------------------------------------------------- #
# Détection de format
# --------------------------------------------------------------------------- #


def test_detects_png() -> None:
    assert detect_format(make_png_bytes()) is ImageFormat.PNG


def test_detects_jpeg() -> None:
    assert detect_format(make_jpeg_bytes()) is ImageFormat.JPEG


def test_detects_dicom() -> None:
    assert detect_format(make_dicom_bytes()) is ImageFormat.DICOM


def test_unknown_content_is_not_detected() -> None:
    assert detect_format(b"ceci est un fichier texte") is None


def test_detection_reads_content_not_extension() -> None:
    """Un exécutable renommé en .png ne doit pas passer la détection."""
    assert detect_format(b"MZ\x90\x00" + b"\x00" * 200) is None


def test_truncated_file_is_not_mistaken_for_dicom() -> None:
    assert detect_format(b"\x00" * 64) is None


# --------------------------------------------------------------------------- #
# Décodage
# --------------------------------------------------------------------------- #


def test_loads_png_as_grayscale() -> None:
    image, image_format = load_image(make_png_bytes(height=120, width=90))

    assert image_format is ImageFormat.PNG
    assert image.ndim == 2
    assert image.shape == (120, 90)
    assert image.dtype == np.uint8


def test_loads_16bit_png_down_to_8bit() -> None:
    """Sans remise à l'échelle, une image 16 bits apparaîtrait presque noire."""
    image, _ = load_image(make_png16_bytes())

    assert image.dtype == np.uint8
    assert image.max() > 200


def test_loads_jpeg() -> None:
    image, image_format = load_image(make_jpeg_bytes())

    assert image_format is ImageFormat.JPEG
    assert image.ndim == 2


def test_loads_dicom() -> None:
    image, image_format = load_image(make_dicom_bytes(height=200, width=150))

    assert image_format is ImageFormat.DICOM
    assert image.shape == (200, 150)
    assert image.dtype == np.uint8


def test_monochrome1_dicom_is_inverted() -> None:
    """En MONOCHROME1, la valeur haute représente le noir : l'image doit être inversée."""
    monochrome2, _ = load_image(make_dicom_bytes(seed=7, photometric="MONOCHROME2"))
    monochrome1, _ = load_image(make_dicom_bytes(seed=7, photometric="MONOCHROME1"))

    # Les deux jeux de pixels sont identiques ; seule l'interprétation diffère.
    assert not np.array_equal(monochrome1, monochrome2)
    assert np.allclose(monochrome1.astype(int) + monochrome2.astype(int), 255, atol=2)


def test_loads_jpeg2000_compressed_dicom() -> None:
    """La plupart des mammographes produisent du JPEG 2000, pas du non compressé."""
    image, image_format = load_image(make_jpeg2000_dicom_bytes(height=200, width=160))

    assert image_format is ImageFormat.DICOM
    assert image.shape == (200, 160)
    assert image.dtype == np.uint8


def test_loads_rle_compressed_dicom() -> None:
    image, image_format = load_image(make_rle_dicom_bytes(height=200, width=160))

    assert image_format is ImageFormat.DICOM
    assert image.shape == (200, 160)


def test_compression_is_lossless_end_to_end() -> None:
    """JPEG 2000 sans perte : le résultat doit être identique au non compressé."""
    uncompressed, _ = load_image(make_dicom_bytes(height=120, width=100, seed=11))
    compressed, _ = load_image(
        make_jpeg2000_dicom_bytes(height=120, width=100, seed=11)
    )

    assert np.array_equal(uncompressed, compressed)


def test_unsupported_format_is_rejected() -> None:
    with pytest.raises(UnsupportedFormatError):
        load_image(b"pas une image du tout")


def test_corrupted_png_is_rejected() -> None:
    """Signature valide mais contenu illisible : la détection ne suffit pas."""
    with pytest.raises(ImageLoadError):
        load_image(make_corrupted_png_bytes())


def test_uniform_image_does_not_divide_by_zero() -> None:
    uniform = np.full((10, 10), 1234, dtype=np.uint16)

    assert to_uint8(uniform).max() == 0


# --------------------------------------------------------------------------- #
# Transformations
# --------------------------------------------------------------------------- #


def test_resize_preserves_aspect_ratio_with_padding() -> None:
    """Déformer l'image changerait la géométrie des lésions."""
    tall = np.full((400, 100), 255, dtype=np.uint8)
    resized = resize_with_padding(tall, (384, 384))

    assert resized.shape == (384, 384)
    # Le contenu occupe une bande centrale ; les bords latéraux sont du remplissage.
    assert resized[:, 0].max() == 0
    assert resized[192, 192] == 255


def test_resize_upscales_small_images() -> None:
    small = np.full((20, 30), 128, dtype=np.uint8)

    assert resize_with_padding(small, (384, 384)).shape == (384, 384)


def test_resize_rejects_empty_image() -> None:
    with pytest.raises(ValueError, match="vide"):
        resize_with_padding(np.zeros((0, 10), dtype=np.uint8))


def test_denoise_keeps_shape_and_type() -> None:
    image = make_png_bytes()
    decoded, _ = load_image(image)
    result = denoise(decoded)

    assert result.shape == decoded.shape
    assert result.dtype == np.uint8


def test_denoise_removes_isolated_speckle() -> None:
    """Le bruit impulsionnel isolé doit disparaître, c'est tout l'intérêt du médian."""
    image = np.full((32, 32), 100, dtype=np.uint8)
    image[16, 16] = 255

    assert denoise(image)[16, 16] == 100


def test_contrast_enhancement_widens_the_histogram() -> None:
    flat = np.random.default_rng(0).integers(100, 130, size=(64, 64), dtype=np.uint8)
    enhanced = enhance_contrast(flat)

    assert enhanced.std() > flat.std()


def test_normalize_produces_three_channels() -> None:
    """EfficientNet attend trois canaux : le canal unique est répliqué."""
    tensor = normalize(np.full((384, 384), 128, dtype=np.uint8))

    assert tensor.shape == (3, 384, 384)
    assert tensor.dtype == np.float32


def test_normalize_applies_imagenet_statistics() -> None:
    tensor = normalize(np.zeros((8, 8), dtype=np.uint8))

    for channel in range(3):
        expected = -IMAGENET_MEAN[channel] / IMAGENET_STD[channel]
        assert tensor[channel].mean() == pytest.approx(expected, abs=1e-5)


# --------------------------------------------------------------------------- #
# Chaîne complète
# --------------------------------------------------------------------------- #


def test_pipeline_on_png() -> None:
    result = preprocess_for_inference(make_png_bytes(height=512, width=400))

    assert result.tensor.shape == (3, *IMAGE_SIZE)
    assert result.display.shape == IMAGE_SIZE
    assert result.original_size == (512, 400)
    assert result.image_format is ImageFormat.PNG
    assert result.duration_ms > 0


def test_pipeline_on_dicom() -> None:
    result = preprocess_for_inference(make_dicom_bytes(height=300, width=250))

    assert result.tensor.shape == (3, *IMAGE_SIZE)
    assert result.original_size == (300, 250)
    assert result.image_format is ImageFormat.DICOM


def test_pipeline_is_deterministic() -> None:
    """Aucune étape aléatoire : deux passages sur la même image donnent le même tenseur."""
    data = make_png_bytes(seed=5)

    first = preprocess_for_inference(data)
    second = preprocess_for_inference(data)

    assert np.array_equal(first.tensor, second.tensor)


def test_pipeline_output_is_stamped_with_a_version() -> None:
    """La version relie une analyse à la chaîne qui l'a produite."""
    assert preprocess_for_inference(make_png_bytes()).version


def test_display_image_can_be_encoded_to_png() -> None:
    result = preprocess_for_inference(make_png_bytes())
    encoded = encode_png(result.display)

    assert detect_format(encoded) is ImageFormat.PNG
