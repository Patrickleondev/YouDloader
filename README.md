# YouDloader

Téléchargeur de vidéos, de playlists, de pistes audio et d'extraits minutés.
Reprise du projet YouDloader de 2024 (l'identité et le logo sont conservés), sur un
moteur neuf : `pytube`, abandonné et cassé depuis, laisse la place à `yt-dlp`.

Trois façons de l'utiliser, un seul moteur commun dans `youdloader/core.py` :

| Version | Dossier | État |
|---|---|---|
| Bureau (Windows, .exe) | `youdloader/gui.py` | fonctionne |
| Ligne de commande | `youdloader/cli.py` | fonctionne |
| Web local (Docker) | `web/` | fonctionne |
| Android (.apk) | `android/` | à faire |

## Ce qu'il sait faire

- Une vidéo, une playlist entière, ou une liste de liens collés d'un coup.
- Vidéo + son, ou audio seul (m4a, mp3, opus, wav).
- Qualité au choix, 360p par défaut, jusqu'à la meilleure disponible.
- **Extrait minuté** : seulement de la 20e à la 40e minute, par exemple.
- Sous-titres (y compris ceux générés automatiquement), convertis en `.srt`.
- Numérotation des fichiers dans l'ordre des liens, pour garder l'ordre d'un cours.
- Reprise après coupure : relancer la même commande ne retélécharge pas l'existant.
- Thème sombre ou clair.

## Bureau

```powershell
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
venv\Scripts\python bureau.py          # lancer depuis les sources
venv\Scripts\python build_exe.py       # fabriquer dist\YouDloader.exe
```

L'exe fait environ 26 Mo et n'a besoin de rien d'installé, sauf ffmpeg.
S'il manque, l'application le télécharge elle-même dans
`%LOCALAPPDATA%\YouDloader\bin` : aucun droit administrateur, rien de modifié ailleurs
sur le système.

## Ligne de commande

```powershell
venv\Scripts\python -m youdloader.cli URL
venv\Scripts\python -m youdloader.cli URL_PLAYLIST -q 480 -n -s
venv\Scripts\python -m youdloader.cli URL --audio --format mp3
venv\Scripts\python -m youdloader.cli URL --de 20 --a 40      # 20e à 40e minute
venv\Scripts\python -m youdloader.cli -f liens.txt -o "D:\Cours"
venv\Scripts\python -m youdloader.cli --installer-ffmpeg
```

## Web local, dans Docker

```bash
docker compose up -d        # http://127.0.0.1:8080
docker compose logs -f
docker compose down
```

Les fichiers atterrissent dans `./telechargements`, monté dans le conteneur.
L'image embarque ffmpeg et Node, donc rien à installer sur la machine hôte.

Le port est volontairement lié à `127.0.0.1` : ce service n'a ni comptes ni quotas, et
l'exposer sur Internet en ferait un relais de téléchargement ouvert à tous.

## Pourquoi ces choix

**`format_sort: res:360` plutôt qu'un filtre `height<=360`.** Le filtre ne renvoie rien
si aucun flux n'est inférieur ou égal à 360p, et le téléchargement échoue. Le tri prend
la résolution la plus proche par en dessous, et à défaut la plus basse au-dessus.

**Pas d'archive quand on prend un extrait.** `archive.txt` note les vidéos terminées pour
ne pas les reprendre. Un extrait y inscrirait la vidéo comme faite, et la version
complète serait ignorée plus tard.

**Découpe avec réencodage par défaut.** Sans réencodage, la coupe tombe sur l'image clé
précédente, jusqu'à une dizaine de secondes avant la borne demandée. L'option de coupe
rapide reste disponible quand la précision importe peu.

**Node est nécessaire.** YouTube demande d'exécuter du JavaScript pour obtenir les flux ;
yt-dlp délègue à un moteur externe, ici Node.

## Limites connues

- Le mode extrait n'affiche pas de pourcentage : il passe par ffmpeg, qui ne communique
  pas de taille totale. La barre devient une animation d'attente.
- `--format m4a` sur une source Opus réencode, donc perd un peu de qualité.
- Les sous-titres automatiques de YouTube se trompent sur les termes techniques.

Télécharger du contenu protégé sans autorisation reste interdit par les conditions
d'utilisation de YouTube. Cet outil est fait pour les cours, les conférences et les
contenus libres.
