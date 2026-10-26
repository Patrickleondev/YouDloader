"""YouDloader web : la même mécanique, pilotée depuis un navigateur.

Pensé pour tourner en local (sur la machine ou dans Docker), pas sur Internet :
il n'y a ni comptes, ni quotas, et un service de téléchargement exposé publiquement
devient un relais ouvert pour n'importe qui.

    uvicorn web.serveur:app --host 127.0.0.1 --port 8080
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import sys
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from youdloader import core  # noqa: E402

# Dans Docker, /telechargements est monté sur un dossier de la machine hôte.
DEFAUT = "/telechargements" if os.name != "nt" else str(Path.home() / "Videos" / "YouDloader")
DOSSIER = Path(os.environ.get("YOUDLOADER_SORTIE", DEFAUT))

app = FastAPI(title="YouDloader", docs_url="/api")
STATIQUE = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIQUE), name="static")
TACHES: dict[str, dict] = {}


class DemandeAnalyse(BaseModel):
    url: str


class DemandeTelechargement(BaseModel):
    urls: list[str]
    audio_seul: bool = False
    hauteur: int | None = 360
    conteneur: str = "mp4"
    sous_titres: bool = False
    langue: str = "fr"
    debut: str | None = None
    fin: str | None = None
    coupe_precise: bool = True
    numeroter: bool = False
    elements: str = ""


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    return (STATIQUE / "index.html").read_text(encoding="utf-8")


@app.post("/api/analyser")
async def api_analyser(demande: DemandeAnalyse) -> dict:
    try:
        info = await asyncio.to_thread(core.analyser, demande.url)
    except Exception as erreur:
        raise HTTPException(status_code=400, detail=str(erreur)) from erreur
    info.pop("brut", None)  # dictionnaire yt-dlp complet : inutile et énorme côté client
    return info


@app.post("/api/telecharger")
async def api_telecharger(demande: DemandeTelechargement) -> dict:
    identifiant = uuid.uuid4().hex[:12]
    messages: queue.Queue = queue.Queue()
    TACHES[identifiant] = {"file": messages, "etat": "en cours", "fichiers": []}

    try:
        reglages = core.Reglages(
            urls=demande.urls,
            dossier=DOSSIER,
            audio_seul=demande.audio_seul,
            hauteur=demande.hauteur,
            conteneur=demande.conteneur,
            sous_titres=demande.sous_titres,
            langue=demande.langue,
            debut=core.lire_duree(demande.debut) if demande.debut else None,
            fin=core.lire_duree(demande.fin) if demande.fin else None,
            coupe_precise=demande.coupe_precise,
            numeroter=demande.numeroter,
            elements=demande.elements,
        )

        def progres(d: dict) -> None:
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                messages.put({
                    "type": "progres",
                    "pct": round(d.get("downloaded_bytes", 0) / total * 100, 1) if total else None,
                    "titre": (d.get("info_dict") or {}).get("title", ""),
                })
            elif d["status"] == "finished":
                nom = Path(d.get("filename", "")).name
                TACHES[identifiant]["fichiers"].append(nom)
                messages.put({"type": "fichier", "nom": nom})

        options = core.construire(reglages, hooks_progres=[progres])
    except core.ErreurReglages as erreur:
        raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def travail() -> None:
        code = core.telecharger(reglages, options)
        TACHES[identifiant]["etat"] = "terminé" if code == 0 else "erreur"
        messages.put({"type": "fin", "code": code})

    threading.Thread(target=travail, daemon=True).start()
    return {"tache": identifiant}


@app.get("/api/suivi/{identifiant}")
async def api_suivi(identifiant: str) -> StreamingResponse:
    """Flux d'événements : le navigateur suit l'avancement sans recharger la page."""
    tache = TACHES.get(identifiant)
    if tache is None:
        raise HTTPException(status_code=404, detail="tâche inconnue")

    async def flux():
        while True:
            try:
                message = await asyncio.to_thread(tache["file"].get, True, 30)
            except queue.Empty:
                yield ": ping\n\n"
                continue
            yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
            if message.get("type") == "fin":
                break

    return StreamingResponse(flux(), media_type="text/event-stream")


@app.get("/api/fichiers")
def api_fichiers() -> list[dict]:
    if not DOSSIER.exists():
        return []
    fichiers = [f for f in DOSSIER.rglob("*") if f.is_file() and f.name != "archive.txt"]
    fichiers.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"nom": str(f.relative_to(DOSSIER)), "taille": f.stat().st_size} for f in fichiers[:200]]


@app.get("/api/fichier/{chemin:path}")
def api_fichier(chemin: str) -> FileResponse:
    """Sert un fichier téléchargé. Le chemin est contraint au dossier de sortie."""
    cible = (DOSSIER / chemin).resolve()
    if not cible.is_file() or DOSSIER.resolve() not in cible.parents:
        raise HTTPException(status_code=404, detail="fichier introuvable")
    return FileResponse(cible, filename=cible.name)
