"""Trouve Node, et sait l'installer lui-même si la machine ne l'a pas.

YouTube protège ses flux par du JavaScript que yt-dlp doit exécuter. Sans moteur
JavaScript, yt-dlp n'obtient qu'une partie des formats : certaines qualités
disparaissent, d'autres liens échouent. yt-dlp accepte Deno, Node, Bun ou QuickJS ;
on installe Node (version 22 au moins, exigée par yt-dlp), seul node.exe est gardé.
Même dossier et même principe que ffmpeg : rien n'est écrit ailleurs sur le système.
"""
from __future__ import annotations

import functools
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from .ffmpeg_auto import EchecInstallation, dossier_outil, extraire, telecharger_archive

VERSION_MINIMALE = 22
INDEX = "https://nodejs.org/dist/index.json"


def _nom() -> str:
    return "node.exe" if sys.platform == "win32" else "node"


@functools.lru_cache(maxsize=None)
def _version(chemin: str) -> int | None:
    """Version majeure de ce node, ou None s'il ne répond pas."""
    try:
        # CREATE_NO_WINDOW : sinon l'exe sans console fait clignoter une fenêtre noire.
        sortie = subprocess.run([chemin, "--version"], capture_output=True, text=True, timeout=10,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    trouve = re.match(r"v(\d+)", sortie.strip())
    return int(trouve.group(1)) if trouve else None


def chemin_node() -> Path | None:
    """Renvoie le node utilisable : celui du système s'il est assez récent, puis le nôtre."""
    for candidat in (shutil.which("node"), dossier_outil() / _nom()):
        if candidat and Path(candidat).exists():
            version = _version(str(candidat))
            if version is not None and version >= VERSION_MINIMALE:
                return Path(candidat)
    return None


def present() -> bool:
    return chemin_node() is not None


def options_ytdlp() -> dict:
    """Valeur de l'option js_runtimes de yt-dlp.

    Deno reste activé : s'il est installé sur la machine, yt-dlp le trouve tout seul.
    """
    moteurs = {"deno": {}}
    chemin = chemin_node()
    if chemin:
        moteurs["node"] = {"path": str(chemin)}
    return moteurs


def _derniere_lts() -> str:
    """Numéro de la dernière version LTS (support long), lu dans l'index officiel."""
    requete = urllib.request.Request(INDEX, headers={"User-Agent": "YouDloader"})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        versions = json.load(reponse)
    for v in versions:
        if v.get("lts") and "win-x64-zip" in v.get("files", []):
            return v["version"]
    raise EchecInstallation("aucune version LTS de Node pour Windows dans l'index")


def installer(progres=None, annulation=None) -> Path:
    """Télécharge et installe node.exe dans le dossier de l'outil (36 Mo à télécharger).

    Mêmes paramètres et même exception que ffmpeg_auto.installer.
    """
    if sys.platform != "win32":
        raise EchecInstallation(
            "Installation automatique prévue pour Windows seulement. "
            "Sur Linux : sudo apt install nodejs ; sur macOS : brew install node."
        )

    cible = dossier_outil()
    cible.mkdir(parents=True, exist_ok=True)
    try:
        version = _derniere_lts()
        url = f"https://nodejs.org/dist/{version}/node-{version}-win-x64.zip"
        archive = telecharger_archive(url, f"nodejs.org ({version})", progres, annulation,
                                      "youdloader_node.zip")
        try:
            extraire(archive, cible, {_nom()}, progres, "Node")
        finally:
            archive.unlink(missing_ok=True)
    except EchecInstallation:
        raise
    except Exception as erreur:
        raise EchecInstallation(f"nodejs.org : {erreur}") from erreur

    node = cible / _nom()
    if not node.exists():
        raise EchecInstallation("archive de Node sans node.exe")
    _version.cache_clear()
    return node
