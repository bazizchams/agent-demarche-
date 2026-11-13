# Image de production durcie (non-root) — Plateforme Agent Bureau d'Études
#
# Contexte de construction : la racine du dépôt (voir docker-compose.production.yml, build.context: ..)
#
# Architecture :
# - Le serveur en ligne héberge l'API FastAPI, PostgreSQL, le stockage chiffré et, depuis
#   l'ajout du « navigateur de l'agent en ligne », un Chromium headless piloté par Playwright
#   (une session par bureau, vue et prise en main par l'opérateur dans l'interface web).
# - Chromium est installé dans l'image avec ses bibliothèques système (playwright install
#   --with-deps) et exécuté par l'utilisateur non-root « bureau ». Playwright lance Chromium
#   sans bac à sable interne par défaut : l'isolation repose sur le conteneur non-root,
#   no-new-privileges, les limites de ressources et le profil isolé par bureau.
# - Le navigateur n'est utilisé que si BE_NAVIGATEUR_SERVEUR_ACTIF=true (voir docker-compose et
#   docs/DEPLOIEMENT.md, section « Navigateur de l'agent en ligne »).
# - Image NON buildée à la date de rédaction (pas de Docker disponible) : syntaxe relue seulement.

FROM python:3.11-slim-bookworm

# Chromium dans un dossier lisible par l'utilisateur non-root, identique au build et à l'exécution.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /srv/plateforme/serveur

# Utilisateur non-root dédié. Seuls les dossiers de données appartiennent à « bureau » ;
# le code et la configuration restent en lecture seule pour cet utilisateur.
RUN groupadd --gid 10001 bureau && \
    useradd --uid 10001 --gid bureau --create-home --shell /usr/sbin/nologin bureau && \
    mkdir -p /srv/plateforme/donnees/documents_chiffres \
             /srv/plateforme/donnees/sauvegardes_chiffrees \
             /srv/plateforme/donnees/profils_navigateur && \
    chown -R bureau:bureau /srv/plateforme/donnees

# Fichiers de configuration métier YAML : lus par defaut via RACINE_PLATEFORME / "config"
# (app/core/config.py : dossier_demarches, dossier_portails).
COPY config/ /srv/plateforme/config/
COPY serveur/pyproject.toml serveur/alembic.ini ./
COPY serveur/alembic/ ./alembic/
COPY serveur/app/ ./app/

# Dépendances : `pip install .` lit serveur/pyproject.toml (dont httpx, playwright, PyYAML).
# Pilote PostgreSQL : l'URL BE_URL_BASE_DONNEES utilise `postgresql+psycopg://`, or pyproject.toml
# ne fournit PAS psycopg. Il est donc installé ici (binaire précompilé, aucune lib système requise).
RUN pip install --upgrade pip && \
    pip install . "psycopg[binary]>=3.1" && \
    rm -rf /srv/plateforme/serveur/bureau_etudes_serveur.egg-info /srv/plateforme/serveur/build
# NB : `pip install .` installe aussi une copie du paquet `app` dans site-packages, mais c'est le
# dossier courant (WORKDIR, ./app) qui est importé en premier par uvicorn, alembic et `python -m app.cli`.
# Ne pas changer le WORKDIR : app/core/config.py déduit de son emplacement ../../config (= /srv/plateforme/config).

# Chromium pour Playwright + dépendances système (exécuté en root, avant USER bureau).
# Polices : Liberation (métriques Arial/Times), Noto (latin, arabe, emoji) pour que les pages
# des portails s'affichent lisiblement dans les captures. Le cache apt est vidé pour garder l'image légère.
RUN mkdir -p "$PLAYWRIGHT_BROWSERS_PATH" && \
    python -m playwright install --with-deps chromium && \
    apt-get update && \
    apt-get install -y --no-install-recommends fonts-liberation fonts-noto-core fonts-noto-color-emoji && \
    rm -rf /var/lib/apt/lists/* && \
    chmod -R a+rX "$PLAYWRIGHT_BROWSERS_PATH"

USER bureau:bureau

# Dossier des profils de navigateur (un sous-dossier isolé par bureau) : volume dédié dans docker-compose.
# --disable-dev-shm-usage n'est pas nécessaire tant que le service dispose de shm_size: 1gb (compose).
VOLUME ["/srv/plateforme/donnees/profils_navigateur"]

EXPOSE 8000

# Contrôle de santé sans curl (absent de l'image slim) : appel de /api/v1/sante via Python.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/sante', timeout=4).status == 200 else 1)"

# Au démarrage : migrations Alembic (idempotentes) puis serveur.
# `exec` garantit que uvicorn reçoit les signaux d'arrêt (SIGTERM) de Docker.
# --forwarded-allow-ips '*' : seul Caddy atteint ce port (aucun port publié sur l'hôte).
# UN SEUL processus (pas de --workers) : limiteurs de débit et sessions de navigateur sont en mémoire du processus.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*'"]
