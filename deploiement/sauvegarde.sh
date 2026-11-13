#!/usr/bin/env bash
# Sauvegarde complète quotidienne : base PostgreSQL (pg_dump) + documents chiffrés.
#
# NON EXÉCUTÉ à la date de rédaction (pas de Docker sur le poste de développement) : à valider sur un serveur
# de test avec `restauration.sh verifier` (voir docs/DEPLOIEMENT.md, section 7).
#
# Utilisation :   bash /opt/agent-bureau/plateforme/deploiement/sauvegarde.sh
# Planification (cron, 02h30 chaque nuit) :
#   30 2 * * * /bin/bash /opt/agent-bureau/plateforme/deploiement/sauvegarde.sh >> /var/log/agent-bureau-sauvegarde.log 2>&1
#
# Ce script NE sauvegarde PAS : la clé maîtresse (BE_CLE_MAITRESSE_BASE64) — à garder hors serveur, sans elle les
# sauvegardes sont illisibles — ni les profils de navigateur (cookies de session des portails : secrets, exclus).
# Cohérence : base et documents sont copiés l'un après l'autre (pas d'instantané atomique) ; un document ajouté
# entre les deux copies peut manquer à la restauration. Lancer la nuit limite ce risque.
set -euo pipefail
umask 077

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FICHIER_ENV="$DIR/.env.production"
[ -f "$FICHIER_ENV" ] || { echo "Fichier $FICHIER_ENV introuvable." >&2; exit 1; }
COMPOSE=(docker compose --env-file "$FICHIER_ENV" -f "$DIR/docker-compose.production.yml")

# Lecture ciblée de quelques clés (le fichier contient des valeurs <entre-chevrons> : on ne le « source » pas).
lire_env() { grep -E "^$1=" "$FICHIER_ENV" | tail -n1 | cut -d= -f2- || true; }
DEST="${DEST_SAUVEGARDES:-$(lire_env DEST_SAUVEGARDES)}";    DEST="${DEST:-/opt/sauvegardes}"
RETENTION="${RETENTION_JOURS:-$(lire_env RETENTION_JOURS)}"; RETENTION="${RETENTION:-14}"
COPIE="${COPIE_DISTANTE_RSYNC:-$(lire_env COPIE_DISTANTE_RSYNC)}"
[[ "$RETENTION" =~ ^[0-9]+$ ]] || { echo "RETENTION_JOURS invalide : $RETENTION" >&2; exit 1; }

mkdir -p "$DEST"
HORODATAGE="$(date +%F_%H%M)"
BASE="$DEST/base_${HORODATAGE}.dump"
DOCS="$DEST/documents_${HORODATAGE}.tar.gz"
nettoyer() { rm -f "$BASE.partiel" "$DOCS.partiel"; }
trap nettoyer EXIT

echo "[$(date -Is)] Sauvegarde de la base..."
# Format « custom » (-Fc) : compressé, restaurable avec pg_restore. Écriture dans un .partiel puis renommage.
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BASE.partiel"
# Vérification : l'archive doit être lisible par pg_restore (sinon on échoue avant de purger les anciennes).
"${COMPOSE[@]}" exec -T postgres pg_restore -l < "$BASE.partiel" > /dev/null
mv "$BASE.partiel" "$BASE"

echo "[$(date -Is)] Sauvegarde des documents chiffrés..."
# Flux tar depuis le conteneur serveur : indépendant du nom des volumes. Fichiers déjà chiffrés (AES-256-GCM).
"${COMPOSE[@]}" exec -T serveur tar czf - -C /srv/plateforme/donnees/documents_chiffres . > "$DOCS.partiel"
gzip -t "$DOCS.partiel"
mv "$DOCS.partiel" "$DOCS"

( cd "$DEST" && sha256sum "$(basename "$BASE")" "$(basename "$DOCS")" > "sha256_${HORODATAGE}.txt" )

echo "[$(date -Is)] Purge des sauvegardes de plus de ${RETENTION} jours..."
find "$DEST" -maxdepth 1 -type f \( -name 'base_*.dump' -o -name 'documents_*.tar.gz' -o -name 'sha256_*.txt' \) \
  -mtime "+${RETENTION}" -print -delete

if [ -n "$COPIE" ]; then
  echo "[$(date -Is)] Copie distante (rsync) vers $COPIE ..."
  rsync -a --partial -- "$BASE" "$DOCS" "$DEST/sha256_${HORODATAGE}.txt" "$COPIE"
else
  echo "ATTENTION : aucune copie distante (COPIE_DISTANTE_RSYNC). Une sauvegarde sur le même serveur ne protège pas de sa perte." >&2
fi

echo "[$(date -Is)] Terminé : $BASE et $DOCS"
