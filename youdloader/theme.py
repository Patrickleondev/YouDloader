"""Palettes et styles ttk de YouDloader, en version sombre et claire.

Le bleu d'accent vient du logo d'origine (#0069D6), échantillonné sur l'icône de 2024.
Les deux palettes gardent le même accent : seul le fond et les contrastes changent.
"""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

POLICE = ("Segoe UI", 10)
POLICE_TITRE = ("Segoe UI Semibold", 16)
POLICE_PETITE = ("Segoe UI", 9)
POLICE_MONO = ("Consolas", 9)


@dataclass(frozen=True)
class Palette:
    nom: str
    fond: str
    carte: str
    champ: str
    bordure: str
    texte: str
    doux: str
    accent: str
    accent_vif: str
    sur_accent: str
    succes: str
    alerte: str
    erreur: str


SOMBRE = Palette(
    nom="sombre", fond="#11151C", carte="#1A202B", champ="#232B38", bordure="#2E3847",
    texte="#E7ECF3", doux="#8B95A7", accent="#0069D6", accent_vif="#1E86F0",
    sur_accent="#FFFFFF", succes="#2BA36F", alerte="#E0A33B", erreur="#D85050",
)

CLAIR = Palette(
    nom="clair", fond="#F4F6FA", carte="#FFFFFF", champ="#FFFFFF", bordure="#D3DAE6",
    texte="#1B2430", doux="#5F6B7D", accent="#0069D6", accent_vif="#0056B0",
    sur_accent="#FFFFFF", succes="#1C8355", alerte="#9A6B12", erreur="#B3261E",
)

PALETTES = {"sombre": SOMBRE, "clair": CLAIR}


def appliquer(racine: tk.Misc, nom: str = "sombre") -> Palette:
    """Installe la palette demandée sur toute l'application. Renvoie la palette active."""
    p = PALETTES.get(nom, SOMBRE)
    s = ttk.Style(racine)
    # "clam" est le seul thème ttk de base qui accepte qu'on repeigne tout.
    s.theme_use("clam")
    racine.configure(background=p.fond)

    s.configure(".", background=p.fond, foreground=p.texte, font=POLICE,
                fieldbackground=p.champ, bordercolor=p.bordure,
                lightcolor=p.carte, darkcolor=p.carte)
    s.configure("TFrame", background=p.fond)
    s.configure("Carte.TFrame", background=p.carte, relief="flat")
    s.configure("TLabel", background=p.fond, foreground=p.texte)
    s.configure("Carte.TLabel", background=p.carte, foreground=p.texte)
    s.configure("Titre.TLabel", background=p.carte, foreground=p.texte, font=POLICE_TITRE)
    s.configure("Doux.TLabel", background=p.carte, foreground=p.doux, font=POLICE_PETITE)
    s.configure("DouxFond.TLabel", background=p.fond, foreground=p.doux, font=POLICE_PETITE)
    s.configure("Alerte.TLabel", background=p.carte, foreground=p.alerte, font=POLICE_PETITE)

    s.configure("TLabelframe", background=p.fond, bordercolor=p.bordure)
    s.configure("TLabelframe.Label", background=p.fond, foreground=p.doux, font=POLICE_PETITE)

    s.configure("TButton", background=p.champ if p.nom == "sombre" else p.fond,
                foreground=p.texte, borderwidth=1, focusthickness=0, padding=(14, 7))
    s.map("TButton", background=[("active", p.bordure), ("disabled", p.carte)],
          foreground=[("disabled", p.doux)])

    s.configure("Action.TButton", background=p.accent, foreground=p.sur_accent,
                font=("Segoe UI Semibold", 10), padding=(18, 9), borderwidth=0)
    s.map("Action.TButton", background=[("active", p.accent_vif), ("disabled", p.bordure)],
          foreground=[("disabled", p.doux)])

    s.configure("Discret.TButton", background=p.carte, foreground=p.doux,
                padding=(10, 5), borderwidth=0, font=POLICE_PETITE)
    s.map("Discret.TButton", background=[("active", p.bordure)], foreground=[("active", p.texte)])

    s.configure("TEntry", fieldbackground=p.champ, foreground=p.texte, insertcolor=p.texte,
                bordercolor=p.bordure, lightcolor=p.bordure, darkcolor=p.bordure, padding=6)
    s.map("TEntry", fieldbackground=[("disabled", p.fond)], foreground=[("disabled", p.doux)])
    s.configure("TCombobox", fieldbackground=p.champ, background=p.champ, foreground=p.texte,
                arrowcolor=p.texte, bordercolor=p.bordure, padding=5)
    s.map("TCombobox", fieldbackground=[("readonly", p.champ)], foreground=[("disabled", p.doux)])

    for nom_widget in ("TCheckbutton", "TRadiobutton"):
        s.configure(nom_widget, background=p.fond, foreground=p.texte, focuscolor=p.fond,
                    indicatorbackground=p.champ, indicatorforeground=p.sur_accent,
                    indicatormargin=(0, 0, 8, 0), padding=4)
        s.map(nom_widget,
              background=[("active", p.fond)],
              foreground=[("disabled", p.doux)],
              indicatorbackground=[("selected", p.accent), ("active", p.bordure),
                                   ("disabled", p.carte)],
              indicatorforeground=[("selected", p.sur_accent)])

    s.configure("TNotebook", background=p.fond, borderwidth=0, tabmargins=(0, 6, 0, 0))
    s.configure("TNotebook.Tab", background=p.fond, foreground=p.doux,
                padding=(16, 8), borderwidth=0)
    s.map("TNotebook.Tab", background=[("selected", p.carte)], foreground=[("selected", p.texte)])

    s.configure("Barre.Horizontal.TProgressbar", background=p.accent, troughcolor=p.champ,
                bordercolor=p.bordure, lightcolor=p.accent, darkcolor=p.accent, thickness=10)

    s.configure("Treeview", background=p.champ, fieldbackground=p.champ, foreground=p.texte,
                borderwidth=0, rowheight=24)
    s.configure("Treeview.Heading", background=p.carte, foreground=p.doux, borderwidth=0,
                font=POLICE_PETITE)
    s.map("Treeview", background=[("selected", p.accent)], foreground=[("selected", p.sur_accent)])
    s.map("Treeview.Heading", background=[("active", p.bordure)])

    s.configure("TSeparator", background=p.bordure)
    s.configure("Vertical.TScrollbar", background=p.champ, troughcolor=p.fond,
                bordercolor=p.fond, arrowcolor=p.doux)
    s.map("Vertical.TScrollbar", background=[("active", p.bordure)])
    return p
