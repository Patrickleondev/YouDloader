"""YouDloader : interface graphique de téléchargement de vidéos et de playlists.

Reprend l'identité du projet YouDloader de 2024 (logo, icône) sur un moteur neuf
basé sur yt-dlp. Lancer avec :  python gui.py
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from yt_dlp.utils import DownloadCancelled

from . import core, ffmpeg_auto, theme

VERSION = "2.0"


def activer_dpi() -> float:
    """Rend l'application consciente de la mise à l'échelle Windows.

    Sans ça, sur un écran à 150 %, Windows agrandit une image de 1280x720 : texte flou
    et fenêtre qui déborde. Renvoie le facteur d'échelle pour dimensionner le reste.
    """
    if sys.platform != "win32":
        return 1.0
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 1 = conscient du DPI système
        return ctypes.windll.user32.GetDpiForSystem() / 96
    except (AttributeError, OSError):
        return 1.0


def ressource(nom: str) -> Path:
    """Chemin d'un fichier d'assets, que l'on tourne depuis les sources ou depuis l'exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / nom


def fichier_config() -> Path:
    base = os.environ.get("APPDATA") or Path.home()
    return Path(base) / "YouDloader" / "config.json"


def charger_config() -> dict:
    try:
        return json.loads(fichier_config().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def enregistrer_config(d: dict) -> None:
    try:
        f = fichier_config()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except OSError:
        pass  # un réglage non mémorisé ne doit pas empêcher de fermer l'application


class JournalFile:
    """Logger yt-dlp qui renvoie les messages vers le fil principal, via la file."""

    def __init__(self, file: queue.Queue):
        self.file = file

    def debug(self, message: str) -> None:
        if not message.startswith("[debug] "):
            self.file.put(("journal", message))

    def info(self, message: str) -> None:
        self.file.put(("journal", message))

    def warning(self, message: str) -> None:
        self.file.put(("journal", "[!] " + message))

    def error(self, message: str) -> None:
        self.file.put(("journal", "[x] " + message))


class Application(tk.Tk):
    def __init__(self) -> None:
        self.echelle = activer_dpi()
        super().__init__()
        self.reglages_demarrage = charger_config()
        self.title(f"YouDloader {VERSION}")
        # Les polices sont en points : Tk doit savoir combien de pixels fait un point.
        self.tk.call("tk", "scaling", self.echelle * 96 / 72)
        self._dimensionner(1000, 760)
        self.nom_theme = tk.StringVar(value=self.reglages_demarrage.get("theme", "sombre"))
        self.p = theme.appliquer(self, self.nom_theme.get())
        try:
            self.iconbitmap(str(ressource("youdloader.ico")))
        except tk.TclError:
            pass

        self.file: queue.Queue = queue.Queue()
        self.annulation = threading.Event()
        self.travail: threading.Thread | None = None
        self.analyse: dict | None = None
        self.vues: set[str] = set()      # identifiants des vidéos déjà vues en cours de route
        self.toiles: list[tk.Canvas] = []  # zones défilantes, à repeindre si le thème change
        self.reglages = self.reglages_demarrage

        self._construire()
        self._rafraichir_etats()
        self.after(120, self._pomper)
        self.protocol("WM_DELETE_WINDOW", self._fermer)

    def _dimensionner(self, largeur: int, hauteur: int) -> None:
        """Taille voulue, ramenée à ce que l'écran peut afficher, et fenêtre centrée."""
        e = self.echelle
        dispo_l, dispo_h = self.winfo_screenwidth() - 60, self.winfo_screenheight() - 110
        l = min(int(largeur * e), dispo_l)
        h = min(int(hauteur * e), dispo_h)
        x, y = max(0, (self.winfo_screenwidth() - l) // 2), max(0, (dispo_h - h) // 3)
        self.geometry(f"{l}x{h}+{x}+{y}")
        self.minsize(min(int(840 * e), dispo_l), min(int(600 * e), dispo_h))

    # ------------------------------------------------------------------ interface

    def _construire(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._entete()
        self._zone_liens()

        onglets = ttk.Notebook(self)
        onglets.grid(row=2, column=0, sticky="nsew", padx=16, pady=(12, 0))
        self._onglet_reglages(onglets)
        self._onglet_playlist(onglets)
        self._onglet_journal(onglets)

        self._barre_basse()
        # Après coup seulement : ce réglage touche aux boutons de la barre basse.
        self._changer_mode()

    def _entete(self) -> None:
        cadre = ttk.Frame(self, style="Carte.TFrame", padding=(16, 12))
        cadre.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 0))
        cadre.columnconfigure(1, weight=1)

        try:
            self.logo = tk.PhotoImage(file=str(ressource("logo96.png"))).subsample(2, 2)
            ttk.Label(cadre, image=self.logo, style="Carte.TLabel").grid(row=0, column=0, rowspan=2,
                                                                        padx=(0, 14))
        except tk.TclError:
            self.logo = None

        ttk.Label(cadre, text="YouDloader", style="Titre.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(cadre, text="Vidéos, playlists, pistes audio et extraits minutés",
                  style="Doux.TLabel").grid(row=1, column=1, sticky="w")

        self.bouton_theme = ttk.Button(cadre, style="Discret.TButton",
                                       command=self._basculer_theme)
        self.bouton_theme.grid(row=0, column=3, sticky="ne", padx=(12, 0))
        self._libeller_theme()

        if not core.ffmpeg_present():
            ttk.Label(cadre, text="ffmpeg introuvable : fusion, conversion audio et\n"
                                  "extraits indisponibles", style="Alerte.TLabel",
                      justify="right").grid(row=0, column=2, rowspan=2, sticky="e")

    def _zone_liens(self) -> None:
        cadre = ttk.LabelFrame(self, text=" LIENS  (un par ligne : vidéo, playlist, chaîne) ",
                               padding=12)
        cadre.grid(row=1, column=0, sticky="ew", padx=16, pady=(12, 0))
        cadre.columnconfigure(0, weight=1)

        self.liens = tk.Text(cadre, height=3, background=self.p.champ, foreground=self.p.texte,
                             insertbackground=self.p.texte, relief="flat", font=theme.POLICE,
                             wrap="none", padx=8, pady=6)
        self.liens.grid(row=0, column=0, sticky="ew")
        self.liens.bind("<KeyRelease>", lambda _e: self._rafraichir_etats())

        cote = ttk.Frame(cadre)
        cote.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        self.bouton_analyser = ttk.Button(cote, text="Analyser", command=self._lancer_analyse)
        self.bouton_analyser.pack(fill="x")
        ttk.Button(cote, text="Coller", command=self._coller).pack(fill="x", pady=(8, 0))
        ttk.Button(cote, text="Vider", command=self._vider_liens).pack(fill="x", pady=(8, 0))

        self.resume = ttk.Label(cadre, text="Aucun lien analysé.", style="DouxFond.TLabel")
        self.resume.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _cadre_defilant(self, parent: ttk.Frame) -> ttk.Frame:
        """Rend une page défilante : sur un petit écran, les réglages du bas restaient cachés."""
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        toile = tk.Canvas(parent, background=self.p.fond, highlightthickness=0, borderwidth=0)
        barre = ttk.Scrollbar(parent, orient="vertical", command=toile.yview)
        interieur = ttk.Frame(toile, padding=(16, 12))
        fenetre = toile.create_window((0, 0), window=interieur, anchor="nw")

        interieur.bind("<Configure>",
                       lambda _e: toile.configure(scrollregion=toile.bbox("all")))
        toile.bind("<Configure>", lambda e: toile.itemconfigure(fenetre, width=e.width))
        toile.configure(yscrollcommand=barre.set)
        toile.grid(row=0, column=0, sticky="nsew")
        barre.grid(row=0, column=1, sticky="ns")

        # La molette n'agit que quand le pointeur est sur cette page.
        def molette(evenement):
            toile.yview_scroll(-1 * (evenement.delta // 120), "units")

        toile.bind("<Enter>", lambda _e: toile.bind_all("<MouseWheel>", molette))
        toile.bind("<Leave>", lambda _e: toile.unbind_all("<MouseWheel>"))
        self.toiles.append(toile)
        return interieur

    def _onglet_reglages(self, onglets: ttk.Notebook) -> None:
        contenant = ttk.Frame(onglets)
        onglets.add(contenant, text="Réglages")
        page = self._cadre_defilant(contenant)
        page.columnconfigure(1, weight=1)
        page.columnconfigure(3, weight=1)

        # --- ce qu'on récupère
        self.mode = tk.StringVar(value=self.reglages.get("mode", "video"))
        ligne = ttk.Frame(page)
        ligne.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))
        ttk.Label(ligne, text="Récupérer :").pack(side="left", padx=(0, 12))
        for libelle, valeur in (("Vidéo + son", "video"), ("Audio seul", "audio")):
            ttk.Radiobutton(ligne, text=libelle, value=valeur, variable=self.mode,
                            command=self._changer_mode).pack(side="left", padx=(0, 16))

        ttk.Label(page, text="Qualité").grid(row=1, column=0, sticky="w", pady=6)
        self.qualite = ttk.Combobox(page, state="readonly", width=18)
        self.qualite.grid(row=1, column=1, sticky="ew", padx=(8, 20), pady=6)

        ttk.Label(page, text="Format du fichier").grid(row=1, column=2, sticky="w", pady=6)
        self.conteneur = ttk.Combobox(page, state="readonly", width=18)
        self.conteneur.grid(row=1, column=3, sticky="ew", padx=(8, 0), pady=6)

        # --- extrait
        self.extrait = tk.BooleanVar(value=False)
        boite = ttk.LabelFrame(page, text=" EXTRAIT ", padding=12)
        boite.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(16, 6))
        ttk.Checkbutton(boite, text="Ne prendre qu'un passage", variable=self.extrait,
                        command=self._rafraichir_etats).grid(row=0, column=0, columnspan=6, sticky="w")

        ttk.Label(boite, text="de").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.debut = ttk.Entry(boite, width=10)
        self.debut.grid(row=1, column=1, padx=(8, 16), pady=(10, 0))
        ttk.Label(boite, text="à").grid(row=1, column=2, sticky="w", pady=(10, 0))
        self.fin = ttk.Entry(boite, width=10)
        self.fin.grid(row=1, column=3, padx=(8, 16), pady=(10, 0))
        self.precise = tk.BooleanVar(value=True)
        ttk.Checkbutton(boite, text="coupe précise à la seconde (réencode, plus lent)",
                        variable=self.precise).grid(row=1, column=4, sticky="w", pady=(10, 0))
        ttk.Label(boite, text="Formats acceptés : 20 (minutes), 20:30 (min:sec), 1:20:30 (h:min:sec). "
                              "Laisser « à » vide va jusqu'à la fin.",
                  style="DouxFond.TLabel").grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))

        # --- options
        autres = ttk.Frame(page)
        autres.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        self.sous_titres = tk.BooleanVar(value=self.reglages.get("sous_titres", False))
        ttk.Checkbutton(autres, text="Sous-titres", variable=self.sous_titres,
                        command=self._rafraichir_etats).grid(row=0, column=0, sticky="w")
        self.langue = ttk.Entry(autres, width=6)
        self.langue.insert(0, self.reglages.get("langue", "fr"))
        self.langue.grid(row=0, column=1, padx=(8, 24))

        self.numeroter = tk.BooleanVar(value=self.reglages.get("numeroter", False))
        ttk.Checkbutton(autres, text="Numéroter dans l'ordre des liens",
                        variable=self.numeroter).grid(row=0, column=2, sticky="w", padx=(0, 24))
        self.miniature = tk.BooleanVar(value=self.reglages.get("miniature", False))
        ttk.Checkbutton(autres, text="Intégrer la miniature",
                        variable=self.miniature).grid(row=0, column=3, sticky="w")

        ttk.Label(autres, text="Cookies du navigateur").grid(row=1, column=0, columnspan=2,
                                                            sticky="w", pady=(12, 0))
        self.navigateur = ttk.Combobox(autres, state="readonly", width=12,
                                       values=["aucun"] + core.NAVIGATEURS[1:])
        self.navigateur.set(self.reglages.get("navigateur", "aucun"))
        self.navigateur.grid(row=1, column=2, sticky="w", pady=(12, 0))
        ttk.Label(autres, text="(pour les vidéos réservées aux comptes connectés)",
                  style="DouxFond.TLabel").grid(row=1, column=3, sticky="w", pady=(12, 0))


    def _onglet_playlist(self, onglets: ttk.Notebook) -> None:
        page = ttk.Frame(onglets, padding=16)
        onglets.add(page, text="Playlist")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)

        haut = ttk.Frame(page)
        haut.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(haut, text="Analyse un lien de playlist pour choisir les vidéos à prendre.",
                  style="DouxFond.TLabel").pack(side="left")
        ttk.Button(haut, text="Tout", command=lambda: self.table.selection_set(
            self.table.get_children())).pack(side="right", padx=(8, 0))
        ttk.Button(haut, text="Rien", command=lambda: self.table.selection_remove(
            self.table.get_children())).pack(side="right")

        self.table = ttk.Treeview(page, columns=("n", "titre", "duree"), show="headings",
                                  selectmode="extended")
        self.table.heading("n", text="N°")
        self.table.heading("titre", text="TITRE")
        self.table.heading("duree", text="DURÉE")
        self.table.column("n", width=50, anchor="center", stretch=False)
        self.table.column("duree", width=90, anchor="e", stretch=False)
        self.table.grid(row=1, column=0, sticky="nsew")
        barre = ttk.Scrollbar(page, orient="vertical", command=self.table.yview)
        barre.grid(row=1, column=1, sticky="ns")
        self.table.configure(yscrollcommand=barre.set)

        ttk.Label(page, text="Sans sélection, toute la playlist est téléchargée.",
                  style="DouxFond.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _onglet_journal(self, onglets: ttk.Notebook) -> None:
        page = ttk.Frame(onglets, padding=16)
        onglets.add(page, text="Journal")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)

        self.journal = tk.Text(page, background=self.p.champ, foreground=self.p.doux,
                               relief="flat", font=theme.POLICE_MONO, wrap="word",
                               padx=10, pady=8, state="disabled")
        self.journal.grid(row=0, column=0, sticky="nsew")
        barre = ttk.Scrollbar(page, orient="vertical", command=self.journal.yview)
        barre.grid(row=0, column=1, sticky="ns")
        self.journal.configure(yscrollcommand=barre.set)
        self.journal.tag_configure("erreur", foreground=self.p.erreur)
        self.journal.tag_configure("succes", foreground=self.p.succes)

        ttk.Button(page, text="Copier le journal", command=self._copier_journal).grid(
            row=1, column=0, sticky="w", pady=(10, 0))

    def _barre_basse(self) -> None:
        # Le dossier de destination reste visible quel que soit l'onglet ouvert :
        # c'est le réglage qu'on vérifie juste avant de cliquer sur Télécharger.
        ligne = ttk.Frame(self, padding=(16, 12, 16, 0))
        ligne.grid(row=3, column=0, sticky="ew")
        ligne.columnconfigure(1, weight=1)
        ttk.Label(ligne, text="Dossier").grid(row=0, column=0, padx=(0, 8))
        self.dossier = ttk.Entry(ligne)
        self.dossier.insert(0, self.reglages.get("dossier")
                            or str(Path.home() / "Videos" / "YouDloader"))
        self.dossier.grid(row=0, column=1, sticky="ew")
        ttk.Button(ligne, text="Parcourir", command=self._choisir_dossier).grid(row=0, column=2,
                                                                               padx=(8, 0))

        cadre = ttk.Frame(self, padding=(16, 12, 16, 16))
        cadre.grid(row=4, column=0, sticky="ew")
        cadre.columnconfigure(0, weight=1)

        self.barre = ttk.Progressbar(cadre, style="Barre.Horizontal.TProgressbar",
                                     mode="determinate", maximum=100)
        self.barre.grid(row=0, column=0, columnspan=4, sticky="ew")

        self.etat = ttk.Label(cadre, text="Prêt.", style="DouxFond.TLabel")
        self.etat.grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.bouton_dossier = ttk.Button(cadre, text="Ouvrir le dossier", command=self._ouvrir_dossier)
        self.bouton_dossier.grid(row=1, column=1, padx=(8, 0), pady=(8, 0))
        self.bouton_annuler = ttk.Button(cadre, text="Annuler", command=self._annuler)
        self.bouton_annuler.grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        self.bouton_lancer = ttk.Button(cadre, text="Télécharger", style="Action.TButton",
                                        command=self._lancer_telechargement)
        self.bouton_lancer.grid(row=1, column=3, padx=(8, 0), pady=(8, 0))

    def _libeller_theme(self) -> None:
        clair = self.nom_theme.get() == "clair"
        self.bouton_theme.configure(text="Mode sombre" if clair else "Mode clair")

    def _basculer_theme(self) -> None:
        self.nom_theme.set("clair" if self.nom_theme.get() == "sombre" else "sombre")
        self.p = theme.appliquer(self, self.nom_theme.get())
        # ttk se repeint tout seul ; ces deux-là sont des widgets tk classiques.
        self.liens.configure(background=self.p.champ, foreground=self.p.texte,
                             insertbackground=self.p.texte)
        self.journal.configure(background=self.p.champ, foreground=self.p.doux)
        self.journal.tag_configure("erreur", foreground=self.p.erreur)
        self.journal.tag_configure("succes", foreground=self.p.succes)
        for toile in self.toiles:
            toile.configure(background=self.p.fond)
        self._libeller_theme()

    # ------------------------------------------------------------------ petites actions

    def _coller(self) -> None:
        try:
            self.liens.insert("end", self.clipboard_get().strip() + "\n")
        except tk.TclError:
            pass
        self._rafraichir_etats()

    def _vider_liens(self) -> None:
        self.liens.delete("1.0", "end")
        self.table.delete(*self.table.get_children())
        self.analyse = None
        self.resume.configure(text="Aucun lien analysé.")
        self._rafraichir_etats()

    def _choisir_dossier(self) -> None:
        choix = filedialog.askdirectory(initialdir=self.dossier.get() or str(Path.home()))
        if choix:
            self.dossier.delete(0, "end")
            self.dossier.insert(0, choix)

    def _ouvrir_dossier(self) -> None:
        chemin = Path(self.dossier.get())
        chemin.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(chemin)  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(chemin)])

    def _copier_journal(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.journal.get("1.0", "end"))

    def _changer_mode(self) -> None:
        audio = self.mode.get() == "audio"
        if audio:
            self.conteneur.configure(values=core.CONTENEURS_AUDIO)
            self.conteneur.set(self.reglages.get("conteneur_audio", "m4a"))
            debits = (self.analyse or {}).get("debits") or []
            self.qualite.configure(values=["Meilleure"] + [f"{d} kb/s" for d in reversed(debits)])
        else:
            self.conteneur.configure(values=core.CONTENEURS_VIDEO)
            self.conteneur.set(self.reglages.get("conteneur_video", "mp4"))
            hauteurs = (self.analyse or {}).get("hauteurs") or core.HAUTEURS
            self.qualite.configure(values=[f"{h}p" for h in hauteurs] + ["Meilleure"])
        memo = self.reglages.get("qualite_audio" if audio else "qualite_video")
        self.qualite.set(memo if memo in self.qualite.cget("values") else
                         (self.qualite.cget("values") or ["Meilleure"])[0 if audio else -1])
        if not audio and "360p" in self.qualite.cget("values") and not memo:
            self.qualite.set("360p")
        self._rafraichir_etats()

    def _rafraichir_etats(self) -> None:
        """Active ou grise les champs selon les cases cochées, et les boutons selon l'activité."""
        occupe = self.travail is not None and self.travail.is_alive()
        a_des_liens = bool(self._liste_liens())

        etat_extrait = "normal" if self.extrait.get() else "disabled"
        self.debut.configure(state=etat_extrait)
        self.fin.configure(state=etat_extrait)
        self.langue.configure(state="normal" if self.sous_titres.get() else "disabled")

        self.bouton_lancer.configure(state="disabled" if occupe or not a_des_liens else "normal")
        self.bouton_analyser.configure(state="disabled" if occupe or not a_des_liens else "normal")
        self.bouton_annuler.configure(state="normal" if occupe else "disabled")

    def _liste_liens(self) -> list[str]:
        brut = self.liens.get("1.0", "end").splitlines()
        return [l.strip() for l in brut if l.strip() and not l.strip().startswith("#")]

    def _ecrire(self, texte: str, tag: str = "") -> None:
        self.journal.configure(state="normal")
        self.journal.insert("end", texte.rstrip() + "\n", tag)
        self.journal.see("end")
        self.journal.configure(state="disabled")

    # ------------------------------------------------------------------ analyse

    def _lancer_analyse(self) -> None:
        liens = self._liste_liens()
        if not liens:
            return
        self.etat.configure(text="Analyse en cours...")
        self.barre.configure(mode="indeterminate")
        self.barre.start(12)
        self._demarrer(self._travail_analyse, liens[0])

    def _travail_analyse(self, url: str) -> None:
        try:
            navigateur = "" if self.navigateur.get() == "aucun" else self.navigateur.get()
            info = core.analyser(url, navigateur=navigateur, logger=JournalFile(self.file))
            self.file.put(("analyse", info))
        except Exception as erreur:  # yt-dlp lève des types très variés
            self.file.put(("echec", str(erreur)))

    def _appliquer_analyse(self, info: dict) -> None:
        self.analyse = info
        self.table.delete(*self.table.get_children())
        for e in info["elements"]:
            self.table.insert("", "end", iid=str(e["index"]),
                              values=(e["index"], e["titre"], core.ecrire_duree(e["duree"])))

        if info["playlist"]:
            total = sum(e["duree"] or 0 for e in info["elements"])
            texte = (f"Playlist : {info['titre']}  ·  {len(info['elements'])} vidéos  "
                     f"·  {core.ecrire_duree(total)} au total  ·  {info['chaine']}")
        else:
            texte = (f"{info['titre']}  ·  {core.ecrire_duree(info['duree'])}  ·  {info['chaine']}")
        if info["hauteurs"]:
            texte += "  ·  jusqu'à " + f"{info['hauteurs'][-1]}p"
        self.resume.configure(text=texte)

        if not self.extrait.get() and info.get("duree"):
            self.fin.configure(state="normal")
            if not self.fin.get():
                self.fin.insert(0, core.ecrire_duree(info["duree"]))
            self.fin.configure(state="disabled")
        self._changer_mode()

    # ------------------------------------------------------------------ téléchargement

    def _rassembler(self) -> core.Reglages:
        """Lit l'interface et en fait un objet Reglages. Lève ErreurReglages si c'est incohérent."""
        audio = self.mode.get() == "audio"
        qualite = self.qualite.get()
        hauteur = None if qualite.startswith("Meill") or audio else int(qualite.rstrip("p"))
        debit = "0" if (not audio or qualite.startswith("Meill")) else qualite.split()[0]

        selection = sorted(int(i) for i in self.table.selection())
        elements = ",".join(str(i) for i in selection) if selection else ""

        return core.Reglages(
            urls=self._liste_liens(),
            dossier=Path(self.dossier.get().strip() or "."),
            audio_seul=audio,
            hauteur=hauteur,
            conteneur=self.conteneur.get(),
            qualite_audio=debit,
            sous_titres=self.sous_titres.get(),
            langue=self.langue.get().strip() or "fr",
            debut=core.lire_duree(self.debut.get()) if self.extrait.get() and self.debut.get() else None,
            fin=core.lire_duree(self.fin.get()) if self.extrait.get() and self.fin.get() else None,
            coupe_precise=self.precise.get(),
            numeroter=self.numeroter.get(),
            elements=elements,
            navigateur="" if self.navigateur.get() == "aucun" else self.navigateur.get(),
            miniature=self.miniature.get(),
        )

    def _lancer_telechargement(self) -> None:
        try:
            r = self._rassembler()
            options = core.construire(r, hooks_progres=[self._hook], hooks_post=[self._hook_post],
                                      logger=JournalFile(self.file))
        except core.ErreurReglages as erreur:
            messagebox.showwarning("Réglage à corriger", str(erreur), parent=self)
            return
        except ValueError as erreur:
            messagebox.showwarning("Réglage à corriger", str(erreur), parent=self)
            return

        self.annulation.clear()
        self.vues.clear()
        self.barre.configure(mode="determinate", value=0)
        self._ecrire(f"--- Téléchargement de {len(r.urls)} lien(s) vers {r.dossier}")
        if r.extrait:
            self._ecrire(f"    extrait {core.ecrire_duree(r.debut or 0)} -> "
                         f"{core.ecrire_duree(r.fin) if r.fin else 'fin'} "
                         f"(sans archive : un extrait ne marque pas la vidéo comme faite)")
        self.etat.configure(text="Téléchargement...")
        self._demarrer(self._travail_telechargement, r, options)

    def _travail_telechargement(self, r: core.Reglages, options: dict) -> None:
        try:
            code = core.telecharger(r, options)
            self.file.put(("fini", code))
        except DownloadCancelled:
            self.file.put(("fini", -1))
        except Exception as erreur:
            self.file.put(("echec", str(erreur)))

    def _hook(self, d: dict) -> None:
        """Appelé par yt-dlp dans le fil de travail : ne touche à rien de Tkinter."""
        if self.annulation.is_set():
            raise DownloadCancelled("annulé")
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            self.file.put(("progres", {
                "pct": (d.get("downloaded_bytes", 0) / total * 100) if total else None,
                "vitesse": d.get("speed"),
                "eta": d.get("eta"),
                "id": (d.get("info_dict") or {}).get("id"),
                "titre": (d.get("info_dict") or {}).get("title") or "",
            }))
        elif d["status"] == "finished":
            self.file.put(("journal", "Fichier récupéré : " + Path(d.get("filename", "")).name))

    def _hook_post(self, d: dict) -> None:
        if self.annulation.is_set():
            raise DownloadCancelled("annulé")
        if d.get("status") == "started":
            self.file.put(("etape", d.get("postprocessor", "")))

    def _demarrer(self, cible, *args) -> None:
        self.travail = threading.Thread(target=cible, args=args, daemon=True)
        self.travail.start()
        self._rafraichir_etats()

    def _annuler(self) -> None:
        self.annulation.set()
        self.etat.configure(text="Annulation en cours...")

    # ------------------------------------------------------------------ boucle de messages

    def _pomper(self) -> None:
        """Vide la file des messages du fil de travail. Seul endroit qui modifie l'affichage."""
        try:
            while True:
                genre, charge = self.file.get_nowait()
                if genre == "journal":
                    self._ecrire(str(charge), "erreur" if str(charge).startswith("[x]") else "")
                elif genre == "progres":
                    self._montrer_progres(charge)
                elif genre == "etape":
                    self.etat.configure(text=f"Traitement : {charge}")
                elif genre == "analyse":
                    self.barre.stop()
                    self.barre.configure(mode="determinate", value=0)
                    self._appliquer_analyse(charge)
                    self.etat.configure(text="Analyse terminée.")
                elif genre == "fini":
                    self._terminer(charge)
                elif genre == "echec":
                    self.barre.stop()
                    self.barre.configure(mode="determinate", value=0)
                    self._ecrire("[x] " + str(charge), "erreur")
                    self.etat.configure(text="Échec. Voir le journal.")
                    messagebox.showerror("Échec", str(charge), parent=self)
        except queue.Empty:
            pass
        self._rafraichir_etats()
        self.after(120, self._pomper)

    def _montrer_progres(self, p: dict) -> None:
        if p.get("id"):
            self.vues.add(p["id"])
        if p["pct"] is None:
            # Les extraits passent par ffmpeg, qui ne donne pas de taille totale.
            if self.barre.cget("mode") != "indeterminate":
                self.barre.configure(mode="indeterminate")
                self.barre.start(12)
        else:
            if self.barre.cget("mode") != "determinate":
                self.barre.stop()
                self.barre.configure(mode="determinate")
            self.barre.configure(value=p["pct"])

        morceaux = []
        if self.vues:
            total = len(self.analyse["elements"]) if self.analyse and self.analyse["elements"] else None
            morceaux.append(f"vidéo {len(self.vues)}" + (f"/{total}" if total else ""))
        if p["pct"] is not None:
            morceaux.append(f"{p['pct']:.0f} %")
        if p.get("vitesse"):
            morceaux.append(f"{p['vitesse'] / 1024 / 1024:.1f} Mo/s")
        if p.get("eta"):
            morceaux.append("reste " + core.ecrire_duree(p["eta"]))
        if p.get("titre"):
            morceaux.append(p["titre"][:60])
        self.etat.configure(text="  ·  ".join(morceaux))

    def _terminer(self, code: int) -> None:
        self.barre.stop()
        self.barre.configure(mode="determinate", value=0 if code else 100)
        if code == -1:
            self.etat.configure(text="Annulé.")
            self._ecrire("--- Annulé par l'utilisateur.")
        elif code == 0:
            self.etat.configure(text=f"Terminé : {len(self.vues)} vidéo(s).")
            self._ecrire(f"--- Terminé : {len(self.vues)} vidéo(s).", "succes")
        else:
            self.etat.configure(text="Terminé avec des erreurs. Voir le journal.")
            self._ecrire("--- Terminé, mais au moins un lien a échoué.", "erreur")

    # ------------------------------------------------------------------ fermeture

    def _fermer(self) -> None:
        if self.travail is not None and self.travail.is_alive():
            if not messagebox.askokcancel("Quitter", "Un téléchargement est en cours. Quitter ?",
                                          parent=self):
                return
            self.annulation.set()
        audio = self.mode.get() == "audio"
        self.reglages.update({
            "mode": self.mode.get(),
            "dossier": self.dossier.get(),
            "sous_titres": self.sous_titres.get(),
            "langue": self.langue.get(),
            "numeroter": self.numeroter.get(),
            "miniature": self.miniature.get(),
            "navigateur": self.navigateur.get(),
            "theme": self.nom_theme.get(),
            ("qualite_audio" if audio else "qualite_video"): self.qualite.get(),
            ("conteneur_audio" if audio else "conteneur_video"): self.conteneur.get(),
        })
        enregistrer_config(self.reglages)
        self.destroy()


if __name__ == "__main__":
    Application().mainloop()
