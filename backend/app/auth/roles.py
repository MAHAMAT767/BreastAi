"""Rôles applicatifs et hiérarchie des permissions."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """Rôles d'un compte BreastAI.

    ADMIN       — gestion des comptes, accès à l'ensemble des données.
    DOCTOR      — médecin ou radiologue : patients et analyses, usage clinique.
    RESEARCHER  — accès aux données agrégées et anonymisées, pas aux dossiers nominatifs.
    """

    ADMIN = "admin"
    DOCTOR = "doctor"
    RESEARCHER = "researcher"


#: Valeurs autorisées en base, utilisées par la contrainte CHECK de la table `users`.
ROLE_VALUES: tuple[str, ...] = tuple(role.value for role in UserRole)

#: Libellés d'affichage.
ROLE_LABELS_FR: dict[str, str] = {
    UserRole.ADMIN: "Administrateur",
    UserRole.DOCTOR: "Médecin / Radiologue",
    UserRole.RESEARCHER: "Chercheur",
}
