"""Moteur de téléchargement : construit les options yt-dlp et lance les téléchargements.

Partagé par la ligne de commande (dl.py) et l'interface graphique (gui.py).
Aucune dépendance à Tkinter ici, pour que le moteur reste testable tout seul.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled, download_range_func

from . import ffmpeg_auto

# Qualités proposées quand on n'a pas analysé la vidéo.
HAUTEURS = [144, 240, 360, 480, 720, 1080, 1440, 2160]
CONTENEURS_VIDEO = ["mp4", "mkv", "webm"]
CONTENEURS_AUDIO = ["m4a", "mp3", "opus", "wav"]
NAVIGATEURS = ["", "chrome", "firefox", "edge", "brave", "opera", "vivaldi"]


class ErreurReglages(ValueError):
    """Un réglage est incohérent : on prévient avant de lancer le téléchargement."""


def lire_duree(texte: str) -> float:
    """Convertit "20", "20:30" ou "1:20:30" en secondes.

    Un nombre seul est lu comme des minutes : c'est la façon dont on parle d'une
    vidéo ("à partir de la 20e minute").
    """
    texte = (texte or "").strip().replace(",", ".")
    if not texte:
        raise ErreurReglages("durée vide")
    if not re.fullmatch(r"\d+(\.\d+)?(:\d{1,2}(\.\d+)?){0,2}", texte):
        raise ErreurReglages(f"« {texte} » n'est pas une durée (attendu : 20, 20:30 ou 1:20:30)")

    parties = [float(p) for p in texte.split(":")]
    if len(parties) == 1:
        return parties[0] * 60
    if len(parties) == 2:
        return parties[0] * 60 + parties[1]
    return parties[0] * 3600 + parties[1] * 60 + parties[2]


def ecrire_duree(secondes: float | None) -> str:
    """Formate des secondes en h:mm:ss ou mm:ss, pour l'affichage."""
    if secondes is None:
        return "?"
    s = int(round(secondes))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@dataclass
class Reglages:
    """Tout ce que l'utilisateur choisit, en un seul objet."""

    urls: list[str] = field(default_factory=list)
    dossier: Path = Path("telechargements")
    audio_seul: bool = False
    hauteur: int | None = 360          # None = la meilleure disponible
    conteneur: str = "mp4"            # mp4/mkv/webm, ou m4a/mp3/opus/wav en audio
    qualite_audio: str = "0"           # 0 = meilleure, sinon kbps pour la conversion
    sous_titres: bool = False
    langue: str = "fr"
    debut: float | None = None         # secondes ; None = depuis le début
    fin: float | None = None           # secondes ; None = jusqu'à la fin
    coupe_precise: bool = True
    numeroter: bool = False
    elements: str = ""                 # éléments de playlist, ex. "1-5,8"
    navigateur: str = ""               # cookies : "" = aucun
    miniature: bool = False
    metadonnees: bool = True

    @property
    def extrait(self) -> bool:
        return self.debut is not None or self.fin is not None

    def verifier(self) -> None:
        if not self.urls:
            raise ErreurReglages("aucun lien à télécharger")
        if self.debut is not None and self.fin is not None and self.fin <= self.debut:
            raise ErreurReglages(
                f"la fin ({ecrire_duree(self.fin)}) doit être après le début ({ecrire_duree(self.debut)})"
            )
        if self.elements and not re.fullmatch(r"[\d\s,:\-]+", self.elements):
            raise ErreurReglages(f"« {self.elements} » n'est pas une liste d'éléments (ex. 1-5,8)")
        if self.extrait and not ffmpeg_present():
            raise ErreurReglages("découper un extrait exige ffmpeg, qui est introuvable")


def ffmpeg_present() -> bool:
    """ffmpeg du système, ou celui que l'outil a installé dans son propre dossier."""
    return ffmpeg_auto.present()


def modele_nom(r: Reglages) -> str:
    """Modèle de nom de fichier.

    Le "/" du sous-dossier de playlist reste hors du champ : placé dedans, il serait
    nettoyé en "⧹" et on obtiendrait un seul nom de fichier à rallonge.
    """
    suffixe = "(%(abr)dk)" if r.audio_seul else "(%(height)sp)"
    numero = "%(autonumber)03d - " if r.numeroter else "%(playlist_index&{:03d} - |)s"
    # Un extrait porte ses bornes dans le nom, sinon il écrase la vidéo entière.
    borne = " [%(section_start>%H-%M-%S|)s a %(section_end>%H-%M-%S|)s]" if r.extrait else ""
    return "%(playlist_title|)s/" + numero + "%(title)s" + suffixe + borne + ".%(ext)s"


def construire(r: Reglages, *, hooks_progres=(), hooks_post=(), logger=None) -> dict:
    """Traduit les réglages en dictionnaire d'options yt-dlp."""
    r.verifier()
    postprocesseurs = []

    if r.audio_seul:
        fmt = "ba[ext=m4a]/ba/b"
        tri = ["abr"]
        postprocesseurs.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": r.conteneur,
            "preferredquality": r.qualite_audio,
        })
    else:
        fmt = "bv*+ba/b"
        # res:360 prend la plus haute résolution <= 360 et, s'il n'y en a aucune,
        # la plus basse au-dessus. Un filtre height<=360 échouerait dans ce cas.
        tri = ["res", "ext:mp4:m4a"] if r.hauteur is None else [f"res:{r.hauteur}", "ext:mp4:m4a"]

    if r.sous_titres:
        postprocesseurs.append({"key": "FFmpegSubtitlesConvertor", "format": "srt"})
    if r.metadonnees:
        postprocesseurs.append({"key": "FFmpegMetadata"})
    if r.miniature:
        postprocesseurs.append({"key": "EmbedThumbnail"})

    o = {
        "format": fmt,
        "format_sort": tri,
        "outtmpl": str(r.dossier / modele_nom(r)),
        "paths": {"home": str(r.dossier)},
        "postprocessors": postprocesseurs,
        "ignoreerrors": "only_download",
        "js_runtimes": {"node": {}},
        "noprogress": True,
        "quiet": True,
        "no_warnings": False,
        "progress_hooks": list(hooks_progres),
        "postprocessor_hooks": list(hooks_post),
        "writethumbnail": r.miniature,
    }
    emplacement = ffmpeg_auto.emplacement_pour_ytdlp()
    if emplacement:
        o["ffmpeg_location"] = emplacement
    if not r.audio_seul:
        o["merge_output_format"] = r.conteneur

    if r.sous_titres:
        o.update(writesubtitles=True, writeautomaticsub=True, subtitleslangs=[r.langue])
    if r.elements:
        o["playlist_items"] = r.elements
    if r.navigateur:
        o["cookiesfrombrowser"] = (r.navigateur,)
    if logger is not None:
        o["logger"] = logger

    if r.extrait:
        o["download_ranges"] = download_range_func([], [[r.debut or 0, r.fin or float("inf")]])
        # Sans ça, la coupe tombe sur l'image clé précédente : jusqu'à ~10 s de décalage.
        o["force_keyframes_at_cuts"] = r.coupe_precise
    else:
        # L'archive ne sert que pour les téléchargements entiers : un extrait y
        # inscrirait la vidéo comme faite, et la version complète serait ignorée après.
        o["download_archive"] = str(r.dossier / "archive.txt")

    return o


def analyser(url: str, *, navigateur: str = "", logger=None) -> dict:
    """Récupère les informations d'un lien sans rien télécharger.

    Renvoie un dict : titre, durée, chaîne, qualités disponibles, et la liste des
    éléments si c'est une playlist.
    """
    o = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "js_runtimes": {"node": {}},
        # Dans une playlist, on ne détaille que la première vidéo : le reste à plat,
        # sinon analyser 50 liens prendrait plusieurs minutes.
        "extract_flat": "in_playlist",
    }
    if navigateur:
        o["cookiesfrombrowser"] = (navigateur,)
    if logger is not None:
        o["logger"] = logger

    with YoutubeDL(o) as ydl:
        info = ydl.extract_info(url, download=False)
    if info is None:
        raise ErreurReglages("lien illisible : vidéo privée, supprimée, ou lien erroné")

    entrees = [e for e in (info.get("entries") or []) if e]
    if entrees:
        premiere = entrees[0]
        if premiere.get("_type") == "url":  # entrée à plat : il faut l'analyser à part
            premiere = analyser(premiere["url"], navigateur=navigateur, logger=logger)["brut"]
    else:
        premiere = info

    # Les formats sans codec vidéo réel sont les planches de vignettes (27p, 45p, 90p) :
    # yt-dlp les liste comme des formats, mais ce ne sont pas des qualités téléchargeables.
    formats = premiere.get("formats") or []
    hauteurs = sorted({f["height"] for f in formats
                       if f.get("height") and f.get("vcodec") not in (None, "none")})
    debits = sorted({round(f["abr"]) for f in formats
                     if f.get("abr") and f.get("acodec") not in (None, "none")})

    return {
        "playlist": bool(entrees),
        "titre": info.get("title") or "?",
        "chaine": info.get("uploader") or premiere.get("uploader") or "?",
        "duree": premiere.get("duration") if not entrees else None,
        "hauteurs": hauteurs,
        "debits": debits,
        "elements": [
            {
                "index": i,
                "titre": e.get("title") or "?",
                "duree": e.get("duration"),
            }
            for i, e in enumerate(entrees, 1)
        ],
        "brut": premiere,
    }


def telecharger(r: Reglages, options: dict) -> int:
    """Lance le téléchargement. Renvoie le code de retour de yt-dlp (0 = tout va bien)."""
    r.dossier.mkdir(parents=True, exist_ok=True)
    with YoutubeDL(options) as ydl:
        try:
            return ydl.download(r.urls)
        except DownloadCancelled:
            return -1
