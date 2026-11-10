#!/usr/bin/env bash
# Periodic backup of the SQLite database and photos.
#
# Cron example (daily at 02:15):
#   15 2 * * * /home/luis/Proyectos/InvernaderoAuto/scripts/backup.sh >> /var/log/greenhouse-backup.log 2>&1
set -euo pipefail
umask 077

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
data_dir="${DATA_DIR:-$project_dir/data}"
backup_dir="${BACKUP_DIR:-$project_dir/backups}"
keep="${BACKUP_KEEP:-14}"
db="$data_dir/greenhouse.db"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
work="$backup_dir/$stamp"

mkdir -p "$work"
chmod 700 "$backup_dir" "$work"

if [ -f "$db" ]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    # .backup is safe while the API is writing. TRUNCATE keeps the WAL small.
    sqlite3 "$db" ".backup '$work/greenhouse.db'"
    sqlite3 "$work/greenhouse.db" "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;"
  else
    cp "$db" "$work/greenhouse.db"
    [ -f "$db-wal" ] && cp "$db-wal" "$work/greenhouse.db-wal"
    [ -f "$db-shm" ] && cp "$db-shm" "$work/greenhouse.db-shm"
  fi
fi

if [ -d "$data_dir/photos" ]; then
  tar -C "$data_dir" -czf "$work/photos.tar.gz" photos
fi

cat > "$work/MANIFEST.txt" <<EOF
created_utc=$stamp
host=$(hostname)
database_bytes=$(stat -c%s "$work/greenhouse.db" 2>/dev/null || echo 0)
EOF

# Keep only the newest $keep backups.
find "$backup_dir" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
  | sort -rn | tail -n +"$((keep + 1))" | cut -d' ' -f2- \
  | while read -r old; do rm -rf "$old"; done

echo "$stamp backup complete -> $work"
