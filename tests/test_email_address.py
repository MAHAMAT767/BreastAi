"""Tests du type d'adresse e-mail accepté en entrée.

Ce qui est vérifié ici : la restriction sur les domaines de réseau privé est
levée, et **rien d'autre** ne l'est. Un assouplissement qui laisserait aussi
passer une adresse syntaxiquement invalide serait pire que la restriction
d'origine, puisqu'il ferait entrer des données inexploitables dans un dossier
patient sans que personne ne s'en aperçoive.
"""

from __future__ import annotations

import pytest

from app.models.email_address import (
    ALLOWED_RESERVED_DOMAINS,
    validate_email_address,
)

# --------------------------------------------------------------------------- #
# Domaines de réseau privé : acceptés
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("domain", ALLOWED_RESERVED_DOMAINS)
def test_private_network_domains_are_accepted(domain: str) -> None:
    address = f"medecin@hopital.{domain}"

    assert validate_email_address(address) == address


def test_subdomain_of_a_private_network_is_accepted() -> None:
    assert validate_email_address("medecin@radiologie.hopital.local") == (
        "medecin@radiologie.hopital.local"
    )


def test_public_domains_still_work() -> None:
    assert validate_email_address("medecin@hopital.td") == "medecin@hopital.td"


def test_domain_is_normalized_to_lowercase() -> None:
    assert validate_email_address("Medecin@Hopital.LOCAL") == "Medecin@hopital.local"


def test_surrounding_whitespace_is_trimmed() -> None:
    assert validate_email_address("  medecin@hopital.local  ") == "medecin@hopital.local"


# --------------------------------------------------------------------------- #
# Syntaxe : toujours refusée
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "address",
    [
        "pas-un-email",
        "sans-domaine@",
        "@sans-partie-locale.local",
        "espace dans@hopital.local",
        "double@@arobase.local",
        "medecin@hopital",  # domaine sans point
        "",
    ],
)
def test_syntactically_invalid_addresses_are_still_refused(address: str) -> None:
    with pytest.raises(ValueError):
        validate_email_address(address)


# --------------------------------------------------------------------------- #
# Domaines réservés qui restent refusés
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "address",
    [
        "medecin@hopital.test",
        "medecin@hopital.invalid",
        "medecin@localhost",
        "medecin@quelquechose.onion",
    ],
)
def test_non_network_reserved_domains_are_still_refused(address: str) -> None:
    """Ces domaines ne peuvent désigner aucune adresse réelle.

    Les accepter reviendrait à laisser des données de test entrer dans un
    dossier patient.
    """
    with pytest.raises(ValueError):
        validate_email_address(address)
