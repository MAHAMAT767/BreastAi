"""Inférence : chargement du modèle et prédiction.

    loader.py     — construction du réseau, chargement et validation du checkpoint
    predictor.py  — prédiction, singleton de modèle
    schemas.py    — structures de résultat

Le modèle est chargé une seule fois puis réutilisé. Remplacer le modèle se fait
en déposant un checkpoint dans `MODEL_PATH` : le format attendu et les
vérifications appliquées sont décrits dans la docstring de `loader.py`.

Sans checkpoint, un modèle placeholder à poids ImageNet est chargé. Il n'a jamais
vu de mammographie et ses sorties n'ont aucune valeur clinique ; elles ne servent
qu'à valider la chaîne technique. Tout résultat qu'il produit porte un
`model_version` préfixé par `placeholder-`, ce qui permet de le reconnaître même
longtemps après, sur une analyse déjà enregistrée.
"""

from app.ai.inference.loader import (
    ARCHITECTURES,
    DEFAULT_ARCHITECTURE,
    DEFAULT_THRESHOLD,
    PLACEHOLDER_PREFIX,
    ModelBundle,
    ModelLoadError,
    build_model,
    build_placeholder,
    is_placeholder_version,
    load_bundle,
    load_checkpoint,
    resolve_device,
)
from app.ai.inference.predictor import Predictor, get_predictor, set_predictor
from app.ai.inference.schemas import PredictionResult, SuspiciousRegion

__all__ = [
    "ARCHITECTURES",
    "DEFAULT_ARCHITECTURE",
    "DEFAULT_THRESHOLD",
    "PLACEHOLDER_PREFIX",
    "ModelBundle",
    "ModelLoadError",
    "PredictionResult",
    "Predictor",
    "SuspiciousRegion",
    "build_model",
    "build_placeholder",
    "get_predictor",
    "is_placeholder_version",
    "load_bundle",
    "load_checkpoint",
    "resolve_device",
    "set_predictor",
]
