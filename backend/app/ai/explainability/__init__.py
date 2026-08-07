"""Explicabilité : Grad-CAM et cartes thermiques.

    gradcam.py  — calcul de la carte et localisation de la zone saillante
    heatmap.py  — application de la palette
    overlay.py  — superposition sur l'image prétraitée, encodage PNG

Grad-CAM pondère les cartes d'activation de la dernière couche convolutive par
le gradient du score de la classe prédite, ce qui fait ressortir les régions
ayant motivé la décision.

Limite à rappeler dans l'interface et dans les rapports : la carte indique **où
le modèle a regardé**, pas où se trouve une lésion. Un modèle qui se trompe
produit une carte tout aussi nette qu'un modèle qui a raison. Elle appuie la
lecture du médecin, elle ne la remplace pas et ne la valide pas.
"""

from app.ai.explainability.gradcam import (
    REGION_THRESHOLD,
    GradCAM,
    locate_suspicious_region,
)
from app.ai.explainability.heatmap import to_colormap
from app.ai.explainability.overlay import DEFAULT_ALPHA, encode_png, overlay_heatmap

__all__ = [
    "DEFAULT_ALPHA",
    "REGION_THRESHOLD",
    "GradCAM",
    "encode_png",
    "locate_suspicious_region",
    "overlay_heatmap",
    "to_colormap",
]
