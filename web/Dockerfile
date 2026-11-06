# Image de la version web de YouDloader. Elle embarque ses deux dépendances système :
# ffmpeg (fusion, conversion, découpe) et Node (YouTube exige d'exécuter du JavaScript).
FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Le paquet nodejs de Debian est en version 20, et yt-dlp exige Node 22 au moins :
# il ignorerait ce Node-là. On prend le binaire de l'image officielle.
COPY --from=node:24-slim /usr/local/bin/node /usr/local/bin/node

WORKDIR /app
COPY web/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY youdloader/ ./youdloader/
COPY web/ ./web/

ENV YOUDLOADER_SORTIE=/telechargements
VOLUME ["/telechargements"]
EXPOSE 8080

# 127.0.0.1 côté hôte : le service n'est pas fait pour être exposé sur Internet.
CMD ["uvicorn", "web.serveur:app", "--host", "0.0.0.0", "--port", "8080"]
