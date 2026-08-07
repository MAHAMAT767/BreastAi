"""Prédiction sur une mammographie prétraitée."""

from __future__ import annotations

import logging
import threading
import time

import numpy as np
import torch

from app.ai.inference.loader import ModelBundle, load_bundle
from app.ai.inference.schemas import PredictionResult

logger = logging.getLogger(__name__)

#: Index de la classe maligne dans la sortie du modèle. Verrouillé par
#: `tests/test_ai_contracts.py` : c'est la probabilité que lit le médecin.
MALIGNANT_INDEX = 1


class Predictor:
    """Enveloppe un `ModelBundle` et produit des `PredictionResult`."""

    def __init__(self, bundle: ModelBundle) -> None:
        self.bundle = bundle

    def _to_batch(self, tensor: np.ndarray) -> torch.Tensor:
        """Transforme un tenseur CHW en lot de taille 1 sur le bon périphérique."""
        if tensor.ndim != 3 or tensor.shape[0] != 3:
            raise ValueError(
                f"Tenseur d'entrée attendu en (3, H, W), reçu {tensor.shape}."
            )
        return torch.from_numpy(np.ascontiguousarray(tensor)).unsqueeze(0).to(
            self.bundle.device
        )

    def predict(self, tensor: np.ndarray) -> PredictionResult:
        """Classe une image prétraitée.

        Le seuil de décision vient du modèle, pas d'un 0,5 implicite : en
        dépistage, il se règle sur la sensibilité voulue, un faux négatif coûtant
        bien plus cher qu'un faux positif.
        """
        batch = self._to_batch(tensor)

        started = time.perf_counter()
        with torch.no_grad():
            logits = self.bundle.model(batch)
            probabilities = torch.softmax(logits, dim=1)[0]
        elapsed_ms = (time.perf_counter() - started) * 1000

        scores = {
            name: float(probabilities[index])
            for index, name in enumerate(self.bundle.class_names)
        }
        malignant_probability = float(probabilities[MALIGNANT_INDEX])

        label = (
            self.bundle.class_names[MALIGNANT_INDEX]
            if malignant_probability >= self.bundle.threshold
            else self.bundle.class_names[0]
        )

        return PredictionResult(
            label=label,
            probability=malignant_probability,
            confidence=scores[label],
            inference_time_ms=elapsed_ms,
            model_version=self.bundle.version,
            is_placeholder=self.bundle.is_placeholder,
            threshold=self.bundle.threshold,
            probabilities=scores,
        )


_predictor: Predictor | None = None
_lock = threading.Lock()


def get_predictor() -> Predictor:
    """Instance unique, construite au premier appel.

    Le chargement des poids coûte plusieurs centaines de millisecondes : le faire
    à chaque requête HTTP serait absurde. Le verrou évite que deux requêtes
    concurrentes chargent le modèle deux fois au démarrage.
    """
    global _predictor

    if _predictor is None:
        with _lock:
            if _predictor is None:
                _predictor = Predictor(load_bundle())
    return _predictor


def set_predictor(predictor: Predictor | None) -> None:
    """Remplace l'instance courante.

    Utilisé par les tests et par un rechargement de modèle à chaud ; passer
    `None` force une reconstruction au prochain appel.
    """
    global _predictor

    with _lock:
        _predictor = predictor
