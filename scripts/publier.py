"""Prépare et publie une version de YouDloader.

    python scripts/publier.py                 construit et prépare, sans rien publier
    python scripts/publier.py --publier       publie aussi la release sur GitHub

Étapes : vérifier que l'arbre git est propre, construire l'exe, calculer son empreinte,
poser l'étiquette de version, puis créer la release et y joindre l'exe.

La publication passe par `gh`, pas par GitHub Actions : le compte est bloqué côté
facturation depuis septembre 2026, donc aucun workflow ne démarre. Le fichier
.github/workflows/exe.yml fera le même travail automatiquement le jour où ce sera réglé.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from youdloader import __version__  # noqa: E402

EXE = RACINE / "dist" / "YouDloader.exe"
EMPREINTES = RACINE / "dist" / "SHA256SUMS.txt"


def executer(*commande: str, verifier: bool = True) -> subprocess.CompletedProcess:
    print(">", " ".join(commande))
    resultat = subprocess.run(commande, cwd=RACINE, text=True, capture_output=True)
    if resultat.stdout.strip():
        print(resultat.stdout.strip())
    if verifier and resultat.returncode != 0:
        print(resultat.stderr.strip(), file=sys.stderr)
        raise SystemExit(f"échec : {' '.join(commande)}")
    return resultat


def verifier_arbre_propre() -> None:
    modifies = executer("git", "status", "--porcelain").stdout.strip()
    if modifies:
        raise SystemExit("Des fichiers ne sont pas commités. Commite avant de publier :\n"
                         + modifies)


def empreinte(fichier: Path) -> str:
    condense = hashlib.sha256()
    with open(fichier, "rb") as source:
        for morceau in iter(lambda: source.read(1024 * 1024), b""):
            condense.update(morceau)
    return condense.hexdigest()


def construire() -> None:
    code = subprocess.call([sys.executable, str(RACINE / "build_exe.py")], cwd=RACINE)
    if code != 0 or not EXE.exists():
        raise SystemExit("la construction de l'exe a échoué")
    EMPREINTES.write_text(f"{empreinte(EXE)}  {EXE.name}\n", encoding="utf-8")
    print(f"\n{EXE.name} : {EXE.stat().st_size / 1e6:.1f} Mo")
    print(EMPREINTES.read_text(encoding="utf-8").strip())


def etiqueter(etiquette: str) -> None:
    deja = executer("git", "tag", "--list", etiquette).stdout.strip()
    if deja:
        print(f"étiquette {etiquette} déjà posée")
        return
    executer("git", "tag", "-a", etiquette, "-m", f"YouDloader {__version__}")
    print(f"étiquette {etiquette} posée. Elle n'est pas encore poussée.")


def publier(etiquette: str) -> None:
    if shutil.which("gh") is None:
        raise SystemExit("gh est introuvable : installe GitHub CLI, puis `gh auth login`")
    if executer("gh", "auth", "status", verifier=False).returncode != 0:
        raise SystemExit("pas connecté à GitHub : lance `gh auth login`")

    executer("git", "push", "origin", "main")
    executer("git", "push", "origin", etiquette)
    notes = (
        f"## YouDloader {__version__}\n\n"
        "### Installation\n\n"
        f"Télécharger `YouDloader.exe` ci-dessous et le lancer. Rien à installer.\n"
        "Windows affiche un avertissement SmartScreen parce que l'exécutable n'est pas\n"
        "signé : *Informations complémentaires* puis *Exécuter quand même*.\n\n"
        "ffmpeg n'est pas inclus. S'il manque sur la machine, l'application propose de\n"
        "le télécharger elle-même dans son propre dossier.\n\n"
        "### Empreinte\n\n```\n"
        + EMPREINTES.read_text(encoding="utf-8").strip() + "\n```\n"
    )
    executer("gh", "release", "create", etiquette, str(EXE), str(EMPREINTES),
             "--title", f"YouDloader {__version__}", "--notes", notes)
    print(f"\nPublié : release {etiquette}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--publier", action="store_true", help="pousse et crée la release GitHub")
    p.add_argument("--sans-construire", action="store_true", help="réutilise l'exe déjà construit")
    args = p.parse_args()

    etiquette = f"v{__version__}"
    print(f"Version : {__version__}  (étiquette {etiquette})\n")

    verifier_arbre_propre()
    if not args.sans_construire:
        construire()
    elif not EXE.exists():
        raise SystemExit("aucun exe dans dist/ : relance sans --sans-construire")
    etiqueter(etiquette)

    if args.publier:
        publier(etiquette)
    else:
        print("\nRien n'a été publié. Pour publier :\n"
              "  python scripts/publier.py --publier --sans-construire")


if __name__ == "__main__":
    main()
