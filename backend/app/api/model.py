"""État du modèle actuellement chargé.

À ne pas confondre avec la provenance d'une analyse : cet endpoint décrit le
modèle **en service maintenant**, tandis que chaque `AnalysisRead` porte la
provenance du modèle qui a produit *ce* résultat-là. Les deux divergent dès qu'un
modèle est remplacé, et c'est voulu — les analyses passées gardent leur
avertissement.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.ai.inference.predictor import get_predictor
from app.auth.dependencies import CurrentUser
from app.disclaimer import (
    MEDICAL_DISCLAIMER,
    ModelStatus,
    derive_model_status,
    model_warning_for,
)

router = APIRouter(prefix="/model", tags=["modèle"])


class ModelStatusRead(BaseModel):
    """Ce que l'interface doit savoir pour afficher le bon avertissement."""

    model_version: str
    architecture: str
    class_names: list[str]
    threshold: float
    preprocessing_version: str

    is_placeholder_model: bool = Field(
        description="Le modèle n'a jamais été entraîné sur des mammographies."
    )
    clinically_validated: bool = Field(
        description=(
            "Sa valeur clinique a-t-elle été établie par une revue documentée ? "
            "Question indépendante de la précédente."
        )
    )
    model_status: ModelStatus
    model_warning: str | None = None

    #: Permanent, quel que soit l'état du modèle.
    disclaimer: str = MEDICAL_DISCLAIMER


@router.get("", response_model=ModelStatusRead, summary="État du modèle chargé")
def model_status(user: CurrentUser) -> ModelStatusRead:
    """Décrit le modèle en service, avertissement de provenance compris.

    Ouvert à tous les rôles connectés : aucune donnée de patiente n'y figure, et
    savoir quel modèle tourne intéresse autant le chercheur que le clinicien.
    """
    del user
    bundle = get_predictor().bundle
    status = derive_model_status(bundle.is_placeholder, bundle.clinically_validated)

    return ModelStatusRead(
        model_version=bundle.version,
        architecture=bundle.architecture,
        class_names=list(bundle.class_names),
        threshold=bundle.threshold,
        preprocessing_version=bundle.preprocessing_version,
        is_placeholder_model=bundle.is_placeholder,
        clinically_validated=bundle.clinically_validated,
        model_status=status,
        model_warning=model_warning_for(status),
    )
