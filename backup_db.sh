#!/bin/bash
# Incremental SQLite backup: only saves a new snapshot if the DB changed
# since the last one for the given kind. Usage: backup_db.sh <kind> <retention_days>
set -euo pipefail

KIND="${1:?usage: backup_db.sh <daily|weekly> <retention_days>}"
RETENTION_DAYS="${2:?usage: backup_db.sh <daily|weekly> <retention_days>}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$REPO_DIR/backups/$KIND"
mkdir -p "$BACKUP_DIR"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

docker compose -f "$REPO_DIR/docker-compose.yml" exec -T mangashelf python3 -c "
import sqlite3
src = sqlite3.connect('/code/data/mangashelf.db')
dst = sqlite3.connect('/tmp/_backup_tmp.db')
src.backup(dst)
dst.close()
src.close()
"
docker compose -f "$REPO_DIR/docker-compose.yml" cp mangashelf:/tmp/_backup_tmp.db "$TMP"
docker compose -f "$REPO_DIR/docker-compose.yml" exec -T mangashelf rm -f /tmp/_backup_tmp.db

NEW_HASH="$(sha256sum "$TMP" | cut -d' ' -f1)"
LATEST="$(ls -1 "$BACKUP_DIR"/mangashelf-*.db 2>/dev/null | sort | tail -n1 || true)"

if [ -n "$LATEST" ] && [ "$(sha256sum "$LATEST" | cut -d' ' -f1)" = "$NEW_HASH" ]; then
    echo "[$KIND] No changes since last backup — skipping."
    exit 0
fi

DEST="$BACKUP_DIR/mangashelf-$(date +%Y-%m-%d).db"
cp "$TMP" "$DEST"
echo "[$KIND] Saved $DEST"

find "$BACKUP_DIR" -name "mangashelf-*.db" -mtime "+$RETENTION_DAYS" -delete
