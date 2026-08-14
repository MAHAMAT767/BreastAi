"""Avertissements accompagnant toute sortie du système, source unique.

Module isolé pour éviter un import circulaire : `app.main`, les schémas de
réponse et l'assistant en ont tous besoin.

Ne retirer aucun de ces textes d'une réponse d'analyse, d'un rapport ou d'un
message de l'assistant.
"""

from __future__ import annotations

from typing import Final, Literal

MEDICAL_DISCLAIMER: Final[str] = (
    "BreastAI est un outil d'aide à la décision. Ses résultats ne constituent pas "
    "un diagnostic et ne remplacent pas l'avis d'un professionnel de santé qualifié."
)

#: Accompagne tout résultat produit par le modèle de substitution. Ce texte doit
#: rester explicite au point d'être impossible à prendre pour une nuance de
#: prudence : les valeurs concernées sont du bruit, pas une estimation faible.
PLACEHOLDER_MODEL_WARNING: Final[str] = (
    "⚠️ MODÈLE DE DÉMONSTRATION — AUCUNE VALEUR CLINIQUE. Ce résultat provient "
    "d'un réseau qui n'a jamais été entraîné sur des mammographies : son corps "
    "porte des poids ImageNet et sa tête de classification est initialisée au "
    "hasard. La prédiction, la probabilité et la carte Grad-CAM affichées sont "
    "des valeurs arbitraires, produites uniquement pour valider la chaîne "
    "technique. Elles ne doivent en aucun cas être lues comme un résultat "
    "d'analyse, ni montrées à une patiente."
)

#: Accompagne tout résultat produit par un modèle réellement entraîné mais dont
#: la valeur clinique n'a jamais été établie par une revue documentée. Ce cas est
#: plus dangereux que le placeholder : les sorties y sont plausibles, donc
#: crédibles, sans être pour autant fiables. L'avertissement doit rester aussi
#: visible que celui du placeholder, et non se réduire à une nuance de prudence.
UNVALIDATED_MODEL_WARNING: Final[str] = (
    "⚠️ MODÈLE ENTRAÎNÉ MAIS NON VALIDÉ CLINIQUEMENT — à visée académique et "
    "démonstrative uniquement. Ce modèle a été entraîné sur un jeu de données "
    "restreint et n'a fait l'objet d'aucune validation clinique : ses "
    "performances réelles sur des patientes sont inconnues. Le résultat affiché "
    "ne remplace pas un diagnostic médical et ne doit pas orienter une prise en "
    "charge."
)

#: Rappel joint à toute carte Grad-CAM.
GRADCAM_DISCLAIMER: Final[str] = (
    "La carte de chaleur indique les régions ayant influencé la décision du "
    "modèle, et non l'emplacement d'une lésion. Un modèle qui se trompe produit "
    "une carte tout aussi nette qu'un modèle qui a raison."
)

#: Les trois états de provenance d'un résultat, du moins fiable au plus fiable.
ModelStatus = Literal["placeholder", "trained_unvalidated", "validated"]


def derive_model_status(
    is_placeholder_model: bool, clinically_validated: bool
) -> ModelStatus:
    """Réduit les deux drapeaux à l'état à afficher.

    Fonction unique, appelée partout où l'état est exposé (analyse, rapport,
    assistant, tableau de bord, état du modèle). Dupliquer ce calcul ferait
    dériver les interfaces les unes des autres, et c'est précisément ainsi qu'un
    avertissement finit par manquer à un endroit.

    L'état n'est **jamais** stocké : ni en base, ni dans le checkpoint. Il se
    recalcule à partir des deux booléens, qui sont les seules sources de vérité.
    """
    if is_placeholder_model:
        return "placeholder"
    if not clinically_validated:
        return "trained_unvalidated"
    return "validated"


def model_warning_for(status: ModelStatus) -> str | None:
    """Texte d'avertissement correspondant à l'état, `None` si aucun.

    Un modèle validé ne porte plus d'avertissement de provenance — mais
    `MEDICAL_DISCLAIMER` reste rendu partout, dans tous les cas.
    """
    if status == "placeholder":
        return PLACEHOLDER_MODEL_WARNING
    if status == "trained_unvalidated":
        return UNVALIDATED_MODEL_WARNING
    return None
