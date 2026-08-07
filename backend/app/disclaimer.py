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
