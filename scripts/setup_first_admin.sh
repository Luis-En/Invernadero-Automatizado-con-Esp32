#!/usr/bin/env bash
# Create or repair the first administrator with role=admin.
#
#   ADMIN_USERNAME=admin ADMIN_PASSWORD='...' bash scripts/setup_first_admin.sh
#
# If the password is omitted the script prompts for it without echoing. It
# validates the same minimum length as the API (12 characters).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

USERNAME="${ADMIN_USERNAME:-admin}"
EMAIL="${ADMIN_EMAIL:-${USERNAME}@local}"
PASSWORD="${ADMIN_PASSWORD:-}"

if [[ -z "$PASSWORD" ]]; then
  read -r -s -p "Contraseña para '$USERNAME': " PASSWORD
  echo
  read -r -s -p "Repite la contraseña: " PASSWORD_CONFIRM
  echo
  if [[ "$PASSWORD" != "$PASSWORD_CONFIRM" ]]; then
    echo "Las contraseñas no coinciden." >&2
    exit 1
  fi
fi

if [[ ${#PASSWORD} -lt 12 ]]; then
  echo "ADMIN_PASSWORD debe tener al menos 12 caracteres." >&2
  exit 1
fi

if ! docker compose ps --services --filter status=running | grep -qx 'api'; then
  echo "La API no está en ejecución. Levántala con: docker compose up -d api" >&2
  exit 1
fi

docker compose exec -T \
  -e SETUP_USERNAME="$USERNAME" \
  -e SETUP_EMAIL="$EMAIL" \
  -e SETUP_PASSWORD="$PASSWORD" \
  api python - <<'PY'
import asyncio
import os

from sqlalchemy import select

from app.auth import get_password_hash
from app.database import AsyncSessionLocal
from app.models import User
from app.password_policy import validate_password_strength


async def main() -> None:
    username = os.environ["SETUP_USERNAME"]
    email = os.environ["SETUP_EMAIL"]
    password = os.environ["SETUP_PASSWORD"]

    errors = validate_password_strength(password, username)
    if errors:
        raise SystemExit("Contraseña no válida: " + "; ".join(errors))

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                username=username,
                email=email or None,
                hashed_password=get_password_hash(password),
                role="admin",
                is_active=True,
            )
            db.add(user)
            action = "created"
        else:
            user.hashed_password = get_password_hash(password)
            user.role = "admin"
            user.is_active = True
            if email:
                user.email = email
            action = "updated"
        await db.commit()
        print(f"Administrador '{username}' {action} con rol admin.")


asyncio.run(main())
PY

echo "Listo. Inicia sesión en /admin/login."
