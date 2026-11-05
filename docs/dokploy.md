# Despliegue en Dokploy

Guía para publicar InvernaderoAuto en un servidor con
[Dokploy](https://dokploy.com). El resultado puede ser **un único dominio** que
sirve el frontend compilado y hace proxy de la API y del WebSocket, o un acceso
directo por IP y puerto (`http://IP:8080`) mientras no haya DNS.

---

## 1. Qué se despliega

El archivo [`docker-compose.dokploy.yml`](../docker-compose.dokploy.yml) define
cuatro servicios:

| Servicio | Imagen | Función | Expuesto |
|----------|--------|---------|----------|
| `frontend` | Nginx + build de Vite | Sirve la SPA y hace proxy de `/api`, `/photos` y `/api/config/ws` | Puerto 80 interno; `8080` en el host |
| `api` | Python 3.12 + Uvicorn | FastAPI, SQLite, WebSocket, clima y comandos MQTT | Solo red interna (`8000`) |
| `serial-bridge` | Python 3.12 | Simulador o puente USB del ESP32 | Solo red interna |
| `mqtt` | Eclipse Mosquitto 2 | Broker para comandos de actuadores | Solo red interna (`1883`) |

Los datos (base SQLite y fotos) se guardan en el volumen nombrado
`greenhouse_data`, montado en `/app/data`. Sobreviven a redeploys.

```
Internet / LAN ──▶ frontend (Nginx :80 / host :8080)
                     ├── /                   → React (dist)
                     ├── /api/*              → api:8000
                     ├── /photos/*           → api:8000
                     ├── /api/config/ws      → api:8000 (WebSocket)
                     └── /health             → api:8000/health

api ──▶ mqtt:1883 (red interna, no publicado)
```

> No uses `docker-compose.yml` en Dokploy: es el compose de desarrollo, usa
> `npm run dev`, monta el código desde el host y apunta a `localhost`.

---

## 2. Requisitos

1. Dokploy instalado y accesible.
2. El código en el repositorio Git que Dokploy clona:
   `https://github.com/Luis-En/Invernadero-Automatizado-con-Esp32.git`.
3. Opcional: un registro DNS `A` del dominio (o subdominio) apuntando a la IP
   del servidor. Sin dominio se puede usar `http://IP:8080`.
4. Acceso SSH al servidor si quieres revisar volúmenes o logs por consola.
5. Al menos ~1.5 GB de RAM libre para compilar (Node + Python). Si el equipo es
   muy pequeño, añade swap o usa un *build server*.

---

## 3. Servicio en Dokploy

El servicio ya existe como **Compose**. Verifica:

1. **Compose Type**: `Docker Compose` (no “Stack”: Stack/Swarm no soporta
   `build` y aquí se construyen las imágenes desde el Dockerfile).
2. **Provider / Source**: Git con URL personalizada.
3. **Repository**: `https://github.com/Luis-En/Invernadero-Automatizado-con-Esp32.git`
4. **Branch**: `main`
5. **Compose Path**: `./docker-compose.dokploy.yml`
6. **Auto Deploy**: activado si quieres que cada push a `main` despliegue solo.

Si el repositorio es privado, configura una clave SSH o un proveedor de Git con
permisos de lectura en Dokploy.

---

## 4. Variables de entorno

Abre la pestaña **Environment** y pega el contenido de
[`.env.dokploy.example`](../.env.dokploy.example), cambiando los valores:

```env
JWT_SECRET_KEY=<salida de: openssl rand -hex 32>

ADMIN_USERNAME=admin
ADMIN_PASSWORD=<clave fuerte del administrador>
VIEWER_PASSWORD=<clave fuerte del usuario viewer>

DEVICE_USERNAME=viewer
DEVICE_PASSWORD=<la misma que VIEWER_PASSWORD>

# Si entras por IP:8080 sin dominio:
CORS_ORIGINS=["http://10.160.66.170:8080","http://localhost:8080"]

SIMULATE=true
```

Notas importantes:

- `JWT_SECRET_KEY` es **obligatorio**. Si falta, la interpolación de Compose
  falla y el despliegue se detiene con un mensaje claro.
- `ADMIN_PASSWORD` y `VIEWER_PASSWORD` se aplican al crear la base de datos y
  también se **sincronizan en cada arranque**. Así puedes rotar la contraseña
  en un volumen que ya existe: cambia la variable y redespliega.
- `DEVICE_PASSWORD` debe coincidir con `VIEWER_PASSWORD`, porque el bridge usa
  ese usuario para leer la configuración activa.
- `CORS_ORIGINS` no es necesario para el uso normal por dominio (frontend y API
  comparten origen). Si entras por `IP:8080`, incluye ese origen en la lista
  JSON. También sirve para llamar la API desde otro dominio.
- `SIMULATE=true` mantiene el dashboard con datos aunque no haya hardware. Si
  no quieres datos simulados, pon `SIMULATE=false` (sin hardware no habrá
  telemetría) o detén el servicio `serial-bridge` desde Dokploy.
- `OPENWEATHER_API_KEY` es opcional. Sin clave la sección de clima se oculta y
  el resto del sistema funciona igual.
- `MQTT_ENABLED=true` usa el broker interno. No se publica el puerto `1883` al
  exterior; para un ESP32 en otra red necesitarás exponerlo con autenticación
  y TLS (ver sección 10).

Dokploy guarda estas variables en un `.env` junto al compose y Compose las
inyecta con la sintaxis `${VAR}`.

---

## 5. Acceso por IP (sin dominio)

El compose publica `8080:80` en el servicio `frontend`. Después del despliegue:

```
http://10.160.66.170:8080
```

Si cambias de servidor o de red, actualiza `CORS_ORIGINS` y vuelve a desplegar.
Si más adelante configuras un dominio, puedes quitar el bloque `ports` del
servicio `frontend` para dejar solo el acceso por Traefik.

---

## 6. Configurar un dominio (opcional)

1. Ve a la pestaña **Domains** del servicio Compose.
2. **Add Domain**:
   - **Service**: `frontend`
   - **Host**: `invernadero.midominio.com`
   - **Path**: `/`
   - **Internal Port**: `80`
   - **HTTPS**: activado
   - **Certificate Provider**: `Let's Encrypt`
3. Guarda.

Dokploy añade automáticamente las etiquetas de Traefik y conecta el servicio a
la red `dokploy-network`. El compose ya declara esa red como externa en
`frontend`, así que todo queda consistente.

El puerto que debes indicar es **80** (el contenedor de Nginx). No publiques
`8000` ni `5173` en el host.

---

## 7. Desplegar

Pulsa **Deploy**. La primera vez:

1. Dokploy clona el repositorio.
2. Construye las imágenes (puede tardar varios minutos).
3. Levanta `mqtt`, `api`, espera su healthcheck (`/health`), luego `frontend` y
   `serial-bridge`.
4. Si configuraste dominio, Traefik emite el certificado TLS.

En la pestaña **Deployments** puedes seguir el log. Si algo falla, revisa la
pestaña **Logs** de cada servicio.

---

## 8. Verificar

Con IP o dominio ya funcionando:

```bash
# API a través de Nginx
curl http://10.160.66.170:8080/health
# → {"status":"ok","service":"greenhouse-api"}

# Login (usa tu ADMIN_PASSWORD)
curl -X POST http://10.160.66.170:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"TU_CLAVE"}'
```

Luego abre la UI:

- Inicia sesión con `admin` / `ADMIN_PASSWORD`.
- El dashboard debe mostrar telemetría (el simulador envía cada 30 s).
- El indicador de WebSocket debe conectarse; la primera foto simulada aparece
  a los ~30 s (`SIM_FIRST_PHOTO_DELAY_SEC`).
- `/health` es un atajo al healthcheck de la API.

---

## 9. Operación y datos

### Volumen

La base y las fotos viven en `greenhouse_data` (`/app/data`):

- `greenhouse.db` — SQLite
- `photos/` — imágenes

El nombre real del volumen lo prefija el proyecto Compose. En el servidor:

```bash
docker volume ls | grep greenhouse
```

### Backup manual

```bash
# Sustituye el nombre por el que devuelva `docker volume ls`
docker run --rm \
  -v invernadero_greenhouse_data:/data:ro \
  -v "$PWD":/backup \
  alpine tar czf /backup/greenhouse-$(date +%F).tar.gz -C /data .
```

También puedes activar **Volume Backups** de Dokploy hacia S3; funciona con
volúmenes nombrados.

### Migrar datos de un despliegue local

Si ya tienes `data/greenhouse.db` y `data/photos/` de `docker-compose.yml`, el
nuevo despliegue arranca con un volumen vacío. Para conservarlos:

```bash
# 1. Detén el stack de desarrollo SIN borrar datos
cd /home/invernadero/InvernaderoAuto
docker compose down

# 2. Despliega en Dokploy una vez (crea el volumen), luego localiza su nombre
docker volume ls | grep greenhouse_data
#    Ejemplo: invernaderouvg-invernaderouvg-lo7zbx_greenhouse_data

# 3. Copia la base y las fotos al volumen (con la API detenida)
docker run --rm \
  -v invernaderouvg-invernaderouvg-lo7zbx_greenhouse_data:/target \
  -v /home/invernadero/InvernaderoAuto/data:/source:ro \
  alpine sh -c "cp -a /source/. /target/"

# 4. Reinicia el servicio desde Dokploy
```

Mantén `ADMIN_USERNAME=admin` al migrar: si lo cambias, el seed creará un
segundo administrador. La contraseña de `ADMIN_PASSWORD` se sincroniza en el
siguiente arranque.

### Actualizar

```bash
git add .
git commit -m "cambios"
git push
```

Si activaste **Auto Deploy**, Dokploy despliega solo; si no, pulsa **Deploy**.
El volumen y la base se conservan.

### Logs y shell

- UI de Dokploy → servicio → **Logs**.
- Por SSH: `docker ps` y `docker logs -f <contenedor>`.
- No ejecutes `docker compose down -v`: borra el volumen de datos.

### Cambiar contraseñas

Edita `ADMIN_PASSWORD` / `VIEWER_PASSWORD` (y `DEVICE_PASSWORD`) en
**Environment**, guarda y redespliega. El seed sincroniza los hashes al
arrancar.

---

## 10. MQTT y hardware real

### MQTT dentro del servidor

El servicio `mqtt` usa `config/mosquitto.conf` y solo es accesible desde la red
interna del compose. La API se conecta a `mqtt:1883`. Los botones de actuadores
del dashboard publican comandos y esperan el ACK del dispositivo; sin un ESP32
conectado, el comando termina en timeout (es esperado).

### ESP32 en la misma red

El firmware puede publicar directamente al broker. Si el broker corre en el
mismo servidor y la red es confiable, publica el puerto `1883` en el compose y
ajusta `MQTT_HOST` según corresponda. Para exposición a Internet no uses
`allow_anonymous true`: configura usuario/clave, TLS y firewall.

### Caso A: Dokploy corre en la Raspberry Pi con el gateway conectado

1. En **Environment**: `SIMULATE=false`, `SERIAL_PORT=/dev/ttyUSB0`.
2. En `docker-compose.dokploy.yml`, descomenta el bloque `devices` del servicio
   `serial-bridge`.
3. Verifica en el host que el dispositivo existe: `ls -l /dev/ttyUSB0`.
4. Redespliega. El contenedor necesita permiso sobre el dispositivo; si falla
   por permisos, ejecuta el bridge como root (comportamiento por defecto) o
   ajusta el grupo `dialout` del host.

El firmware y el protocolo están en [`backend/serial_bridge/README.md`](../backend/serial_bridge/README.md).

### Caso B: Dokploy está en la nube y la Raspberry Pi está en el invernadero

No conectes hardware al servidor cloud. Opciones:

1. Ejecuta **solo** el bridge en la Pi, apuntando a la API pública:
   ```bash
   cd backend/serial_bridge
   pip install -r requirements.txt
   SIMULATE=false SERIAL_PORT=/dev/ttyUSB0 \
   API_URL=https://invernadero.midominio.com python bridge.py
   ```
2. Quita o desactiva el servicio `serial-bridge` del compose cloud (si lo dejas
   con `SIMULATE=true`, seguirás viendo datos simulados).
3. El endpoint `POST /api/config/telemetry` no pide autenticación (está pensado
   para el dispositivo). Si la API queda pública, protégelo con firewall,
   Tailscale/WireGuard o un proxy con autenticación.

---

## 11. Problemas comunes

| Síntoma | Causa / solución |
|---------|------------------|
| `502 Bad Gateway` | La API no está sana. Revisa sus logs; suele ser `JWT_SECRET_KEY` ausente o error de arranque. |
| El deploy falla en “required variable JWT_SECRET_KEY” | Falta la variable en **Environment**. |
| El deploy falla con “Compose file not found” | El `Compose Path` debe ser `./docker-compose.dokploy.yml` y el archivo debe estar en la rama `main`. |
| El deploy falla con “Github Provider not found” | El servicio está en modo proveedor GitHub pero no hay proveedor configurado. Usa Source Type **Git** con URL personalizada. |
| WebSocket no conecta | Debe entrar por `ws://IP:8080/api/config/ws` o `wss://tu-dominio/api/config/ws`. Ya está configurado en Nginx. |
| Error CORS al entrar por IP | Agrega `http://IP:8080` a `CORS_ORIGINS` como lista JSON y redespliega. |
| Login admin falla | El usuario por defecto es `admin` (o tu `ADMIN_USERNAME`), no el correo. Confirma `ADMIN_PASSWORD` y redespliega para sincronizar. |
| Los datos desaparecen tras un deploy | Se está usando otro proyecto/volumen o se ejecutó `down -v`. Usa siempre el volumen nombrado. |
| Los comandos de actuadores dan timeout | No hay un ESP32 conectado al broker MQTT. Es normal en simulación. |
| Build agotado por memoria | Añade swap al servidor o configura un build server en Dokploy. |
| `port is already allocated` | Otro proceso usa el `8080`. Cambia el mapeo o quita `ports` y usa solo dominio. |
| Cambié el código y no se ve | Dokploy clona y reconstruye; verifica el commit desplegado y que `Auto Deploy` esté activo. |

---

## 12. Referencia rápida de archivos

| Archivo | Uso |
|---------|-----|
| `docker-compose.dokploy.yml` | Compose de producción para Dokploy |
| `docker-compose.yml` | Desarrollo local (no usar en Dokploy) |
| `.env.dokploy.example` | Plantilla de variables para la pestaña Environment |
| `backend/api/Dockerfile.prod` | Imagen de producción de la API |
| `frontend/Dockerfile.prod` | Build de Vite + Nginx |
| `frontend/nginx.conf` | Proxy `/api`, `/photos`, WebSocket y fallback SPA |
| `config/mosquitto.conf` | Configuración del broker MQTT interno |
| `.env.example` | Variables para desarrollo local |
