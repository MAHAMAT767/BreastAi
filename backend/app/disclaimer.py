"""Avertissement médical, source unique pour tout le backend.

Isolé dans son propre module parce qu'il est requis à la fois par l'application
(`app.main`), par les schémas de réponse (`app.models.schemas`) et, en Phase 7,
par l'assistant conversationnel. Le faire vivre dans `app.main` créerait un
import circulaire.

Ce texte accompagne toute sortie du système. Ne pas le retirer d'une réponse
d'analyse, d'un rapport ou d'un message de l'assistant.
"""

from __future__ import annotations

from typing import Final

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

#: Rappel joint à toute carte Grad-CAM.
GRADCAM_DISCLAIMER: Final[str] = (
    "La carte de chaleur indique les régions ayant influencé la décision du "
    "modèle, et non l'emplacement d'une lésion. Un modèle qui se trompe produit "
    "une carte tout aussi nette qu'un modèle qui a raison."
)
