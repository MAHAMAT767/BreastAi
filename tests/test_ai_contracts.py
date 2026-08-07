"""Vérifie les constantes partagées entre entraînement et inférence.

Une divergence sur l'ordre des classes ou la taille d'entrée produit des
prédictions fausses sans lever d'erreur — d'où ces tests dès le scaffolding.
"""

from __future__ import annotations

from app.ai import CLASS_LABELS_FR, CLASS_NAMES, IMAGE_SIZE


def test_class_order_is_benign_then_malignant() -> None:
    """L'index 1 doit être la classe maligne : c'est elle dont on lit la probabilité."""
    assert CLASS_NAMES == ("benign", "malignant")
    assert CLASS_NAMES.index("malignant") == 1


def test_every_class_has_a_french_label() -> None:
    assert set(CLASS_LABELS_FR) == set(CLASS_NAMES)


def test_image_size_is_square_and_positive() -> None:
    height, width = IMAGE_SIZE
    assert height == width
    assert height > 0
