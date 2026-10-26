"""YouDloader en ligne de commande, sur le même moteur que l'interface graphique.

Exemples :
    python -m youdloader.cli URL
    python -m youdloader.cli URL_PLAYLIST -q 480 -n
    python -m youdloader.cli URL --audio --format mp3
    python -m youdloader.cli URL --de 20 --a 40        (de la 20e à la 40e minute)
    python -m youdloader.cli -f liens.txt -o "D:\\Cours"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import core, ffmpeg_auto


def analyser_arguments(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="youdloader", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("urls", nargs="*", help="vidéos, playlists ou chaînes")
    p.add_argument("-f", "--fichier", type=Path, help="fichier texte, une URL par ligne")
    p.add_argument("-o", "--sortie", type=Path, default=Path("telechargements"))
    p.add_argument("-q", "--qualite", default="360",
                   help="hauteur max en pixels, ou 'max' (défaut : 360)")
    p.add_argument("-a", "--audio", action="store_true", help="audio seul")
    p.add_argument("--format", dest="conteneur", default="",
                   help="mp4/mkv/webm en vidéo, m4a/mp3/opus/wav en audio")
    p.add_argument("--de", help="début de l'extrait : 20, 20:30 ou 1:20:30")
    p.add_argument("--a", dest="jusqua", help="fin de l'extrait")
    p.add_argument("--coupe-rapide", action="store_true",
                   help="ne pas réencoder : plus rapide, coupe à l'image clé la plus proche")
    p.add_argument("-s", "--sous-titres", action="store_true")
    p.add_argument("--langue", default="fr")
    p.add_argument("-n", "--numeroter", action="store_true",
                   help="numérote les fichiers dans l'ordre des liens")
    p.add_argument("--elements", default="", help="éléments de playlist, ex. 1-5,8")
    p.add_argument("--cookies", default="", choices=core.NAVIGATEURS,
                   help="navigateur d'où lire les cookies")
    p.add_argument("--miniature", action="store_true", help="intègre la miniature au fichier")
    p.add_argument("--installer-ffmpeg", action="store_true",
                   help="télécharge ffmpeg dans le dossier de l'outil puis quitte")
    return p.parse_args(argv)


def construire_reglages(args: argparse.Namespace) -> core.Reglages:
    urls = list(args.urls)
    if args.fichier:
        lignes = args.fichier.read_text(encoding="utf-8").splitlines()
        urls += [l.strip() for l in lignes if l.strip() and not l.lstrip().startswith("#")]

    defaut_conteneur = "m4a" if args.audio else "mp4"
    return core.Reglages(
        urls=urls,
        dossier=args.sortie,
        audio_seul=args.audio,
        hauteur=None if str(args.qualite).lower() in ("max", "best") else int(args.qualite),
        conteneur=args.conteneur or defaut_conteneur,
        sous_titres=args.sous_titres,
        langue=args.langue,
        debut=core.lire_duree(args.de) if args.de else None,
        fin=core.lire_duree(args.jusqua) if args.jusqua else None,
        coupe_precise=not args.coupe_rapide,
        numeroter=args.numeroter,
        elements=args.elements,
        navigateur=args.cookies,
        miniature=args.miniature,
    )


def main(argv=None) -> int:
    args = analyser_arguments(argv)

    if args.installer_ffmpeg:
        def montrer(recus, total, message):
            part = f"{recus / 1e6:.0f}/{total / 1e6:.0f} Mo" if total else f"{recus / 1e6:.0f} Mo"
            print(f"\r{message} : {part}   ", end="", flush=True)
        chemin = ffmpeg_auto.installer(progres=montrer)
        print(f"\nffmpeg installé : {chemin}")
        return 0

    try:
        reglages = construire_reglages(args)
        options = core.construire(reglages, logger=None)
    except core.ErreurReglages as erreur:
        print(f"Réglage à corriger : {erreur}", file=sys.stderr)
        return 2
    except ValueError as erreur:
        print(f"Argument invalide : {erreur}", file=sys.stderr)
        return 2

    options["quiet"] = False
    options["noprogress"] = False
    return core.telecharger(reglages, options)


if __name__ == "__main__":
    raise SystemExit(main())
