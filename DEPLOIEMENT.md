# Publier une version

Qui lit ce document : la personne qui maintient le dépôt. Les utilisateurs, eux,
ont besoin de [INSTALL.md](INSTALL.md).

## En une commande

```powershell
venv\Scripts\python scripts\publier.py --publier
```

Le script refuse de travailler sur un arbre git sale, construit l'exe, calcule son
empreinte SHA-256, pose l'étiquette `vX.Y.Z`, pousse, puis crée la release GitHub avec
l'exe et `SHA256SUMS.txt` en pièces jointes.

Sans `--publier`, il s'arrête juste avant de publier : c'est le mode à utiliser pour
vérifier ce qui sortirait.

## Avant de lancer

1. **Le numéro de version** vit à un seul endroit, dans `youdloader/__init__.py` :

   ```python
   __version__ = "2.0.0"
   ```

   MAJEUR quand un réglage existant change de sens, MINEUR pour une fonction en plus,
   CORRECTIF pour une correction seule.

2. **Tout doit être commité.** Le script s'arrête sinon, pour éviter de publier un exe
   construit à partir de code absent du dépôt.

3. **`gh` doit être connecté** :

   ```powershell
   gh auth status
   gh auth login      # si besoin, demande un code dans le navigateur
   ```

4. **Tester l'exe avant de le publier.** Le construire sans publier, le lancer, faire un
   vrai téléchargement et un extrait :

   ```powershell
   venv\Scripts\python scripts\publier.py
   .\dist\YouDloader.exe
   ```

## Pourquoi la publication se fait en local

GitHub Actions ne démarre pas sur ce compte depuis septembre 2026, pour un blocage de
facturation. Le workflow `.github/workflows/exe.yml` est pourtant prêt : il construit
l'exe et le joint à la release dès qu'une étiquette `v*` est poussée. Le jour où le
compte est débloqué, il n'y a rien à écrire, seulement à vérifier que le job démarre.

En attendant, `scripts/publier.py` fait le même travail depuis ta machine.

## Publier l'image Docker (facultatif)

Utile seulement si tu veux que quelqu'un lance la version web sans cloner le dépôt.

```powershell
docker build -t ghcr.io/patrickleondev/youdloader:2.0.0 -f web/Dockerfile .
docker tag ghcr.io/patrickleondev/youdloader:2.0.0 ghcr.io/patrickleondev/youdloader:latest
echo $env:GHCR_TOKEN | docker login ghcr.io -u Patrickleondev --password-stdin
docker push ghcr.io/patrickleondev/youdloader:2.0.0
docker push ghcr.io/patrickleondev/youdloader:latest
```

`GHCR_TOKEN` est un jeton personnel GitHub avec la portée `write:packages`. Le paquet
publié est privé par défaut : le rendre public se fait depuis la page du paquet.

## Liste de contrôle

- [ ] `__version__` à jour dans `youdloader/__init__.py`
- [ ] README et INSTALL relus si le comportement a changé
- [ ] Tout commité, rien en attente
- [ ] Exe construit et réellement lancé
- [ ] Un téléchargement complet et un extrait testés avec cet exe
- [ ] `python scripts/publier.py --publier`
- [ ] La page Releases affiche l'exe et l'empreinte
- [ ] L'exe téléchargé depuis la release se lance sur une autre machine si possible

## Ce qui n'est pas publié

`dist/`, `build/`, `venv/` et `telechargements/` sont exclus par `.gitignore`. Un binaire
de 26 Mo n'a pas sa place dans l'historique git : il gonfle le dépôt pour toujours, et se
régénère à l'identique avec `build_exe.py`. Sa place est dans les pièces jointes d'une
release.
