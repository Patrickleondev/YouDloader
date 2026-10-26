"""Fabrique YouDloader.exe avec PyInstaller.

    venv\\Scripts\\python build_exe.py            exe d'un seul fichier
    venv\\Scripts\\python build_exe.py --dossier  dossier (démarrage plus rapide)

ffmpeg n'est volontairement pas embarqué : l'exe pèse ainsi une trentaine de Mo et
l'application télécharge ffmpeg au premier besoin, dans son propre dossier.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
NOM = "YouDloader"


def construire(un_fichier: bool = True) -> int:
    separateur = ";" if sys.platform == "win32" else ":"
    commande = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile" if un_fichier else "--onedir",
        "--windowed",                     # pas de fenêtre console derrière l'interface
        "--name", NOM,
        "--icon", str(RACINE / "assets" / "youdloader.ico"),
        "--add-data", f"{RACINE / 'assets'}{separateur}assets",
        # yt-dlp charge ses extracteurs dynamiquement : PyInstaller ne les voit pas tous.
        "--collect-submodules", "yt_dlp",
        "--collect-data", "yt_dlp",
        str(RACINE / "bureau.py"),
    ]
    print(" ".join(commande))
    return subprocess.call(commande, cwd=RACINE)


if __name__ == "__main__":
    if shutil.which("pyinstaller") is None and not (RACINE / "venv").exists():
        print("Installe d'abord les dépendances : pip install -r requirements.txt")
    code = construire(un_fichier="--dossier" not in sys.argv)
    if code == 0:
        cible = RACINE / "dist" / (f"{NOM}.exe" if "--dossier" not in sys.argv else NOM)
        print(f"\nPrêt : {cible}")
    raise SystemExit(code)
