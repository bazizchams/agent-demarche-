#!/usr/bin/env bash
# Restauration testable des sauvegardes produites par sauvegarde.sh.
#
# NON EXÉCUTÉ à la date de rédaction (pas de Docker) : à valider sur un serveur de test AVANT la mise en service.
#
#   bash restauration.sh verifier  base_AAAA-MM-JJ_HHMM.dump [documents_AAAA-MM-JJ_HHMM.tar.gz]
#       Sans risque pour la production : restaure la base dans une base TEMPORAIRE « restauration_test »,
#       compte les tables, lit la version Alembic, contrôle l'archive de documents, puis supprime la base temporaire.
#
#   bash restauration.sh appliquer base_AAAA-MM-JJ_HHMM.dump documents_AAAA-MM-JJ_HHMM.tar.gz
#       DESTRUCTIF : remplace la base et les documents actuels (confirmation : taper RESTAURER). À utiliser sur un
#       serveur neuf ou après incident, avec LA MÊME clé BE_CLE_MAITRESSE_BASE64 dans .env.production.
set -euo pipefail
umask 077

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FICHIER_ENV="$DIR/.env.production"
[ -f "$FICHIER_ENV" ] || { echo "Fichier $FICHIER_ENV introuvable." >&2; exit 1; }
COMPOSE=(docker compose --env-file "$FICHIER_ENV" -f "$DIR/docker-compose.production.yml")
DOSSIER_DOCS=/srv/plateforme/donnees/documents_chiffres
BASE_TEST=restauration_test

usage() { sed -n '2,12p' "$0" >&2; exit 2; }
[ $# -ge 2 ] || usage
MODE="$1"; DUMP="$2"; DOCS="${3:-}"
[ -r "$DUMP" ] || { echo "Fichier illisible : $DUMP" >&2; exit 1; }
[ -z "$DOCS" ] || [ -r "$DOCS" ] || { echo "Fichier illisible : $DOCS" >&2; exit 1; }

# Exécute une commande dans le conteneur postgres (stdin transmis).
pg() { "${COMPOSE[@]}" exec -T postgres "$@"; }

# Vérifie la somme de contrôle si un fichier sha256_*.txt du même dossier la contient.
verifier_somme() {
  local dossier nom
  dossier="$(dirname "$1")"; nom="$(basename "$1")"
  if grep -qs " $nom\$" "$dossier"/sha256_*.txt 2>/dev/null; then
    ( cd "$dossier" && grep -hs " $nom\$" sha256_*.txt | sha256sum -c - )
  else
    echo "Aucune somme de contrôle trouvée pour $nom (ignoré)."
  fi
}

supprimer_base_test() {
  pg sh -c "dropdb -U \"\$POSTGRES_USER\" --if-exists $BASE_TEST" > /dev/null 2>&1 || true
}

verifier() {
  verifier_somme "$DUMP"
  echo "Restauration de test dans la base temporaire $BASE_TEST ..."
  supprimer_base_test
  pg sh -c "createdb -U \"\$POSTGRES_USER\" $BASE_TEST"
  trap supprimer_base_test EXIT   # la base temporaire disparaît quoi qu'il arrive
  pg sh -c "pg_restore -U \"\$POSTGRES_USER\" -d $BASE_TEST --no-owner --exit-on-error" < "$DUMP"
  local tables version
  tables="$(pg sh -c "psql -U \"\$POSTGRES_USER\" -d $BASE_TEST -tAc \"select count(*) from information_schema.tables where table_schema='public'\"" | tr -d '[:space:]')"
  version="$(pg sh -c "psql -U \"\$POSTGRES_USER\" -d $BASE_TEST -tAc 'select version_num from alembic_version'" | tr -d '[:space:]')"
  echo "Tables restaurées : $tables ; version Alembic : $version"
  if [ "${tables:-0}" -lt 10 ] || [ -z "$version" ]; then
    echo "ÉCHEC : base restaurée incomplète." >&2
    exit 1
  fi
  if [ -n "$DOCS" ]; then
    verifier_somme "$DOCS"
    echo "Documents : $(gzip -dc "$DOCS" | tar -t | grep -vc '/$' || true) fichier(s) dans l'archive."
  fi
  echo "OK : la sauvegarde est restaurable (base temporaire supprimée)."
}

appliquer() {
  [ -n "$DOCS" ] || { echo "Le mode « appliquer » exige aussi l'archive de documents." >&2; exit 2; }
  verifier_somme "$DUMP"; verifier_somme "$DOCS"
  read -r -p "Ceci REMPLACE la base et les documents actuels. Tapez RESTAURER pour continuer : " reponse
  [ "$reponse" = "RESTAURER" ] || { echo "Annulé."; exit 1; }
  "${COMPOSE[@]}" up -d postgres
  "${COMPOSE[@]}" stop serveur caddy
  pg sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
  pg sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < "$DUMP"
  # Documents : conteneur serveur éphémère (utilisateur « bureau », propriétaire du volume).
  "${COMPOSE[@]}" run --rm --no-deps -T --entrypoint sh serveur -c \
    "find $DOSSIER_DOCS -mindepth 1 -delete && tar xzf - -C $DOSSIER_DOCS" < "$DOCS"
  "${COMPOSE[@]}" up -d
  echo "Restauration terminée. Contrôlez les journaux du serveur puis connectez-vous à l'interface."
}

case "$MODE" in
  verifier) verifier ;;
  appliquer) appliquer ;;
  *) usage ;;
esac
