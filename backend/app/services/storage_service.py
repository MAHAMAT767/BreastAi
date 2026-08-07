"""Stockage des fichiers d'images sur disque.

En production, ce module doit être remplacé par un stockage objet chiffré avec
accès contrôlé : des mammographies sur le disque local d'un conteneur ne sont ni
sauvegardées ni chiffrées au repos.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Final

from app.config import settings

logger = logging.getLogger(__name__)

#: Caractères conservés dans un nom de fichier affiché. Tout le reste est
#: remplacé, ce qui neutralise les séparateurs de chemin et les « .. ».
_SAFE_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9._-]")

MAX_DISPLAY_NAME_LENGTH: Final[int] = 200


def sanitize_filename(filename: str) -> str:
    """Nettoie un nom de fichier fourni par le client, pour l'affichage seul.

    Ce nom n'entre **jamais** dans la construction d'un chemin : les chemins sont
    dérivés d'identifiants UUID générés par le serveur. La désinfection sert à ce
    qu'un nom hostile ne soit pas réaffiché tel quel plus tard.
    """
    name = Path(filename).name  # retire tout composant de répertoire
    cleaned = _SAFE_NAME_PATTERN.sub("_", name).lstrip(".")
    return (cleaned or "sans-nom")[:MAX_DISPLAY_NAME_LENGTH]


def upload_root() -> Path:
    """Racine du stockage, créée si nécessaire."""
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def analysis_directory(patient_id: uuid.UUID, analysis_id: uuid.UUID) -> Path:
    """Dossier d'une analyse : `<racine>/<patient>/<analyse>/`.

    L'arborescence est construite uniquement à partir d'UUID serveur, jamais
    d'une donnée fournie par le client — aucune traversée de chemin possible.
    """
    directory = upload_root() / str(patient_id) / str(analysis_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_bytes(directory: Path, name: str, data: bytes) -> str:
    """Écrit un fichier et renvoie son chemin relatif à la racine de stockage.

    Le chemin stocké en base est relatif : déplacer le volume de stockage ne doit
    pas invalider toutes les analyses déjà enregistrées.
    """
    path = directory / name
    path.write_bytes(data)
    return path.relative_to(upload_root()).as_posix()


def absolute_path(relative_path: str) -> Path:
    """Reconstruit un chemin absolu et vérifie qu'il reste sous la racine."""
    root = upload_root()
    candidate = (root / relative_path).resolve()

    # Garde-fou : même si les chemins sont générés par le serveur, une entrée
    # corrompue en base ne doit pas permettre de lire hors du stockage.
    if not candidate.is_relative_to(root):
        raise ValueError("Chemin de fichier hors du répertoire de stockage.")

    return candidate


def read_bytes(relative_path: str) -> bytes:
    return absolute_path(relative_path).read_bytes()


def exists(relative_path: str) -> bool:
    try:
        return absolute_path(relative_path).is_file()
    except ValueError:
        return False


def delete_analysis_files(patient_id: uuid.UUID, analysis_id: uuid.UUID) -> None:
    """Supprime le dossier d'une analyse. Sans effet s'il n'existe pas."""
    directory = upload_root() / str(patient_id) / str(analysis_id)
    if not directory.is_dir():
        return

    for path in directory.iterdir():
        if path.is_file():
            path.unlink()
    directory.rmdir()
    logger.info("Fichiers de l'analyse %s supprimés.", analysis_id)
