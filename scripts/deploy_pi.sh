#!/bin/bash
# Script de despliegue en Raspberry Pi 5
# Ejecutar como usuario con permisos docker (ej. pi o luis)

set -e

PROJECT_DIR="/home/luis/Proyectos/InvernaderoAuto"
cd "$PROJECT_DIR"

echo "=== Desplegando Invernadero Automatizado en Raspberry Pi 5 ==="

# 1. Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "Reinicia sesión y vuelve a ejecutar este script"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "Instalando Docker Compose plugin..."
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi

# 2. Crear directorios de datos
mkdir -p data/photos data/logs/nginx
chmod 700 data data/photos data/logs data/logs/nginx

# 3. Configurar .env si no existe
if [ ! -f .env ]; then
    cp .env.example .env
    # Generate every required secret. They are written to .env; the script
    # never prints a default password.
    JWT_KEY=$(openssl rand -hex 32)
    DEVICE_TOKEN=$(openssl rand -hex 32)
    ADMIN_PASS=$(openssl rand -base64 18 | tr -d '=+/')
    sed -i "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_KEY|" .env
    sed -i "s|DEVICE_API_TOKEN=.*|DEVICE_API_TOKEN=$DEVICE_TOKEN|" .env
    sed -i "s|ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$ADMIN_PASS|" .env
    chmod 600 .env
    echo "Secretos generados en .env (JWT, token de dispositivo y clave admin)."
fi

# Fail early instead of starting an API that will refuse to boot.
if ! grep -q '^JWT_SECRET_KEY=.\{16,\}' .env; then
    echo "❌ JWT_SECRET_KEY is missing or too short in .env" >&2
    exit 1
fi
if ! grep -q '^DEVICE_API_TOKEN=.\{16,\}' .env; then
    echo "❌ DEVICE_API_TOKEN is missing or too short in .env" >&2
    exit 1
fi
if ! grep -q '^ADMIN_PASSWORD=.\{12,\}' .env; then
    echo "❌ ADMIN_PASSWORD must be at least 12 characters in .env" >&2
    exit 1
fi

# 3b. Claves VAPID para las notificaciones de riego (Web Push).
if [ ! -f config/vapid_private.pem ] || [ ! -f config/vapid_public.pem ]; then
    bash scripts/generate_vapid_keys.sh
fi

# 4. Construir y levantar
compose_files=(-f docker-compose.yml)
if [ "${PRODUCTION:-0}" = "1" ]; then
  compose_files+=(-f docker-compose.production.yml)
  echo "Modo producción: TLS/túnel requerido (ver docs/deploy-public.md)."
fi

echo "Construyendo imágenes..."
docker compose "${compose_files[@]}" build --no-cache

echo "Levantando servicios..."
docker compose "${compose_files[@]}" up -d

# 5. Esperar a que estén listos
echo "Esperando servicios..."
sleep 10

# 6. Verificar
echo "Verificando salud..."
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "✅ API respondiendo"
else
    echo "❌ API no responde - revisa logs: docker compose ${compose_files[*]} logs api"
    exit 1
fi

if curl -sf http://localhost:5173 > /dev/null; then
    echo "✅ Frontend respondiendo"
else
    echo "❌ Frontend no responde - revisa logs: docker compose ${compose_files[*]} logs frontend"
    exit 1
fi

# 7. La base de datos se siembra automáticamente al arrancar la API
#    (usuarios por defecto, catálogo de cultivos y configuración activa).

echo ""
echo "=== Despliegue completado ==="
echo "UI: http://$(hostname -I | awk '{print $1}'):5173"
echo "API (solo loopback): http://127.0.0.1:8000"
echo "Usuario admin: ${ADMIN_USERNAME:-admin} (contraseña en .env -> ADMIN_PASSWORD)"
echo ""
echo "Importante: la instalación de la PWA y las notificaciones push requieren HTTPS."
echo "Ver docs/pwa-notificaciones.md (Tailscale Serve, Caddy o Cloudflare Tunnel)."
echo ""
echo "IMPORTANTE: guarda .env en un lugar seguro; no se muestran las claves."
echo "Logs: docker compose ${compose_files[*]} logs -f"
echo "Detener: docker compose ${compose_files[*]} down"