#!/bin/sh
# Sauvegarde la base SQLite du bot (copie cohérente) dans ~/backups, garde les 14 dernières.
# À lancer depuis la machine qui héberge le bot : sh deploy/backup.sh
set -eu
cd "$(dirname "$0")/.."
DIR="${BACKUP_DIR:-$HOME/backups}"
mkdir -p "$DIR"
STAMP=$(date +%Y%m%d-%H%M%S)

# Copie à chaud avec l'API de sauvegarde de SQLite (sûre même si une partie est en cours)
docker compose exec -T bot python -c "
import sqlite3
src = sqlite3.connect('/app/storage/undercover.db')
dst = sqlite3.connect('/app/storage/backup.db')
src.backup(dst)
dst.close(); src.close()
"
docker compose cp bot:/app/storage/backup.db "$DIR/undercover-$STAMP.db"
docker compose exec -T bot rm -f /app/storage/backup.db

# Ne garde que les 14 sauvegardes les plus récentes
ls -1t "$DIR"/undercover-*.db | tail -n +15 | xargs -r rm -f
echo "Sauvegarde : $DIR/undercover-$STAMP.db"
