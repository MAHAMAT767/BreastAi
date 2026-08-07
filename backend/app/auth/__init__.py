"""Authentification et autorisation.

    roles.py         — rôles applicatifs (admin, doctor, researcher)
    security.py      — hachage bcrypt, émission et validation des jetons JWT
    dependencies.py  — `get_current_user`, `require_roles(...)`

Choix de conception : les jetons sont sans état côté serveur. Un jeton d'accès
embarque l'horodatage du dernier changement de mot de passe, ce qui permet de
révoquer d'un coup toutes les sessions d'un compte en modifiant son mot de passe,
sans maintenir de table de révocation.
"""

from app.auth.roles import ROLE_LABELS_FR, ROLE_VALUES, UserRole

__all__ = ["ROLE_LABELS_FR", "ROLE_VALUES", "UserRole"]
