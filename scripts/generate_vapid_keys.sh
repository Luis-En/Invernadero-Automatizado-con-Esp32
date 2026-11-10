#!/usr/bin/env bash
# Generate the VAPID key pair used by Web Push.
#
#   bash scripts/generate_vapid_keys.sh
#
# The files land in config/ (mounted into the API container as /app/config)
# and are ignored by git. Re-run with FORCE=1 only to rotate the keys; every
# existing phone subscription must be re-created after rotating.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${1:-$ROOT_DIR/config}"
PRIVATE_KEY="$CONFIG_DIR/vapid_private.pem"
PUBLIC_KEY="$CONFIG_DIR/vapid_public.pem"

mkdir -p "$CONFIG_DIR"

if [[ -f "$PRIVATE_KEY" && "${FORCE:-0}" != "1" ]]; then
  echo "Ya existen claves VAPID en $CONFIG_DIR (usa FORCE=1 para rotarlas)."
  exit 0
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl no está instalado." >&2
  exit 1
fi

umask 077
TMP_KEY="$(mktemp)"
trap 'rm -f "$TMP_KEY"' EXIT

# P-256 is the curve required by Web Push. PKCS#8 keeps pywebpush happy.
openssl ecparam -name prime256v1 -genkey -noout -out "$TMP_KEY"
openssl pkcs8 -topk8 -nocrypt -in "$TMP_KEY" -out "$PRIVATE_KEY"
openssl ec -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY" 2>/dev/null

chmod 600 "$PRIVATE_KEY"
chmod 644 "$PUBLIC_KEY"

echo "Claves VAPID creadas:"
echo "  privada: $PRIVATE_KEY"
echo "  pública: $PUBLIC_KEY"
echo
echo "La API las detecta automáticamente. Reinicia el servicio:"
echo "  docker compose up -d --build api"
