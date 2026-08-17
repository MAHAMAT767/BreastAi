"""Délai de prise en charge suggéré, dérivé de la probabilité déjà calculée.

Module isolé, sur le modèle de `app.disclaimer` : les schémas de réponse et le
service de rapport en ont besoin, et le passer par l'un d'eux créerait un import
circulaire.

## Ce que ce module fait, et ce qu'il ne fait pas

Il n'y a **aucune inférence ici**. La probabilité de malignité est produite une
seule fois, par le modèle, au moment de l'analyse. Ce module ne fait que ranger
cette valeur dans une tranche et y associer une phrase. Aucun appel réseau,
aucun état, aucune lecture en base : une fonction pure sur deux arguments.

## ⚠️ La grille ci-dessous n'est pas validée cliniquement

Les seuils 0,80 / 0,50 / 0,20 et les délais associés sont un **point de départ
technique**, choisi pour donner une structure à l'interface — pas un protocole.
Ils ne proviennent d'aucune recommandation de société savante, d'aucune étude,
d'aucune relecture médicale. Ils n'ont pas été calibrés sur la sensibilité réelle
du modèle, qui n'est elle-même pas établie (voir `DEFAULT_CLINICALLY_VALIDATED`
dans `app.ai.inference.loader`).

**Avant tout usage réel, cette grille doit être relue et arrêtée par un médecin
partenaire** — radiologue ou sénologue — sur trois points au moins :

1. les bornes elles-mêmes, qui dépendent du seuil de décision du modèle et de la
   prévalence dans la population dépistée ;
2. les délais, qui dépendent de ce que le système de soins local peut réellement
   offrir : un « sous 1 à 2 semaines » n'a de sens que si le créneau existe ;
3. le principe même d'afficher un délai — un délai rassurant sur un faux négatif
   est plus nocif que pas de délai du tout.

Tant que cette relecture n'a pas eu lieu, `FOLLOWUP_NOTICE` doit accompagner la
recommandation partout où elle est affichée ou imprimée.

Les constantes sont isolées en tête de fichier précisément pour que cette
révision soit une modification de valeurs, pas une réécriture de logique.
"""

from __future__ import annotations

from typing import Final, Literal

#: Niveaux d'urgence, du plus pressant au moins pressant.
FollowupUrgency = Literal["urgent", "rapproche", "surveillance", "routine"]

# --------------------------------------------------------------------------- #
# Grille — valeurs à faire arrêter par un médecin (voir docstring du module)
# --------------------------------------------------------------------------- #

#: Au-delà : consultation spécialisée à brève échéance.
URGENT_THRESHOLD: Final[float] = 0.80

#: Au-delà : consultation rapprochée. Correspond au seuil de décision par défaut
#: du modèle — c'est la borne au-dessus de laquelle une analyse est classée
#: maligne quand `threshold` vaut 0,5.
CLOSE_FOLLOWUP_THRESHOLD: Final[float] = 0.50

#: Au-delà : surveillance. En deçà, suivi de routine.
SURVEILLANCE_THRESHOLD: Final[float] = 0.20

#: Phrase affichée pour chaque niveau. Rédigées comme des recommandations de
#: délai, jamais comme une prescription : « recommandée », pas « à réaliser ».
FOLLOWUP_LABELS: Final[dict[str, str]] = {
    "urgent": "Consultation spécialisée recommandée sous 1 à 2 semaines",
    "rapproche": "Consultation recommandée sous 4 semaines",
    "surveillance": "Contrôle de suivi recommandé sous 6 mois",
    "routine": "Suivi de routine (prochain contrôle dans 12 mois)",
}

#: Accompagne la recommandation partout où elle apparaît — écran, rapport PDF.
#: Ce n'est pas une formule de prudence décorative : la grille n'est pas validée,
#: et un délai lu sans cette mention se lit comme une consigne médicale.
FOLLOWUP_NOTICE: Final[str] = (
    "Délai indicatif généré automatiquement, non prescriptif — la décision "
    "clinique revient au médecin."
)


def derive_followup_urgency(
    prediction: str | None, probability: float | None
) -> FollowupUrgency | None:
    """Range une probabilité de malignité dans un niveau de suivi.

    Fonction unique, appelée partout où le délai est exposé (analyse, rapport).
    Dupliquer cette règle ferait dériver l'écran et le PDF l'un de l'autre, et
    c'est exactement ainsi qu'un document finirait par annoncer un délai que
    l'application n'affiche pas.

    Renvoie `None` quand il n'y a rien à ranger : analyse en attente, en échec,
    ou dont l'inférence n'a pas abouti. Un délai « par défaut » sur une analyse
    sans résultat serait une affirmation sortie de nulle part.

    `prediction` n'est pas redondant avec `probability`. Le seuil de décision est
    porté par le checkpoint (`ModelBundle.threshold`) et ne vaut pas
    nécessairement 0,5 : un modèle réglé plus bas peut classer « malignant » une
    image à 0,42, que les seules bornes de probabilité rangeraient en simple
    surveillance. Une prédiction maligne ne descend donc jamais sous
    « rapproche ».
    """
    if prediction is None or probability is None:
        return None

    if probability >= URGENT_THRESHOLD:
        return "urgent"
    if probability >= CLOSE_FOLLOWUP_THRESHOLD:
        return "rapproche"

    # Sous 0,50 mais classée maligne : le modèle a un seuil de décision bas. On
    # suit le modèle plutôt que la borne, dans le sens prudent.
    if prediction == "malignant":
        return "rapproche"

    if probability >= SURVEILLANCE_THRESHOLD:
        return "surveillance"
    return "routine"


def followup_label_for(urgency: FollowupUrgency | None) -> str | None:
    """Phrase correspondant au niveau, `None` s'il n'y en a pas."""
    if urgency is None:
        return None
    return FOLLOWUP_LABELS[urgency]
