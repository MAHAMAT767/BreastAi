"""Création du compte administrateur initial.

Usage (après `alembic upgrade head`) :

    cd backend
    FIRST_ADMIN_EMAIL=... FIRST_ADMIN_PASSWORD=... python -m app.database.init_db

Sans compte administrateur, personne ne peut créer d'utilisateur : c'est
l'amorçage de la plateforme. La commande est idempotente.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy.orm import Session

from app.auth.roles import UserRole
from app.config import settings
from app.database.session import session_factory
from app.services import user_service

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("breastai.init_db")


def create_first_admin(db: Session, email: str, password: str, full_name: str) -> bool:
    """Crée l'administrateur s'il n'existe pas. Renvoie True s'il a été créé."""
    if user_service.get_by_email(db, email) is not None:
        logger.info("Le compte %s existe déjà — rien à faire.", email)
        return False

    user_service.create_user(
        db,
        email=email,
        password=password,
        full_name=full_name,
        role=UserRole.ADMIN,
    )
    logger.info("Administrateur créé : %s", email)
    return True


def main() -> int:
    if not settings.first_admin_email or not settings.first_admin_password:
        logger.error(
            "FIRST_ADMIN_EMAIL et FIRST_ADMIN_PASSWORD doivent être définis "
            "dans l'environnement ou dans .env."
        )
        return 1

    with session_factory() as db:
        create_first_admin(
            db,
            settings.first_admin_email,
            settings.first_admin_password,
            settings.first_admin_name,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - point d'entrée CLI
    sys.exit(main())
