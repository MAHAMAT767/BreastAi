"""Tests du Grad-CAM et de la superposition."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from app.ai import IMAGE_SIZE
from app.ai.explainability import (
    GradCAM,
    encode_png,
    locate_suspicious_region,
    overlay_heatmap,
    to_colormap,
)
from app.ai.inference import Predictor, build_placeholder
from app.ai.preprocessing import detect_format, preprocess_for_inference
from tests.factories import make_png_bytes

DEVICE = torch.device("cpu")


@pytest.fixture(scope="module")
def bundle():
    """Un seul chargement de poids pour tout le module."""
    return build_placeholder(DEVICE)


@pytest.fixture(scope="module")
def preprocessed():
    return preprocess_for_inference(make_png_bytes(height=600, width=500))


@pytest.fixture(scope="module")
def cam(bundle, preprocessed) -> np.ndarray:
    """Carte Grad-CAM calculée sur une vraie image, via le vrai réseau."""
    batch = torch.from_numpy(preprocessed.tensor).unsqueeze(0)
    with GradCAM(bundle.model, bundle.target_layer) as gradcam:
        return gradcam.compute(batch, class_index=1)


# --------------------------------------------------------------------------- #
# Carte
# --------------------------------------------------------------------------- #


def test_cam_matches_the_input_resolution(cam: np.ndarray) -> None:
    assert cam.shape == IMAGE_SIZE


def test_cam_is_normalized(cam: np.ndarray) -> None:
    assert cam.min() >= 0.0
    assert cam.max() == pytest.approx(1.0, abs=1e-5)


def test_cam_is_not_uniform(cam: np.ndarray) -> None:
    """Une carte plate ne localiserait rien et n'expliquerait rien."""
    assert cam.std() > 0.01


def test_cam_is_deterministic(bundle, preprocessed) -> None:
    batch = torch.from_numpy(preprocessed.tensor).unsqueeze(0)

    with GradCAM(bundle.model, bundle.target_layer) as gradcam:
        first = gradcam.compute(batch, class_index=1)
    with GradCAM(bundle.model, bundle.target_layer) as gradcam:
        second = gradcam.compute(batch, class_index=1)

    assert np.allclose(first, second, atol=1e-6)


def test_different_classes_give_different_maps(bundle, preprocessed) -> None:
    """Grad-CAM est spécifique à une classe : sinon il n'explique aucune décision."""
    batch = torch.from_numpy(preprocessed.tensor).unsqueeze(0)

    with GradCAM(bundle.model, bundle.target_layer) as gradcam:
        benign = gradcam.compute(batch, class_index=0)
    with GradCAM(bundle.model, bundle.target_layer) as gradcam:
        malignant = gradcam.compute(batch, class_index=1)

    assert not np.allclose(benign, malignant, atol=1e-3)


def test_hooks_are_removed_after_use(bundle, preprocessed) -> None:
    """Sans retrait, les hooks s'accumuleraient sur le modèle partagé à chaque analyse."""
    layer = bundle.target_layer
    before = len(layer._forward_hooks) + len(layer._backward_hooks)

    batch = torch.from_numpy(preprocessed.tensor).unsqueeze(0)
    with GradCAM(bundle.model, layer) as gradcam:
        during = len(layer._forward_hooks) + len(layer._backward_hooks)
        gradcam.compute(batch, class_index=1)

    after = len(layer._forward_hooks) + len(layer._backward_hooks)
    assert during > before
    assert after == before


def test_compute_outside_context_is_refused(bundle, preprocessed) -> None:
    gradcam = GradCAM(bundle.model, bundle.target_layer)
    batch = torch.from_numpy(preprocessed.tensor).unsqueeze(0)

    with pytest.raises(RuntimeError, match="gestionnaire de contexte"):
        gradcam.compute(batch, class_index=1)


def test_model_returns_to_eval_mode(bundle, preprocessed) -> None:
    """Le modèle est partagé : le laisser en mode entraînement fausserait la suite."""
    batch = torch.from_numpy(preprocessed.tensor).unsqueeze(0)

    with GradCAM(bundle.model, bundle.target_layer) as gradcam:
        gradcam.compute(batch, class_index=1)

    assert bundle.model.training is False


def test_prediction_still_works_after_gradcam(bundle, preprocessed) -> None:
    """Le passage arrière ne doit pas laisser le modèle dans un état dégradé."""
    predictor = Predictor(bundle)
    before = predictor.predict(preprocessed.tensor)

    batch = torch.from_numpy(preprocessed.tensor).unsqueeze(0)
    with GradCAM(bundle.model, bundle.target_layer) as gradcam:
        gradcam.compute(batch, class_index=1)

    after = predictor.predict(preprocessed.tensor)
    assert after.probability == pytest.approx(before.probability, abs=1e-5)


# --------------------------------------------------------------------------- #
# Localisation
# --------------------------------------------------------------------------- #


def test_region_is_located_inside_the_image(cam: np.ndarray) -> None:
    region = locate_suspicious_region(cam)

    assert region is not None
    assert 0 <= region.x < IMAGE_SIZE[1]
    assert 0 <= region.y < IMAGE_SIZE[0]
    assert region.x + region.width <= IMAGE_SIZE[1]
    assert region.y + region.height <= IMAGE_SIZE[0]


def test_region_follows_the_activation_peak() -> None:
    """Sur une carte artificielle, le rectangle doit entourer le foyer."""
    synthetic = np.zeros((100, 100), dtype=np.float32)
    synthetic[30:50, 60:80] = 1.0

    region = locate_suspicious_region(synthetic)

    assert region is not None
    assert region.x == 60
    assert region.y == 30
    assert region.width == 20
    assert region.height == 20


def test_empty_map_has_no_region() -> None:
    assert locate_suspicious_region(np.zeros((64, 64), dtype=np.float32)) is None


# --------------------------------------------------------------------------- #
# Rendu
# --------------------------------------------------------------------------- #


def test_colormap_produces_three_channels(cam: np.ndarray) -> None:
    colored = to_colormap(cam)

    assert colored.shape == (*IMAGE_SIZE, 3)
    assert colored.dtype == np.uint8


def test_overlay_keeps_the_background_visible(cam: np.ndarray, preprocessed) -> None:
    """Une carte trop opaque empêcherait le médecin de juger du tissu en dessous."""
    blended = overlay_heatmap(preprocessed.display, cam)
    saturated = to_colormap(cam)

    assert blended.shape == (*IMAGE_SIZE, 3)
    assert not np.array_equal(blended, saturated)


def test_overlay_draws_the_region_when_provided(cam: np.ndarray, preprocessed) -> None:
    region = locate_suspicious_region(cam)
    without = overlay_heatmap(preprocessed.display, cam)
    with_region = overlay_heatmap(preprocessed.display, cam, region=region)

    assert not np.array_equal(without, with_region)


def test_overlay_refuses_a_colour_background(cam: np.ndarray) -> None:
    with pytest.raises(ValueError, match="niveaux de gris"):
        overlay_heatmap(np.zeros((*IMAGE_SIZE, 3), dtype=np.uint8), cam)


def test_overlay_resizes_a_mismatched_map(preprocessed) -> None:
    small = np.random.default_rng(0).random((48, 48)).astype(np.float32)

    assert overlay_heatmap(preprocessed.display, small).shape == (*IMAGE_SIZE, 3)


def test_overlay_encodes_to_png(cam: np.ndarray, preprocessed) -> None:
    encoded = encode_png(overlay_heatmap(preprocessed.display, cam))

    assert detect_format(encoded) is not None
