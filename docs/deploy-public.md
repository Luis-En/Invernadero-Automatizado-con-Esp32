# Despliegue público con túnel (v2)

Esta guía publica el invernadero en lectura para cualquiera y deja el control
bajo `/admin/*` con sesión y rol `admin`.

## Arquitectura

| Ruta | Acceso | Contenido |
|------|--------|-----------|
| `/` | Público | Dashboard en vivo (`/api/public/*`) |
| `/fotos` | Público | Galería |
| `/clima` | Público | Pronóstico |
| `/admin/login` | Público (formulario) | Login de administrador |
| `/admin` | Rol admin | Control de actuadores, eventos, historial |
| `/admin/cultivos` | Rol admin | CRUD de cultivos |
| `/admin/configuracion` | Rol admin | Configuración e histeresis |
| `/admin/logs` | Rol admin | Auditoría |
| `/admin/usuarios` | Rol admin | Altas de usuarios y roles |

La API pública solo expone datos redactados: no incluye `device_id`, RSSI,
secuencia, notas internas ni rutas de archivos. Las escrituras viven en
`/api/admin/*` y exigen rol `admin`.

## 1. Requisitos

- Docker + Compose.
- Un túnel o proxy con TLS: Tailscale Serve, Caddy, Cloudflare Tunnel o Dokploy.
- El proxy debe enviar `X-Forwarded-Proto: https` al contenedor. Si no, la API
  responde `403 HTTPS requerido` y Nginx redirige a HTTPS.

Para una guía concreta con Dokploy y Cloudflare Tunnel:
**[deploy-dokploy-cloudflare.md](deploy-dokploy-cloudflare.md)**.

## 2. Variables

Copia `.env.example` a `.env` y rellena:

```bash
ENVIRONMENT=production
AUTH_COOKIE_SECURE=true
REQUIRE_HTTPS=true
PUBLIC_BASE_URL=https://invernadero.example.com
CORS_ORIGINS=["https://invernadero.example.com"]
TRUSTED_PROXIES=127.0.0.1/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,100.64.0.0/10,::1/128
ADMIN_PASSWORD=una-contraseña-de-12-o-más
JWT_SECRET_KEY=<openssl rand -hex 32>
DEVICE_API_TOKEN=<openssl rand -hex 32>
```

`docker-compose.production.yml` ya fija `ENVIRONMENT`, `AUTH_COOKIE_SECURE`,
`REQUIRE_HTTPS`, `ENABLE_DOCS=false`, `RATE_LIMIT_ENABLED=true` y
`AUDIT_LOG_ENABLED=true`.

## 3. Levantar

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.production.yml ps
```

Los puertos 8000 y 5173 quedan enlazados solo a `127.0.0.1`. El túnel debe
apuntar a `http://127.0.0.1:5173`.

### Tailscale Serve

```bash
tailscale serve --bg --https=443 http://127.0.0.1:5173
tailscale serve status
```

Tailscale añade `X-Forwarded-Proto: https`.

### Caddy

```caddyfile
invernadero.example.com {
    reverse_proxy 127.0.0.1:5173 {
        header_up X-Forwarded-Proto https
        header_up X-Real-IP {remote_host}
    }
}
```

### Dokploy / Cloudflare Tunnel

Configura el dominio público hacia `http://127.0.0.1:5173` y asegúrate de que
el proxy conserve `X-Forwarded-Proto`. En Dokploy usa el puerto 5173, no 8000.

## 4. Primer administrador

El seed crea el admin con `ADMIN_USERNAME`/`ADMIN_PASSWORD` y rol `admin`. Si
necesitas repararlo o cambiar la contraseña:

```bash
ADMIN_USERNAME=admin ADMIN_PASSWORD='...' bash scripts/setup_first_admin.sh
```

El script valida 12 caracteres y no imprime la contraseña.

## 5. Verificación

```bash
# Público, sin cookie
curl -s https://invernadero.example.com/api/public/telemetry | python3 -m json.tool
curl -s https://invernadero.example.com/api/public/crops | python3 -m json.tool
curl -s -o /dev/null -w '%{http_code}\n' https://invernadero.example.com/admin

# Login admin por el mismo origen
curl -s -c /tmp/gh.jar -X POST https://invernadero.example.com/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"..."}'

# Viewer no puede administrar
curl -s -o /dev/null -w '%{http_code}\n' -b /tmp/gh.jar \
  -X POST https://invernadero.example.com/api/admin/config \
  -H 'Content-Type: application/json' -d '{}'

# Salud detallada solo admin
curl -s -b /tmp/gh.jar https://invernadero.example.com/api/admin/health
```

Comprobaciones esperadas:

- `/api/public/telemetry` → `200` sin sesión.
- `/api/admin/actuators/control` sin sesión → `401`.
- Viewer autenticado en `/api/admin/*` → `403`.
- Admin → `200`.
- `/api/admin/logs` devuelve las acciones.
- Una petición HTTP directa a la API con `REQUIRE_HTTPS=true` → `403`.

## 6. Producción y operación

- **Rate limit:** Nginx 10 req/min en login + SlowAPI 5/min + bloqueo
  persistente por IP/usuario.
- **Auditoría:** `audit_logs` guarda login fallido, bloqueo, login correcto,
  comandos de actuador, cambios de cultivo y configuración. Consulta en
  `/admin/logs`.
- **Fail2ban:** `deploy/fail2ban/README.md`.
- **Logs:** `data/logs/nginx/access.log`, rotación con
  `deploy/logrotate/greenhouse`.
- **Backups:** `scripts/backup.sh` (aplica `umask 077`).
- **Documentación:** `/docs` está deshabilitado en producción. Para depurar,
  activa `ENABLE_DOCS=true` temporalmente.

## 7. Problemas frecuentes

**403 “HTTPS requerido”.** El proxy no envía `X-Forwarded-Proto: https`.
Corrige el proxy; no desactives `REQUIRE_HTTPS` en producción.

**Redirección infinita a HTTPS.** El proxy conecta por HTTP y no reenvía el
esquema. Añade `X-Forwarded-Proto: https` o sirve TLS en el propio proxy.

**El panel admin redirige a `/`.** La cuenta no tiene rol `admin`. Ejecuta
`scripts/setup_first_admin.sh` o crea el usuario con rol correcto.

**“Demasiados intentos”.** Espera el `Retry-After` o desbloquea:
`sudo fail2ban-client set greenhouse-login unbanip <IP>` si usas Fail2ban.
