# Installer YouDloader

Trois façons de l'utiliser, au choix. La première ne demande rien d'autre que Windows.

- [Windows, l'exécutable](#windows-lexécutable) : le plus simple
- [Docker, la version web](#docker-la-version-web) : accessible depuis le navigateur
- [Depuis les sources](#depuis-les-sources) : pour modifier le code

---

## Windows, l'exécutable

1. Ouvrir la page [Releases](https://github.com/Patrickleondev/YouDloader/releases).
2. Télécharger `YouDloader.exe` de la version la plus récente.
3. Double-cliquer.

Il n'y a rien à installer : pas de Python, pas de dépendances, aucun accès administrateur.

### Windows affiche un avertissement, c'est normal

> **Windows a protégé votre ordinateur** – Microsoft Defender SmartScreen a empêché
> le démarrage d'une application non reconnue.

L'exécutable n'est pas signé, et une signature de code coûte quelques centaines d'euros
par an. SmartScreen prévient donc pour tout programme qu'il ne connaît pas encore.

Pour lancer quand même : **Informations complémentaires**, puis **Exécuter quand même**.

Avant de cliquer, tu peux vérifier que le fichier est bien celui publié. Compare la
sortie de cette commande avec le contenu de `SHA256SUMS.txt`, joint à la release :

```powershell
Get-FileHash .\YouDloader.exe -Algorithm SHA256
```

Si les deux empreintes diffèrent, n'exécute pas le fichier : il a été modifié en chemin.

### Un antivirus peut aussi réagir

Les exécutables produits par PyInstaller déclenchent régulièrement de fausses alertes,
parce que leur façon de déballer le code en mémoire ressemble à celle de certains
logiciels malveillants. Si ton antivirus met le fichier en quarantaine, l'empreinte
ci-dessus est le bon moyen de trancher, puis une exception sur le fichier.

### ffmpeg

ffmpeg est nécessaire pour trois choses : fusionner l'image et le son (YouTube les sert
séparément au-dessus de 360p), convertir l'audio, et découper un extrait.

L'application le cherche d'abord sur la machine. S'il manque, un bandeau le signale en
haut de la fenêtre et l'outil peut le télécharger lui-même dans
`%LOCALAPPDATA%\YouDloader\bin`. Rien n'est écrit ailleurs, aucun droit administrateur
n'est demandé, et le désinstaller revient à supprimer ce dossier.

Pour l'installer à la main, au choix :

```powershell
winget install Gyan.FFmpeg
```

### Où vont les fichiers

| Quoi | Où |
|---|---|
| Vidéos téléchargées | le dossier choisi dans la fenêtre, `%USERPROFILE%\Videos\YouDloader` par défaut |
| Réglages mémorisés | `%APPDATA%\YouDloader\config.json` |
| ffmpeg installé par l'outil | `%LOCALAPPDATA%\YouDloader\bin` |

Pour tout désinstaller : supprimer l'exe et ces deux dossiers.

---

## Docker, la version web

Utile pour piloter l'outil depuis le navigateur, y compris depuis un téléphone sur le
même réseau. L'image embarque ffmpeg et Node, donc la machine hôte n'a besoin de rien.

Il faut [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows,
macOS) ou Docker Engine (Linux), **démarré**.

```bash
git clone https://github.com/Patrickleondev/YouDloader.git
cd YouDloader
docker compose up -d
```

Puis ouvrir http://127.0.0.1:8080.

| Commande | Effet |
|---|---|
| `docker compose logs -f` | suivre ce qui se passe |
| `docker compose down` | arrêter |
| `docker compose up -d --build` | reconstruire après une mise à jour du code |

Les fichiers téléchargés arrivent dans `./telechargements`, sur la machine hôte.

**Ne pas supprimer ce dossier pendant que le conteneur tourne** : le montage pointerait
dans le vide et tout téléchargement échouerait jusqu'à un `docker compose restart`.

### Pourquoi le port est limité à 127.0.0.1

`docker-compose.yml` publie `127.0.0.1:8080:8080`, donc le service n'est joignable que
depuis la machine elle-même. Ce service n'a ni comptes, ni mots de passe, ni quotas :
exposé sur Internet, il deviendrait un relais de téléchargement utilisable par n'importe
qui, à ton nom et sur ta connexion.

Pour y accéder depuis ton téléphone **sur ton réseau local**, remplace cette ligne par
`"8080:8080"` et ouvre `http://IP_DE_TON_PC:8080`. À ne faire que sur un réseau de
confiance, jamais sur un Wi-Fi public ni derrière une redirection de port.

---

## Depuis les sources

Pour modifier le code, ou pour utiliser la ligne de commande.

Il faut Python 3.11 ou plus récent.

```powershell
git clone https://github.com/Patrickleondev/YouDloader.git
cd YouDloader
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
```

Lancer l'interface :

```powershell
venv\Scripts\python bureau.py
```

Lancer en ligne de commande :

```powershell
venv\Scripts\python -m youdloader.cli URL
venv\Scripts\python -m youdloader.cli URL --de 20 --a 40      # 20e à 40e minute
venv\Scripts\python -m youdloader.cli URL --audio --format mp3
venv\Scripts\python -m youdloader.cli -f liens.txt -o "D:\Cours" -n -s
venv\Scripts\python -m youdloader.cli --installer-ffmpeg
```

Fabriquer l'exécutable :

```powershell
venv\Scripts\python build_exe.py
```

Le résultat est dans `dist\YouDloader.exe`.

---

## Quand ça ne marche pas

**« ffmpeg introuvable » alors qu'il est installé.** Il n'est pas dans le `PATH`. Ouvre
un nouveau terminal après l'installation, ou laisse l'outil installer sa propre copie.

**Une vidéo YouTube échoue avec une erreur d'extraction.** YouTube change régulièrement,
et yt-dlp suit. Mets-le à jour :

```powershell
venv\Scripts\python -m pip install -U "yt-dlp[default]"
```

Avec l'exécutable, il faut récupérer une version plus récente dans les Releases : la
bibliothèque est figée à l'intérieur de l'exe.

**Rien ne se télécharge, les erreurs parlent de DNS ou de certificat.** Typique d'un
Wi-Fi à portail captif, comme sur un campus : ouvre une page web, accepte le portail,
réessaie.

**« Nous n'avons pas pu vérifier que vous n'êtes pas un robot ».** La vidéo exige un
compte. Choisis ton navigateur dans **Cookies du navigateur** pour que l'outil réutilise
ta session. Le navigateur doit être fermé pendant la lecture des cookies sur Chrome.

**Le port 8080 est déjà pris.** Change la ligne de `docker-compose.yml` en
`"127.0.0.1:8090:8080"` et utilise http://127.0.0.1:8090.

**Le mode extrait n'affiche pas de pourcentage.** C'est attendu : la découpe passe par
ffmpeg, qui ne communique pas de taille totale. La barre devient une animation d'attente
jusqu'à la fin.
