"""Grad-CAM : localisation des régions ayant motivé la décision du réseau.

Principe : on récupère les cartes d'activation de la dernière couche convolutive
et le gradient du score de la classe visée par rapport à ces cartes. La moyenne
spatiale du gradient donne un poids par canal — l'importance de ce canal pour la
décision. La somme pondérée des cartes, passée par une ReLU, indique les zones
qui **augmentent** le score de la classe.

Implémenté ici plutôt qu'importé : une trentaine de lignes de hooks, contre une
dépendance supplémentaire à suivre dans une chaîne médicale.
"""

from __future__ import annotations

import logging
from types import TracebackType

import cv2
import numpy as np
import torch
from torch import nn
from torch.utils.hooks import RemovableHandle

from app.ai.inference.schemas import SuspiciousRegion

logger = logging.getLogger(__name__)

#: Fraction du maximum au-delà de laquelle un pixel est considéré comme faisant
#: partie de la zone saillante. 0,6 isole le foyer principal sans retenir tout
#: le halo de la carte.
REGION_THRESHOLD: float = 0.6


class GradCAM:
    """Calcule une carte Grad-CAM pour une couche cible.

    S'utilise comme gestionnaire de contexte : les hooks sont retirés à la
    sortie, faute de quoi ils s'accumuleraient sur le modèle partagé à chaque
    analyse et finiraient par retenir en mémoire tous les tenseurs vus.
    """

    def __init__(self, model: nn.Module, target_layer: nn.Module) -> None:
        self.model = model
        self.target_layer = target_layer
        self._activations: torch.Tensor | None = None
        self._gradients: torch.Tensor | None = None
        self._handles: list[RemovableHandle] = []

    def __enter__(self) -> GradCAM:
        self._handles = [
            self.target_layer.register_forward_hook(self._save_activations),
            self.target_layer.register_full_backward_hook(self._save_gradients),
        ]
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()
        self._activations = None
        self._gradients = None

    def _save_activations(self, _module, _inputs, output: torch.Tensor) -> None:
        self._activations = output.detach()

    def _save_gradients(self, _module, _grad_input, grad_output: tuple[torch.Tensor, ...]) -> None:
        self._gradients = grad_output[0].detach()

    def compute(self, batch: torch.Tensor, class_index: int) -> np.ndarray:
        """Carte de chaleur normalisée dans [0, 1], à la résolution de l'entrée.

        Le calcul nécessite les gradients : contrairement à la prédiction, il ne
        peut pas tourner sous `torch.no_grad()`.
        """
        if not self._handles:
            raise RuntimeError("GradCAM doit être utilisé comme gestionnaire de contexte.")

        was_training = self.model.training
        self.model.eval()
        self.model.zero_grad(set_to_none=True)

        with torch.enable_grad():
            logits = self.model(batch)
            score = logits[0, class_index]
            score.backward()

        if was_training:
            self.model.train()

        if self._activations is None or self._gradients is None:
            raise RuntimeError(
                "Aucune activation capturée : la couche cible n'a pas été traversée."
            )

        # Un poids par canal : à quel point ce canal pousse le score vers le haut.
        weights = self._gradients.mean(dim=(2, 3), keepdim=True)
        cam = (weights * self._activations).sum(dim=1, keepdim=True)

        # ReLU : seules les contributions positives intéressent : ce qui augmente
        # le score de la classe, pas ce qui l'abaisse.
        cam = torch.relu(cam)

        cam = torch.nn.functional.interpolate(
            cam, size=batch.shape[-2:], mode="bilinear", align_corners=False
        )
        cam_array = cam[0, 0].cpu().numpy()

        peak = float(cam_array.max())
        if peak <= 0:
            # Aucune activation positive : carte vide plutôt qu'une division par zéro.
            logger.debug("Carte Grad-CAM entièrement nulle.")
            return np.zeros_like(cam_array, dtype=np.float32)

        return (cam_array / peak).astype(np.float32)


def locate_suspicious_region(
    cam: np.ndarray, threshold: float = REGION_THRESHOLD
) -> SuspiciousRegion | None:
    """Rectangle englobant la composante connexe la plus intense de la carte.

    Renvoie `None` si la carte est vide. Le rectangle indique où le modèle a
    regardé, ce qui n'est pas la même chose que l'emplacement d'une lésion.
    """
    peak = float(cam.max())
    if peak <= 0:
        return None

    mask = (cam >= threshold * peak).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    x, y, width, height = cv2.boundingRect(largest)

    return SuspiciousRegion(
        x=int(x), y=int(y), width=int(width), height=int(height), peak_intensity=peak
    )
