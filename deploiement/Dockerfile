# Image de production durcie (non-root) — Plateforme Agent Bureau d'Études (Phase 6)
# Remarque architecture : Le serveur en ligne héberge uniquement l'API, la base PostgreSQL
# et le stockage chiffré AES-256-GCM. L'automatisation Playwright s'exécute exclusivement
# sur le PC Windows local de chaque bureau d'études (jamais depuis le datacenter).

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/plateforme/serveur

RUN groupadd --gid 10001 bureau && \
    useradd --uid 10001 --gid bureau --create-home --shell /usr/sbin/nologin bureau && \
    mkdir -p /srv/plateforme/donnees/documents_chiffres \
             /srv/plateforme/donnees/sauvegardes_chiffrees \
             /srv/plateforme/configuration && \
    chown -R bureau:bureau /srv/plateforme

COPY configuration/ /srv/plateforme/configuration/
COPY serveur/pyproject.toml /srv/plateforme/serveur/pyproject.toml
COPY serveur/alembic.ini /srv/plateforme/serveur/alembic.ini
COPY serveur/alembic/ /srv/plateforme/serveur/alembic/
COPY serveur/app/ /srv/plateforme/serveur/app/

RUN pip install --upgrade pip && \
    pip install .

USER bureau:bureau

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
