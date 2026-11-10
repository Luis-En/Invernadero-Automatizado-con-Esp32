# Despliegue con Dokploy + Cloudflare Tunnel

Guía para publicar el invernadero con Dokploy y Cloudflare, sin abrir puertos
entrantes al servidor. El frontal y la API quedan detrás de Cloudflare Tunnel;
solo Dokploy necesita acceso administrativo.

Archivos que se usan:

- `docker-compose.dokploy.yml` → pila completa para Dokploy + Cloudflare.
- `docker-compose.remote-bridge.yml` → puente serial en la Raspberry Pi cuando
  la API vive en un VPS.
- `frontend/nginx.production.conf` → se hornea en la imagen mediante
  `NGINX_CONF=nginx.production.conf`.
- `docs/seguridad.md` y `docs/deploy-public.md` → contexto de seguridad.

## 0. Elige el escenario

### A. Dokploy en la misma Raspberry Pi (con gateway USB)

- Ideal si el ESP32 Gateway está conectado por USB a la Pi.
- El servicio `serial-bridge` corre en el mismo Dokploy, con
  `--profile serial` y `devices: /dev/ttyUSB0`.
- Necesitas Pi 5 con 4 GB/almacenamiento suficiente; Dokploy pide al menos
  2 GB de RAM y 30 GB de disco.

### B. Dokploy en un VPS y puente serial en la Raspberry Pi (recomendado para disponibilidad)

- La API/frontend viven en el VPS (Dokploy + Cloudflare Tunnel).
- La Pi solo ejecuta `docker-compose.remote-bridge.yml` y envía telemetría al
  dominio público por HTTPS con el `DEVICE_API_TOKEN`.
- No hay que exponer la Pi ni abrir puertos en casa.

En ambos casos el navegador entra por
`https://invernadero.tudominio.com`.

---

## 1. Requisitos

- Dominio gestionado por Cloudflare (el plan gratuito sirve).
- Servidor con Docker y Dokploy (VPS o Raspberry Pi).
- Repositorio del proyecto accesible desde Dokploy (GitHub/GitLab/Gitea).
- Para el escenario A: `/dev/ttyUSB0` visible en el host.
- Para el escenario B: la Pi con el gateway USB y salida a Internet.

Genera los secretos antes de empezar:

```bash
openssl rand -hex 32   # JWT_SECRET_KEY
openssl rand -hex 32   # DEVICE_API_TOKEN
printf 'Admin-%s-A1!\n' "$(openssl rand -hex 16)"   # ADMIN_PASSWORD fuerte
```

La contraseña de admin debe tener al menos 12 caracteres, mayúscula,
minúscula, número y símbolo. El arranque falla si no cumple la política.

---

## 2. Crear el túnel en Cloudflare

1. Entra en **Cloudflare Dashboard → Networking → Tunnels** (o
   **Zero Trust → Networks → Tunnels**).
2. Pulsa **Create a tunnel**.
3. Elige **Cloudflared** y pon un nombre, por ejemplo `invernadero`.
4. Copia el **token** (`eyJ...`). No lo publiques ni lo subas al repositorio.
5. Guarda el túnel; todavía no hace falta crear la ruta.
6. En **SSL/TLS → Overview** del dominio, selecciona **Full (Strict)** (o
   **Full** si tu configuración de Tunnel lo requiere). No uses **Flexible**:
   puede provocar bucles de redirección.
7. En **SSL/TLS → Edge Certificates**, deja activo **Always Use HTTPS**.

El token se usará como variable `CLOUDFLARE_TUNNEL_TOKEN` en Dokploy.

---

## 3. Instalar Dokploy

En el servidor (VPS o Pi):

```bash
curl -sSL https://dokploy.com/install.sh | sh
```

Después:

1. Abre `http://IP_DEL_SERVIDOR:3000`.
2. Crea la cuenta de administrador de Dokploy.
3. Activa 2FA y, si es posible, publica el panel de Dokploy por HTTPS o
   protégelo con Cloudflare Access/VPN.
4. No necesitas abrir 80/443 para esta app: Cloudflare Tunnel es saliente.
   Mantén solo SSH y el puerto 3000 restringido.

Requisitos oficiales: 2 GB de RAM y 30 GB de disco. En la Pi, usa una SD/SSD
de calidad y limita las builds concurrentes.

---

## 4. Crear el servicio en Dokploy

1. **Projects → Create Project** (`invernadero`).
2. Dentro del proyecto: **Create Service → Docker Compose**.
   - Elige **Docker Compose**, **no Stack**: Stack no soporta `build`, y esta
     pila construye API y frontend.
3. **General**:
   - **Name**: `invernadero`
   - **Source**: GitHub/GitLab/Gitea y el repositorio del proyecto.
   - **Branch**: `main`
   - **Compose Path**: `docker-compose.dokploy.yml`
4. **Environment**: añade las variables de la siguiente sección.
5. Pulsa **Deploy**.
6. No configures un dominio de Dokploy/Traefik para esta app. Cloudflare
   Tunnel hablará directamente con el servicio `frontend` por la red interna.

### Variables de entorno en Dokploy

Añade una por una (Dokploy las escribe en el `.env` del compose):

| Variable | Valor |
|----------|-------|
| `JWT_SECRET_KEY` | 64 hex generados |
| `DEVICE_API_TOKEN` | 64 hex generados |
| `ADMIN_USERNAME` | `admin` |
| `ADMIN_PASSWORD` | contraseña fuerte generada |
| `ADMIN_EMAIL` | tu correo |
| `CLOUDFLARE_TUNNEL_TOKEN` | token `eyJ...` del túnel |
| `PUBLIC_BASE_URL` | `https://invernadero.tudominio.com` |
| `CORS_ORIGINS` | `["https://invernadero.tudominio.com"]` |
| `OPENWEATHER_API_KEY` | tu clave (opcional) |
| `TRUSTED_PROXIES` | dejar el default del compose |

Opcionales:

| Variable | Uso |
|----------|-----|
| `WEATHER_LOCATION_NAME` | nombre mostrado |
| `RATE_LIMIT_*` | ajustar límites |
| `LOGIN_*` | ajustar lockout |
| `AUDIT_LOG_ENABLED` | `true` |
| `NOTIFICATIONS_ENABLED` | `true` |

El compose ya fija `ENVIRONMENT=production`, `AUTH_COOKIE_SECURE=true`,
`REQUIRE_HTTPS=true`, `ENABLE_DOCS=false` y `VAPID_AUTO_GENERATE=true`.

> `CORS_ORIGINS` debe ser un array JSON válido, con el mismo origen que
> `PUBLIC_BASE_URL`. Si usas otro dominio, cambia ambos.

---

## 5. Crear la ruta pública en Cloudflare

Cuando el servicio esté desplegado y `cloudflared` conectado:

1. Vuelve a **Networking → Tunnels → tu túnel → Routes**.
2. **Add route → Published application**.
3. Configura:
   - **Subdomain**: `invernadero` (o el que uses)
   - **Domain**: `tudominio.com`
   - **Service URL**: `http://frontend:80`
4. Guarda.

`frontend` es el nombre del servicio en `docker-compose.dokploy.yml`.
Cloudflared corre en la misma red de Compose, por eso resuelve ese nombre.

Cloudflare crea el registro DNS automáticamente. Si no lo hace, crea un CNAME:

- Tipo: `CNAME`
- Nombre: `invernadero`
- Contenido: `<TUNNEL_ID>.cfargotunnel.com`
- Proxy: activado (naranja)

Espera a que el túnel figure **Healthy** y abre:

```text
https://invernadero.tudominio.com
```

Debe cargar el dashboard público sin pedir login. El panel está en
`https://invernadero.tudominio.com/admin/login`.

---

## 6. Verificación

Desde tu equipo:

```bash
# Debe ser 200 sin sesión
curl -s -o /dev/null -w '%{http_code}\n' https://invernadero.tudominio.com/api/public/telemetry

# Datos redactados
curl -s https://invernadero.tudominio.com/api/public/telemetry | python3 -m json.tool

# El admin exige sesión: 401
curl -s -o /dev/null -w '%{http_code}\n' https://invernadero.tudominio.com/api/admin/health

# La UI pública
curl -s -o /dev/null -w '%{http_code}\n' https://invernadero.tudominio.com/
```

En el navegador:

1. Abre `/admin/login` e inicia sesión con `ADMIN_USERNAME`/`ADMIN_PASSWORD`.
2. Comprueba `/admin` (control), `/admin/logs` (auditoría) y
   `/admin/usuarios`.
3. Instala la PWA desde el menú del navegador (HTTPS ya está disponible).
4. Activa las notificaciones desde la campana; las claves VAPID se generan
   solas en el volumen `vapid_keys` del primer arranque.

---

## 7. Escenario A: gateway USB en el mismo host que Dokploy

El servicio `serial-bridge` está detrás del perfil `serial`. Para activarlo:

1. Verifica el dispositivo:
   ```bash
   ls -l /dev/ttyUSB0
   ```
2. En Dokploy, abre el servicio → **Advanced → Command**.
3. Copia el comando que Dokploy muestra y añade `--profile serial` después de
   los argumentos `-f`:
   ```text
   compose -p <app-name> -f <compose-path> --profile serial up -d --build --remove-orphans --force-recreate
   ```
   El comando exacto que muestra la UI manda; solo inserta `--profile serial`.
4. En **Environment** añade:
   ```text
   SIMULATE=false
   SERIAL_DEVICE=/dev/ttyUSB0
   SERIAL_PORT=/dev/ttyUSB0
   ```
5. Redeploy.
6. En **Logs** del servicio `serial-bridge` debe aparecer
   `serial bridge starting in serial mode on /dev/ttyUSB0`.

Si el dispositivo cambia de nombre (`/dev/ttyACM0`, `/dev/serial/by-id/...`),
ajusta `SERIAL_DEVICE`.

---

## 8. Escenario B: Dokploy en VPS y puente en la Raspberry Pi

Deja el perfil serial **desactivado** en Dokploy (no añadas
`--profile serial`). El VPS no tiene el gateway USB.

En la Raspberry Pi:

```bash
# Si aún no tienes Docker:
# curl -fsSL https://get.docker.com | sh

cd InvernaderoAuto
export API_URL="https://invernadero.tudominio.com"
export DEVICE_API_TOKEN="<el mismo token del VPS>"
docker compose -f docker-compose.remote-bridge.yml up -d --build
docker compose -f docker-compose.remote-bridge.yml logs -f
```

Comprueba que la Pi puede llegar al dominio:

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "X-Device-Token: $DEVICE_API_TOKEN" \
  https://invernadero.tudominio.com/api/config/device/active
```

Debe devolver `200` (o `404` si no hay configuración activa, pero no `401`).

El bridge usa el token de dispositivo, no una sesión de usuario. No pongas
Cloudflare Access delante de `/api/config/telemetry`, `/api/photos/chunk` ni
`/api/config/device/*`, o la Pi no podrá autenticarse.

---

## 9. Persistencia y copias

`docker-compose.dokploy.yml` usa volúmenes nombrados para que un redeploy no
borre datos:

- `greenhouse_data` → base SQLite y fotos (`/app/data`).
- `vapid_keys` → claves VAPID (`/app/secrets`).
- `../files/nginx-logs` → logs de Nginx persistentes.

En Dokploy:

1. **Volume Backups** sobre `greenhouse_data` y `vapid_keys` (S3 compatible).
2. Programa backups diarios.
3. Prueba una restauración en un proyecto temporal antes de confiar en ella.

No guardes la base ni las claves en un bind mount del repositorio: Dokploy
hace un `git clone` en cada despliegue y los archivos generados se perderían.

Si borras `vapid_keys`, se generan claves nuevas, pero **todas las
suscripciones push existentes dejan de ser válidas** y hay que reactivarlas en
cada teléfono.

---

## 10. Actualizaciones

- Push a `main` y **Redeploy** en Dokploy (o activa Auto Deploy).
- Las migraciones Alembic se aplican al arrancar la API.
- Los volúmenes `greenhouse_data` y `vapid_keys` se conservan.
- Si cambias `docker-compose.dokploy.yml`, revisa que siga usando volúmenes
  nombrados y no rutas `./data` del repositorio.

---

## 11. Problemas frecuentes

**El túnel aparece Inactive/Down.**
Token incorrecto o `cloudflared` sin salida a Internet. Revisa
`Logs → cloudflared` y vuelve a copiar el token.

**502 Bad Gateway en el dominio.**
La ruta apunta a un servicio que no resuelve. Debe ser exactamente
`http://frontend:80` y el contenedor `frontend` debe estar healthy. Si Dokploy
renombró el servicio, usa el nombre que aparece en su red.

**403 “HTTPS requerido”.**
Cloudflare no está enviando `X-Forwarded-Proto: https` o el SSL/TLS está en
Flexible. Pon **Full (Strict)** y comprueba:
```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  -H 'X-Forwarded-Proto: https' \
  http://127.0.0.1:5173/api/public/telemetry
```
Debe ser `200`.

**Bucle de redirección HTTPS.**
El origen está recibiendo HTTP sin cabecera segura. No uses Flexible; no
cambies la ruta a `https://frontend:80` (el frontal sirve HTTP interno).

**La API no arranca: “ADMIN_PASSWORD must be at least 12 characters”.**
Cambia la variable en Dokploy y redeploy. La contraseña debe incluir
mayúscula, minúscula, número y símbolo.

**“No admin account exists”.**
Falta `ADMIN_PASSWORD` en el primer arranque, o el seed falló. Corrige la
variable y redeploy. También puedes ejecutar `scripts/setup_first_admin.sh`
desde el host o el terminal de Dokploy.

**No hay datos de sensores.**
En el escenario B, revisa el bridge de la Pi y que `API_URL` sea el dominio
público. En el A, revisa `--profile serial` y `/dev/ttyUSB0`.

**No llegan notificaciones push.**
El túnel/HTTPS es obligatorio. Revisa que el volumen `vapid_keys` exista y que
la campana muestre push activo. En iPhone hay que instalar la PWA (iOS 16.4+).

**Dokploy borró la base en un redeploy.**
Estás usando un bind mount `./data` del repositorio. Cambia a
`greenhouse_data` como en `docker-compose.dokploy.yml`.

**Cloudflare Access bloquea la Pi.**
No protejas los endpoints de dispositivo. Access es para el panel/UI, no para
`/api/config/telemetry` ni `/api/photos/chunk`.

---

## 12. Checklist final

- [ ] Dominio en Cloudflare y SSL/TLS **Full (Strict)**.
- [ ] Túnel creado y token guardado en Dokploy.
- [ ] Dokploy instalado, panel con HTTPS/2FA.
- [ ] Servicio Docker Compose (no Stack) con `docker-compose.dokploy.yml`.
- [ ] `JWT_SECRET_KEY`, `DEVICE_API_TOKEN`, `ADMIN_PASSWORD` fuertes.
- [ ] `PUBLIC_BASE_URL` y `CORS_ORIGINS` con el dominio real.
- [ ] Ruta Cloudflare → `http://frontend:80`.
- [ ] `/` público y `/admin/login` operativo.
- [ ] Volúmenes `greenhouse_data` y `vapid_keys` con backup.
- [ ] Bridge serial funcionando (perfil `serial` o Pi remota).
- [ ] `curl /api/public/telemetry` → 200; `/api/admin/health` sin sesión → 401.
- [ ] Revisar `/admin/logs` tras las primeras acciones.
