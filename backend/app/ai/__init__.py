"""Modules d'intelligence artificielle de BreastAI.

Pipeline complet :

    Upload → preprocessing → inference (EfficientNet) → explainability (Grad-CAM)
           → services.report_service (PDF) → services.assistant_service (LLM)

Sous-paquets :
    preprocessing/   redimensionnement, normalisation, débruitage, augmentation
    training/        chargement des données, fine-tuning, validation, sauvegarde
    inference/       chargement du modèle, prédiction, score de confiance
    explainability/  Grad-CAM, heatmap, superposition
    evaluation/      accuracy, precision, recall, F1, ROC-AUC, matrice de confusion

Constantes partagées ci-dessous : elles fixent le contrat entre les modules
(taille d'entrée, ordre des classes) et doivent rester cohérentes entre
l'entraînement et l'inférence, sous peine de prédictions silencieusement fausses.
"""

from __future__ import annotations

from typing import Final

#: Taille d'entrée du réseau (hauteur, largeur), en pixels.
IMAGE_SIZE: Final[tuple[int, int]] = (384, 384)

#: Ordre des classes en sortie du modèle. L'index est l'étiquette entière.
CLASS_NAMES: Final[tuple[str, ...]] = ("benign", "malignant")

#: Libellés destinés à l'affichage et aux rapports.
CLASS_LABELS_FR: Final[dict[str, str]] = {
    "benign": "Bénin",
    "malignant": "Malin",
}

#: Moyenne et écart-type ImageNet, utilisés par les poids pré-entraînés.
IMAGENET_MEAN: Final[tuple[float, float, float]] = (0.485, 0.456, 0.406)
IMAGENET_STD: Final[tuple[float, float, float]] = (0.229, 0.224, 0.225)

__all__ = [
    "CLASS_LABELS_FR",
    "CLASS_NAMES",
    "IMAGENET_MEAN",
    "IMAGENET_STD",
    "IMAGE_SIZE",
]
