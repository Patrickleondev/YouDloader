"""Trouve ffmpeg, et sait l'installer lui-même si la machine ne l'a pas.

ffmpeg est indispensable à trois choses : fusionner l'image et le son (YouTube les
sert séparément au-dessus de 360p), convertir l'audio, et découper un extrait.
Plutôt que d'exiger une installation manuelle, l'outil télécharge une build officielle
dans son propre dossier et l'utilise de là. Rien n'est écrit ailleurs sur le système,
donc aucun droit administrateur n'est nécessaire.
"""
from __future__ import annotations

import os
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

# Deux sources officielles, essayées dans l'ordre. La première est plus légère.
SOURCES_WINDOWS = [
    ("gyan.dev (essentials)", "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"),
    ("yt-dlp/FFmpeg-Builds",
     "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"),
]
BINAIRES = ("ffmpeg", "ffprobe")


class EchecInstallation(RuntimeError):
    pass


def dossier_outil() -> Path:
    """Dossier de données de l'application, hors Program Files (pas de droits admin)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or Path.home()
    else:
        base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "YouDloader" / "bin"


def _nom(binaire: str) -> str:
    return binaire + (".exe" if sys.platform == "win32" else "")


def chemin_ffmpeg() -> Path | None:
    """Renvoie le ffmpeg utilisable : celui du système d'abord, puis le nôtre."""
    systeme = shutil.which("ffmpeg")
    if systeme:
        return Path(systeme)
    local = dossier_outil() / _nom("ffmpeg")
    return local if local.exists() else None


def present() -> bool:
    return chemin_ffmpeg() is not None


def emplacement_pour_ytdlp() -> str | None:
    """Valeur de l'option ffmpeg_location : le dossier, pas le fichier."""
    chemin = chemin_ffmpeg()
    return str(chemin.parent) if chemin else None


def installer(progres=None, annulation=None) -> Path:
    """Télécharge et installe ffmpeg dans le dossier de l'outil.

    progres : fonction appelée avec (octets_recus, octets_total, message).
    annulation : objet avec .is_set(), consulté pendant le téléchargement.
    Renvoie le chemin de ffmpeg. Lève EchecInstallation si aucune source ne répond.
    """
    if sys.platform != "win32":
        raise EchecInstallation(
            "Installation automatique prévue pour Windows seulement. "
            "Sur Linux : sudo apt install ffmpeg ; sur macOS : brew install ffmpeg."
        )

    cible = dossier_outil()
    cible.mkdir(parents=True, exist_ok=True)
    erreurs = []

    for nom_source, url in SOURCES_WINDOWS:
        try:
            archive = _telecharger(url, nom_source, progres, annulation)
            try:
                _extraire(archive, cible, progres)
            finally:
                archive.unlink(missing_ok=True)
            ffmpeg = cible / _nom("ffmpeg")
            if not ffmpeg.exists():
                raise EchecInstallation(f"{nom_source} : archive sans ffmpeg exécutable")
            return ffmpeg
        except Exception as erreur:  # on essaie la source suivante
            if annulation is not None and annulation.is_set():
                raise
            erreurs.append(f"{nom_source} : {erreur}")

    raise EchecInstallation("Aucune source n'a abouti.\n" + "\n".join(erreurs))


def _telecharger(url: str, nom_source: str, progres, annulation) -> Path:
    destination = Path(tempfile.gettempdir()) / "youdloader_ffmpeg.zip"
    requete = urllib.request.Request(url, headers={"User-Agent": "YouDloader"})
    with urllib.request.urlopen(requete, timeout=60) as reponse, open(destination, "wb") as sortie:
        total = int(reponse.headers.get("Content-Length") or 0)
        recus = 0
        while True:
            if annulation is not None and annulation.is_set():
                raise EchecInstallation("installation annulée")
            morceau = reponse.read(262144)
            if not morceau:
                break
            sortie.write(morceau)
            recus += len(morceau)
            if progres:
                progres(recus, total, f"Téléchargement de ffmpeg depuis {nom_source}")
    return destination


def _extraire(archive: Path, cible: Path, progres) -> None:
    """Ne sort que ffmpeg et ffprobe : l'archive contient aussi des docs et des exemples."""
    if progres:
        progres(0, 0, "Extraction de ffmpeg")
    voulus = {_nom(b) for b in BINAIRES}
    with zipfile.ZipFile(archive) as zip_:
        for membre in zip_.namelist():
            nom = Path(membre).name
            if nom in voulus and not membre.endswith("/"):
                with zip_.open(membre) as source, open(cible / nom, "wb") as sortie:
                    shutil.copyfileobj(source, sortie)
                chemin = cible / nom
                chemin.chmod(chemin.stat().st_mode | stat.S_IEXEC)
