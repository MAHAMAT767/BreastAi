"""Structures de résultat de l'inférence, indépendantes de FastAPI et de la base."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PredictionResult:
    """Sortie du modèle pour une mammographie.

    `probability` est toujours celle de la classe **maligne**, quelle que soit la
    classe prédite : c'est elle que lit le médecin, et l'ambiguïté sur ce point
    est une source classique d'erreur d'interprétation.
    """

    label: str
    probability: float
    confidence: float
    inference_time_ms: float
    model_version: str
    is_placeholder: bool
    threshold: float
    probabilities: dict[str, float] = field(default_factory=dict)
    #: Provenance clinique du modèle ayant produit ce résultat, indépendante de
    #: `is_placeholder`. Le défaut est `False` : un résultat dont on ignore la
    #: provenance est traité comme non validé.
    clinically_validated: bool = False


@dataclass(frozen=True, slots=True)
class SuspiciousRegion:
    """Rectangle englobant la zone la plus activée de la carte Grad-CAM.

    Coordonnées en pixels dans l'image prétraitée (384×384), pas dans l'image
    d'origine : c'est le repère dans lequel le modèle a travaillé.

    Ce rectangle indique **où le modèle a regardé**, pas où se trouve une lésion.
    """

    x: int
    y: int
    width: int
    height: int
    peak_intensity: float
