"""Construction et chargement du modèle de classification.

Ce module est le point de remplacement du modèle. Poser un checkpoint fine-tuné
dans `MODEL_PATH` suffit : ni `predictor.py`, ni les services, ni l'API ne
changent. En l'absence de checkpoint, un modèle **placeholder** est construit —
voir l'avertissement en tête de `build_placeholder`.

## Format de checkpoint attendu

    torch.save(
        {
            "architecture": "efficientnet_b0",
            "class_names": ["benign", "malignant"],
            "preprocessing_version": "v1",
            "threshold": 0.5,
            "version": "efficientnet_b0-cbis-ddsm-v1",
            "state_dict": model.state_dict(),
        },
        "models/breastai_efficientnet.pt",
    )

Les métadonnées ne sont pas décoratives : elles sont **vérifiées** au chargement
et un écart fait échouer le démarrage plutôt que de produire des prédictions
silencieusement fausses. Un modèle entraîné sur un autre prétraitement, ou dont
l'ordre des classes diffère, donnerait des résultats inversés sans lever la
moindre erreur.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import torch
from torch import nn
from torchvision.models import (
    EfficientNet_B0_Weights,
    EfficientNet_B3_Weights,
    efficientnet_b0,
    efficientnet_b3,
)

from app.ai import CLASS_NAMES
from app.ai.preprocessing import PREPROCESSING_VERSION
from app.config import settings

logger = logging.getLogger(__name__)

#: Architectures reconnues : fabrique et poids ImageNet associés.
ARCHITECTURES: Final[dict[str, tuple[Callable[..., nn.Module], Any]]] = {
    "efficientnet_b0": (efficientnet_b0, EfficientNet_B0_Weights.IMAGENET1K_V1),
    "efficientnet_b3": (efficientnet_b3, EfficientNet_B3_Weights.IMAGENET1K_V1),
}

DEFAULT_ARCHITECTURE: Final[str] = "efficientnet_b0"

#: Tout `model_version` commençant par ce préfixe désigne un modèle non
#: exploitable cliniquement. L'API s'en sert pour marquer ses réponses.
PLACEHOLDER_PREFIX: Final[str] = "placeholder-"

#: Graine de la tête de classification du placeholder. Fixée pour que deux
#: démarrages successifs donnent la même sortie sur la même image : des
#: prédictions qui changeraient à chaque redémarrage seraient encore plus
#: trompeuses que des prédictions constantes et fausses.
PLACEHOLDER_SEED: Final[int] = 20260807

DEFAULT_THRESHOLD: Final[float] = 0.5


class ModelLoadError(Exception):
    """Le checkpoint est illisible ou incompatible avec cette version du code."""


def is_placeholder_version(model_version: str | None) -> bool:
    """Un résultat produit par un modèle placeholder reste reconnaissable après coup."""
    return bool(model_version) and model_version.startswith(PLACEHOLDER_PREFIX)


@dataclass(frozen=True)
class ModelBundle:
    """Modèle chargé et tout ce qu'il faut savoir pour l'utiliser correctement."""

    model: nn.Module
    architecture: str
    version: str
    is_placeholder: bool
    device: torch.device
    class_names: tuple[str, ...]
    threshold: float
    preprocessing_version: str

    @property
    def target_layer(self) -> nn.Module:
        """Dernière couche convolutive, cible du Grad-CAM.

        Pour les EfficientNet de torchvision, `features[-1]` est le bloc
        convolutif final : c'est là que les cartes d'activation conservent
        encore une résolution spatiale exploitable.
        """
        return self.model.features[-1]


def build_model(
    architecture: str = DEFAULT_ARCHITECTURE,
    *,
    pretrained: bool = False,
    num_classes: int = len(CLASS_NAMES),
) -> nn.Module:
    """Construit le réseau et remplace sa tête par une sortie à `num_classes`."""
    if architecture not in ARCHITECTURES:
        raise ModelLoadError(
            f"Architecture inconnue : {architecture!r}. "
            f"Attendu parmi {sorted(ARCHITECTURES)}."
        )

    factory, weights = ARCHITECTURES[architecture]
    model = factory(weights=weights if pretrained else None)

    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model


def build_placeholder(device: torch.device) -> ModelBundle:
    """Modèle de substitution, en attendant un entraînement sur données annotées.

    ⚠️ Ce modèle n'a **jamais vu de mammographie**. Son corps porte des poids
    ImageNet (chats, voitures, champignons) et sa tête de classification est
    initialisée au hasard. Ses sorties sont du bruit reproductible : elles
    permettent de valider la chaîne technique de bout en bout, et rien d'autre.
    Aucune décision clinique ne doit s'y appuyer.
    """
    generator = torch.Generator().manual_seed(PLACEHOLDER_SEED)

    model = build_model(DEFAULT_ARCHITECTURE, pretrained=True)
    head = model.classifier[-1]
    with torch.no_grad():
        # Initialisation déterministe de la tête, seule partie non pré-entraînée.
        head.weight.copy_(
            torch.empty_like(head.weight).normal_(0.0, 0.01, generator=generator)
        )
        head.bias.zero_()

    model.to(device).eval()

    logger.warning(
        "Aucun checkpoint entraîné dans %s : modèle PLACEHOLDER chargé. "
        "Les prédictions produites n'ont aucune valeur clinique.",
        settings.model_path,
    )

    return ModelBundle(
        model=model,
        architecture=DEFAULT_ARCHITECTURE,
        version=f"{PLACEHOLDER_PREFIX}{DEFAULT_ARCHITECTURE}-imagenet",
        is_placeholder=True,
        device=device,
        class_names=CLASS_NAMES,
        threshold=DEFAULT_THRESHOLD,
        preprocessing_version=PREPROCESSING_VERSION,
    )


def _validate_checkpoint(checkpoint: dict[str, Any], path: Path) -> None:
    """Refuse un checkpoint dont le contrat diffère de celui du code courant."""
    if "state_dict" not in checkpoint:
        raise ModelLoadError(f"{path} : clé 'state_dict' absente du checkpoint.")

    class_names = tuple(checkpoint.get("class_names", ()))
    if class_names != CLASS_NAMES:
        raise ModelLoadError(
            f"{path} : ordre des classes {class_names} incompatible avec "
            f"{CLASS_NAMES}. Charger ce modèle inverserait les prédictions."
        )

    checkpoint_preprocessing = checkpoint.get("preprocessing_version")
    if checkpoint_preprocessing != PREPROCESSING_VERSION:
        raise ModelLoadError(
            f"{path} : modèle entraîné avec le prétraitement "
            f"{checkpoint_preprocessing!r}, alors que le code applique "
            f"{PREPROCESSING_VERSION!r}. Les images ne seraient pas préparées "
            "comme à l'entraînement."
        )


def load_checkpoint(path: Path, device: torch.device) -> ModelBundle:
    """Charge un modèle entraîné et vérifie sa compatibilité."""
    try:
        # `weights_only=False` est nécessaire pour relire les métadonnées jointes
        # au state_dict. Cela désérialise du pickle : ne charger que des
        # checkpoints dont on maîtrise l'origine — un fichier .pt hostile exécute
        # du code arbitraire au chargement.
        checkpoint = torch.load(path, map_location=device, weights_only=False)
    except Exception as exc:
        raise ModelLoadError(f"{path} : checkpoint illisible ({exc}).") from exc

    if not isinstance(checkpoint, dict):
        raise ModelLoadError(
            f"{path} : format inattendu. Un dictionnaire de métadonnées est "
            "attendu, pas un state_dict nu — voir la docstring du module."
        )

    _validate_checkpoint(checkpoint, path)

    architecture = checkpoint.get("architecture", DEFAULT_ARCHITECTURE)
    model = build_model(architecture)

    try:
        model.load_state_dict(checkpoint["state_dict"], strict=True)
    except RuntimeError as exc:
        raise ModelLoadError(f"{path} : poids incompatibles avec {architecture} ({exc}).") from exc

    model.to(device).eval()

    version = checkpoint.get("version", path.stem)
    if is_placeholder_version(version):
        raise ModelLoadError(
            f"{path} : le préfixe {PLACEHOLDER_PREFIX!r} est réservé aux modèles "
            "de substitution et ne peut pas nommer un modèle entraîné."
        )

    logger.info("Modèle %s chargé depuis %s (%s).", version, path, architecture)

    return ModelBundle(
        model=model,
        architecture=architecture,
        version=version,
        is_placeholder=False,
        device=device,
        class_names=CLASS_NAMES,
        threshold=float(checkpoint.get("threshold", DEFAULT_THRESHOLD)),
        preprocessing_version=PREPROCESSING_VERSION,
    )


def resolve_device(name: str | None = None) -> torch.device:
    """Choisit le périphérique, en retombant sur le CPU si CUDA est absent."""
    requested = (name or settings.model_device).lower()
    if requested.startswith("cuda") and not torch.cuda.is_available():
        logger.warning("CUDA demandé mais indisponible : bascule sur CPU.")
        return torch.device("cpu")
    return torch.device(requested)


def load_bundle(model_path: str | Path | None = None) -> ModelBundle:
    """Charge le modèle à utiliser : le checkpoint s'il existe, sinon le placeholder."""
    device = resolve_device()
    path = Path(model_path or settings.model_path)

    if not path.is_file():
        return build_placeholder(device)

    return load_checkpoint(path, device)
