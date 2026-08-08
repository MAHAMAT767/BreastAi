"""Type d'adresse e-mail accepté en entrée par l'API.

## Pourquoi pas `EmailStr`

`EmailStr` de Pydantic refuse les domaines à usage réservé, dont `.local`. Or
c'est précisément ce qu'utilise le réseau interne d'un établissement de soins :
un service qui adresse ses comptes en `medecin@hopital.local` se retrouvait dans
l'impossibilité de créer le moindre utilisateur ou dossier via l'API.

## Ce qui change, et ce qui ne change pas

Seule la restriction sur les TLD réservés listés dans `ALLOWED_RESERVED_DOMAINS`
est levée. Tout le reste de la validation d'`email-validator` reste en vigueur :
absence d'arobase, partie locale vide, domaine vide, domaine sans point,
caractères interdits, arobases multiples — tout cela continue d'être refusé.

Restent également refusés les domaines réservés qui ne désignent pas un réseau
d'entreprise : `test`, `invalid`, `localhost`, `arpa`, `onion`. Ceux-là ne
peuvent pas correspondre à une adresse réelle, et les accepter reviendrait à
laisser entrer des données de test dans un dossier patient.

## Mécanisme

`email-validator` n'expose aucun paramètre par appel pour cela — ni
`allow_special_use_domains`, qui n'existe pas dans la version 2.2, ni
`globally_deliverable=False`, qui ne lève pas cette vérification. Le point
d'extension prévu par la bibliothèque est sa liste de module
`SPECIAL_USE_DOMAIN_NAMES`, que l'on restreint ici une fois pour toutes.
"""

from __future__ import annotations

from typing import Annotated, Final

import email_validator
from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator

#: Domaines réservés désignant un réseau privé, que BreastAI accepte.
ALLOWED_RESERVED_DOMAINS: Final[tuple[str, ...]] = ("local", "internal", "lan")


def _allow_internal_domains() -> None:
    """Retire de la liste de refus les domaines de réseau privé. Idempotent."""
    for name in ALLOWED_RESERVED_DOMAINS:
        if name in email_validator.SPECIAL_USE_DOMAIN_NAMES:
            email_validator.SPECIAL_USE_DOMAIN_NAMES.remove(name)


_allow_internal_domains()


def validate_email_address(value: str) -> str:
    """Valide une adresse et renvoie sa forme normalisée.

    `check_deliverability=False` : aucune résolution DNS. Interroger le DNS à
    chaque création de dossier ajouterait une latence réseau et ferait échouer
    la saisie hors connexion — situation courante hors des grands centres.
    """
    try:
        result = validate_email(value.strip(), check_deliverability=False)
    except EmailNotValidError as exc:
        # Pydantic attend une `ValueError` pour produire un 422 propre.
        raise ValueError(str(exc)) from exc
    return result.normalized


#: À utiliser dans les schémas d'entrée, à la place d'`EmailStr`.
#: Les schémas de **sortie** gardent `str` : revalider une donnée déjà stockée
#: ne protège de rien et transforme le moindre écart en erreur 500.
EmailAddress = Annotated[str, AfterValidator(validate_email_address)]
