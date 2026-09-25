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
mkdir -p data/photos
chmod 755 data data/photos

# 3. Configurar .env si no existe
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Edita .env con tus valores (JWT_SECRET_KEY, etc.)"
    # Generar JWT_SECRET_KEY seguro
    JWT_KEY=$(openssl rand -hex 32)
    sed -i "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_KEY|" .env
    echo "JWT_SECRET_KEY generado automáticamente"
fi

# 4. Construir y levantar
echo "Construyendo imágenes..."
docker compose build --no-cache

echo "Levantando servicios..."
docker compose up -d

# 5. Esperar a que estén listos
echo "Esperando servicios..."
sleep 10

# 6. Verificar
echo "Verificando salud..."
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "✅ API respondiendo"
else
    echo "❌ API no responde - revisa logs: docker compose logs api"
    exit 1
fi

if curl -sf http://localhost:5173 > /dev/null; then
    echo "✅ Frontend respondiendo"
else
    echo "❌ Frontend no responde - revisa logs: docker compose logs frontend"
    exit 1
fi

# 7. La base de datos se siembra automáticamente al arrancar la API
#    (usuarios por defecto, catálogo de cultivos y configuración activa).

echo ""
echo "=== Despliegue completado ==="
echo "UI: http://$(hostname -I | awk '{print $1}'):5173"
echo "API: http://$(hostname -I | awk '{print $1}'):8000"
echo "Usuario admin: admin / admin123"
echo "Usuario viewer: viewer / viewer123"
echo ""
echo "IMPORTANTE: cambia las contraseñas por defecto en el primer inicio."
echo "Logs: docker compose logs -f"
echo "Detener: docker compose down"