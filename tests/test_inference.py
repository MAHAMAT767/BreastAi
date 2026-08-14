"""Tests du chargement du modèle et de la prédiction."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from app.ai import CLASS_NAMES, IMAGE_SIZE
from app.ai.inference import (
    DEFAULT_ARCHITECTURE,
    PLACEHOLDER_PREFIX,
    ModelLoadError,
    Predictor,
    build_model,
    build_placeholder,
    is_placeholder_version,
    load_bundle,
    load_checkpoint,
    resolve_device,
)
from app.ai.preprocessing import PREPROCESSING_VERSION, preprocess_for_inference
from tests.factories import make_png_bytes

DEVICE = torch.device("cpu")


def valid_checkpoint(**overrides) -> dict:
    """Checkpoint conforme au contrat documenté dans `loader.py`."""
    checkpoint = {
        "architecture": DEFAULT_ARCHITECTURE,
        "class_names": list(CLASS_NAMES),
        "preprocessing_version": PREPROCESSING_VERSION,
        "threshold": 0.5,
        "version": "efficientnet_b0-test-v1",
        "state_dict": build_model(DEFAULT_ARCHITECTURE).state_dict(),
    }
    checkpoint.update(overrides)
    return checkpoint


# --------------------------------------------------------------------------- #
# Construction du réseau
# --------------------------------------------------------------------------- #


def test_head_is_resized_to_the_number_of_classes() -> None:
    model = build_model(DEFAULT_ARCHITECTURE)

    assert model.classifier[-1].out_features == len(CLASS_NAMES)


def test_unknown_architecture_is_refused() -> None:
    with pytest.raises(ModelLoadError, match="Architecture inconnue"):
        build_model("resnet-imaginaire")


def test_cuda_request_falls_back_to_cpu_when_unavailable() -> None:
    if torch.cuda.is_available():
        pytest.skip("CUDA disponible sur cette machine.")

    assert resolve_device("cuda").type == "cpu"


# --------------------------------------------------------------------------- #
# Modèle placeholder
# --------------------------------------------------------------------------- #


def test_placeholder_is_flagged() -> None:
    bundle = build_placeholder(DEVICE)

    assert bundle.is_placeholder is True
    assert bundle.version.startswith(PLACEHOLDER_PREFIX)
    assert is_placeholder_version(bundle.version)


def test_placeholder_is_used_when_no_checkpoint_exists(tmp_path: Path) -> None:
    bundle = load_bundle(tmp_path / "modele-absent.pt")

    assert bundle.is_placeholder is True


def test_placeholder_is_deterministic_across_builds() -> None:
    """Des prédictions qui changeraient à chaque redémarrage seraient pires encore."""
    tensor = preprocess_for_inference(make_png_bytes()).tensor

    first = Predictor(build_placeholder(DEVICE)).predict(tensor)
    second = Predictor(build_placeholder(DEVICE)).predict(tensor)

    assert first.probability == pytest.approx(second.probability, abs=1e-6)
    assert first.label == second.label


def test_trained_model_may_not_claim_the_placeholder_prefix(tmp_path: Path) -> None:
    """Le préfixe est le seul marqueur de provenance : il doit rester fiable."""
    path = tmp_path / "modele.pt"
    torch.save(valid_checkpoint(version=f"{PLACEHOLDER_PREFIX}faux"), path)

    with pytest.raises(ModelLoadError, match="réservé"):
        load_checkpoint(path, DEVICE)


# --------------------------------------------------------------------------- #
# Validation des checkpoints
# --------------------------------------------------------------------------- #


def test_valid_checkpoint_loads(tmp_path: Path) -> None:
    path = tmp_path / "modele.pt"
    torch.save(valid_checkpoint(), path)

    bundle = load_checkpoint(path, DEVICE)

    assert bundle.is_placeholder is False
    assert bundle.version == "efficientnet_b0-test-v1"
    assert bundle.threshold == 0.5


def test_checkpoint_threshold_is_honoured(tmp_path: Path) -> None:
    """Le seuil vient du modèle, pas d'un 0,5 implicite dans le code."""
    path = tmp_path / "modele.pt"
    torch.save(valid_checkpoint(threshold=0.2), path)

    assert load_checkpoint(path, DEVICE).threshold == 0.2


# --------------------------------------------------------------------------- #
# Validation clinique
# --------------------------------------------------------------------------- #


def test_trained_model_is_not_validated_by_default(tmp_path: Path) -> None:
    """Être entraîné ne vaut pas être validé : les deux notions sont disjointes."""
    path = tmp_path / "modele.pt"
    torch.save(valid_checkpoint(), path)  # sans clé `clinically_validated`

    bundle = load_checkpoint(path, DEVICE)

    assert bundle.is_placeholder is False
    assert bundle.clinically_validated is False


def test_placeholder_is_never_clinically_validated() -> None:
    assert build_placeholder(DEVICE).clinically_validated is False


def test_clinically_validated_requires_exactly_true(tmp_path: Path) -> None:
    """Une valeur seulement « vraie au sens de Python » ne suffit pas.

    Un `bool(...)` laisserait la chaîne "false" — ou n'importe quelle valeur non
    vide écrite par erreur dans le checkpoint — déclarer le modèle validé.
    """
    # Un seul fichier, réécrit à chaque tour : un checkpoint pèse une vingtaine
    # de mégaoctets, en écrire cinq d'un coup remplirait le disque pour rien.
    path = tmp_path / "modele.pt"
    for suspicious in ("true", "false", 1, [1], "oui"):
        torch.save(valid_checkpoint(clinically_validated=suspicious), path)

        assert load_checkpoint(path, DEVICE).clinically_validated is False, suspicious


def test_clinically_validated_is_carried_to_the_prediction(tmp_path: Path) -> None:
    """Le drapeau doit survivre jusqu'au résultat : c'est là qu'il est lu."""
    path = tmp_path / "modele.pt"
    torch.save(valid_checkpoint(clinically_validated=True), path)
    tensor = preprocess_for_inference(make_png_bytes()).tensor

    bundle = load_checkpoint(path, DEVICE)
    result = Predictor(bundle).predict(tensor)

    assert bundle.clinically_validated is True
    assert result.clinically_validated is True
    assert result.is_placeholder is False


def test_reversed_class_order_is_refused(tmp_path: Path) -> None:
    """Charger un tel modèle inverserait bénin et malin sans lever d'erreur."""
    path = tmp_path / "modele.pt"
    torch.save(valid_checkpoint(class_names=["malignant", "benign"]), path)

    with pytest.raises(ModelLoadError, match="inverserait"):
        load_checkpoint(path, DEVICE)


def test_mismatched_preprocessing_version_is_refused(tmp_path: Path) -> None:
    """Un modèle entraîné sur un autre prétraitement voit d'autres images."""
    path = tmp_path / "modele.pt"
    torch.save(valid_checkpoint(preprocessing_version="v0"), path)

    with pytest.raises(ModelLoadError, match="prétraitement"):
        load_checkpoint(path, DEVICE)


def test_bare_state_dict_is_refused(tmp_path: Path) -> None:
    """Sans métadonnées, rien ne garantit la compatibilité du modèle."""
    path = tmp_path / "modele.pt"
    torch.save(build_model(DEFAULT_ARCHITECTURE).state_dict(), path)

    with pytest.raises(ModelLoadError):
        load_checkpoint(path, DEVICE)


def test_incompatible_weights_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "modele.pt"
    torch.save(valid_checkpoint(state_dict={"inattendu": torch.zeros(1)}), path)

    with pytest.raises(ModelLoadError):
        load_checkpoint(path, DEVICE)


def test_unreadable_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "modele.pt"
    path.write_bytes(b"ceci n'est pas un checkpoint")

    with pytest.raises(ModelLoadError, match="illisible"):
        load_checkpoint(path, DEVICE)


# --------------------------------------------------------------------------- #
# Prédiction
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def predictor() -> Predictor:
    """Un seul chargement de poids pour tout le module."""
    return Predictor(build_placeholder(DEVICE))


def test_prediction_on_a_real_image(predictor: Predictor) -> None:
    result = predictor.predict(preprocess_for_inference(make_png_bytes()).tensor)

    assert result.label in CLASS_NAMES
    assert 0.0 <= result.probability <= 1.0
    assert 0.0 <= result.confidence <= 1.0
    assert result.inference_time_ms > 0
    assert result.is_placeholder is True


def test_probabilities_sum_to_one(predictor: Predictor) -> None:
    result = predictor.predict(preprocess_for_inference(make_png_bytes()).tensor)

    assert sum(result.probabilities.values()) == pytest.approx(1.0, abs=1e-5)
    assert set(result.probabilities) == set(CLASS_NAMES)


def test_probability_always_refers_to_the_malignant_class(predictor: Predictor) -> None:
    """Point d'ambiguïté classique : c'est cette valeur que lit le médecin."""
    result = predictor.predict(preprocess_for_inference(make_png_bytes()).tensor)

    assert result.probability == pytest.approx(result.probabilities["malignant"], abs=1e-6)


def test_confidence_is_the_probability_of_the_predicted_class(predictor: Predictor) -> None:
    result = predictor.predict(preprocess_for_inference(make_png_bytes()).tensor)

    assert result.confidence == pytest.approx(result.probabilities[result.label], abs=1e-6)


def test_label_follows_the_threshold() -> None:
    """Un seuil très bas doit classer malin ; un seuil de 1 ne le peut jamais."""
    tensor = preprocess_for_inference(make_png_bytes()).tensor

    permissive = build_placeholder(DEVICE)
    object.__setattr__(permissive, "threshold", 0.0)
    strict = build_placeholder(DEVICE)
    object.__setattr__(strict, "threshold", 1.01)

    assert Predictor(permissive).predict(tensor).label == "malignant"
    assert Predictor(strict).predict(tensor).label == "benign"


def test_wrong_tensor_shape_is_refused(predictor: Predictor) -> None:
    with pytest.raises(ValueError, match=r"\(3, H, W\)"):
        predictor.predict(np.zeros((1, *IMAGE_SIZE), dtype=np.float32))
