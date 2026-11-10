# Invernadero Automatizado - Santa Lucía Cotzumalguapa, Guatemala

Sistema completo de monitoreo y automatización para invernadero 19m x 4m con Raspberry Pi 5, ESP32 y sensores IoT.

## 🏗️ Arquitectura

```
ESP32-CAM ──WiFi (AP del campo)──▶ ESP32 Campo primario ──ESP-NOW 50m──▶ ESP32 Gateway ──USB──▶ RPi5
   captura JPEG                     2x suelo + BME280                     puente serial         │
                                     5 actuadores + automatización                             ▼
ESP32 Campo secundario ──ESP-NOW──▶        │                              FastAPI + SQLite + React
   4x suelo extra                          └── el puente fusiona las 6 lecturas   (dashboard vía WebSocket)
```

El nodo de campo levanta su propia red Wi-Fi (`invernadero-campo`), sin router.
La cámara se conecta a ella y sube cada foto; el campo la fragmenta hacia el
gateway por ESP-NOW. Los datos de sensores van por el mismo enlace ESP-NOW y
llegan a la web en tiempo real.

## 📋 Hardware Confirmado

| Componente | Modelo | Especificación |
|------------|--------|----------------|
| Raspberry Pi | Pi 5 4GB + 64GB SD | Kit con cooler 27W |
| ESP32 Campo | DevKit V1 | 6x ADC1, I2C, Wi-Fi (AP), 5 actuadores |
| ESP32 Gateway | DevKit V1 | Puente ESP-NOW ↔ USB Serial |
| ESP32-CAM | OV2640 + 4MB PSRAM | Foto VGA c/30min vía Wi-Fi (AP del campo) |
| Suelo (x6) | Capacitivo v1.2 | 3.3-5V, AOUT analógico |
| Ambiente | BME280 | I2C, ±1°C, ±3% HR, 300-1100 hPa |
| Ventiladores (x2) | 8" 35W 110VAC | Kemik Premiere |
| Humidificadores (x2) | Ultrasónico 24VDC 800mA | Sumergible, 400ml/h, máx 10h/día |
| Bomba | 0.5HP 110VAC 35L/min | Celasa BOM01, ciclo 15min ON / 5min OFF |

## ⚡ Requisitos Eléctricos (Pendientes)

> **IMPORTANTE**: El sistema simula todo sin hardware. Para producción necesitas:
- Cable 12AWG 50m + breaker 15A + varistor para 110VAC
- Contactor 20A para bomba (inrush 12-18A) - **no usar relé 10A**
- SSR-40DA o MOSFET para humidificadores 24VDC
- Fuente 24VDC 3A + fuente 5VDC 3A para ESP32
- Tinaco/reserva de agua + válvula pie + cebado
- Pull-down de 10 kΩ en cada GPIO de relé y puesta a tierra única

Detalle de selección, cableado y verificación: `docs/potencia.md`.

## 🚀 Despliegue Rápido (Simulación)

```bash
cd /home/luis/Proyectos/InvernaderoAuto

# 1. Configurar variables y secretos
cp .env.example .env
# Rellena en .env:
#   JWT_SECRET_KEY       -> openssl rand -hex 32
#   DEVICE_API_TOKEN     -> openssl rand -hex 32
#   ADMIN_PASSWORD       -> una contraseña fuerte
# No existe ningún usuario viewer123 ni contraseña por defecto.

# 2. Levantar con Docker Compose
docker compose up --build -d

# 3. Ver logs
docker compose logs -f

# 4. Acceder a la UI
# Dashboard público: http://localhost:5173/
# Panel admin:       http://localhost:5173/admin/login
# Usuario: ADMIN_USERNAME (por defecto admin) / ADMIN_PASSWORD
```

La API **no arranca** si `JWT_SECRET_KEY` sigue siendo el valor de ejemplo, y
los endpoints de telemetría/fotos/confirmación rechazan peticiones sin
`DEVICE_API_TOKEN`. El frontend se sirve compilado por Nginx en el mismo origen
que `/api`, sin CORS ni `localhost` embebido.

## 🌍 Acceso público y panel admin

Desde v2 la lectura es pública y el control exige rol `admin`:

| Ruta | Acceso |
|------|--------|
| `/` | Dashboard público en vivo (sin login) |
| `/fotos` | Galería pública |
| `/clima` | Clima público |
| `/admin/login` | Login de administrador |
| `/admin` | Control de actuadores |
| `/admin/cultivos` | Gestión de cultivos |
| `/admin/configuracion` | Configuración e histeresis |
| `/admin/logs` | Auditoría de acciones |
| `/admin/usuarios` | Altas de usuarios y roles |

La API pública (`/api/public/telemetry`, `/photos`, `/weather`, `/crops`) está
redactada: no devuelve `device_id`, RSSI, secuencia, notas internas ni rutas de
archivos. Las escrituras viven bajo `/api/admin/*` y todas quedan en
`audit_logs`. La API directa escucha solo en `127.0.0.1:8000`; el frontal Nginx
la expone en el mismo origen.

Despliegue con TLS, túnel y primer admin: **[docs/deploy-public.md](docs/deploy-public.md)**.
Guía específica para **Dokploy + Cloudflare Tunnel**:
**[docs/deploy-dokploy-cloudflare.md](docs/deploy-dokploy-cloudflare.md)**.

## 🧪 Verificación

```bash
# Backend API
curl http://localhost:8000/health

# Login (usa las credenciales definidas en .env)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"TU_ADMIN_PASSWORD"}'

# Telemetría de dispositivo (requiere el token compartido)
curl -X POST http://localhost:8000/api/config/telemetry \
  -H "X-Device-Token: $DEVICE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @telemetry.json

# WebSocket del dashboard público
# Abrir http://localhost:5173/ -> telemetría pública en vivo

# Fotos
# Cada 30min se genera foto dummy y aparece en /fotos
```

## 🔌 Modo Serial (Gateway Real)

Por defecto el bridge simula. Para leer el ESP32 Gateway por USB:

```bash
# Directo
SIMULATE=false SERIAL_PORT=/dev/ttyUSB0 python backend/serial_bridge/bridge.py

# Con Docker (override que adjunta el dispositivo)
SERIAL_DEVICE=/dev/ttyUSB0 docker compose \
  -f docker-compose.yml -f docker-compose.serial.yml up -d serial-bridge
```

El bridge verifica el CRC16 de cada línea y reenvía `telemetry` a
`/api/config/telemetry` y `photo_chunk` a `/api/photos/chunk`. Ver
`backend/serial_bridge/README.md`.

## 📡 Prueba de Enlace ESP-NOW

El firmware de bring-up vive en `firmware/bringup` (dos placas: nodo de campo
y gateway ESP8266). Sigue `firmware/bringup/README.md` para verificar el enlace
radio antes de armar el invernadero:

```bash
cd firmware/bringup/esp8266_field   && pio run -e field -t upload
cd ../esp8266_gateway               && pio run -e gateway -t upload
```

## 🔧 Firmware

Tres nodos con PlatformIO, sobre una librería común (`firmware/common`) que
comparte el driver ESP-NOW, el protocolo y el CRC16:

| Nodo | Placa | Rol |
|------|-------|-----|
| `firmware/field` (primario) | ESP32 | 2 sondas + BME280, 5 actuadores, automatización, fail-safe y AP de cámara |
| `firmware/field` (`field_secondary`) | ESP32 | 4 sondas extra; reenvía telemetría al gateway por ESP-NOW |
| `firmware/gateway` | ESP32 | Puente ESP-NOW ↔ USB serial (telemetría, fotos y comandos) |
| `firmware/camera` | ESP32-CAM | Captura JPEG periódica → Wi-Fi al nodo de campo |

El gateway **solo habla por USB serial** con la Raspberry: telemetría, fotos y
comandos. Los botones de la web llegan a la API, que llama al bridge serial; el
bridge escribe `set_actuator` por USB, el gateway lo traduce a
`CMD_SET_ACTUATOR` por ESP-NOW y devuelve el ACK del campo. No se usa ningún broker externo.

```bash
cd firmware/field   && pio run -e field     # compilar nodo de campo
cd firmware/gateway && pio run -e gateway   # compilar gateway
cd firmware/camera  && pio run -e camera    # compilar cámara
```

La lógica de automatización del firmware sigue las mismas reglas que
`backend/api/app/automation.py` (histéresis, límite máximo de encendido,
cooldown de apagado y detección de sensor congelado). El "port" es fiel en las
decisiones, con dos matices: el push de configuración aplica parcialmente por
chunks y solo se compromete con el CRC del documento completo, y el backend
Python es la referencia de pruebas, no el runtime del simulador (el simulador
tiene su propia copia). Se prueba en el host con
`bash firmware/field/tools/run_logic_tests.sh`. Detalles en
`firmware/field/README.md`, `firmware/gateway/README.md` y
`firmware/camera/README.md`.

## 📁 Estructura del Proyecto

```
InvernaderoAuto/
├── backend/
│   ├── api/                 # FastAPI + SQLite + Auth + WebSocket
│   │   ├── app/
│   │   │   ├── models.py    # SQLAlchemy models
│   │   │   ├── routes/      # REST endpoints
│   │   │   ├── automation.py # Lógica de control de referencia
│   │   │   ├── main.py      # App factory
│   │   │   └── seed.py      # Datos iniciales (12 cultivos zona)
│   │   ├── tests/           # pytest (auth, cultivos, config, fotos, automatización)
│   │   └── Dockerfile
│   └── serial_bridge/       # Puente gateway/simulador → API
│       ├── bridge.py        # Elige simulación o gateway serial
│       ├── serial_source.py # Lector pyserial con reconexión
│       ├── gateway_protocol.py  # CRC16 + framing JSON-lines
│       ├── simulator.py     # Nodo de campo sintético
│       └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/           # Públicas, admin (control, cultivos, config, logs)
│   │   ├── components/      # Layouts, RequireAuth, SensorCard, Charts, Modal…
│   │   ├── context/         # AuthContext, TelemetryContext (WS), WeatherContext
│   │   ├── hooks/           # usePublicTelemetry, useDialog, usePushNotifications…
│   │   ├── test/            # Vitest + Testing Library
│   │   └── api.js           # Cliente API público/admin + WS
│   ├── public/              # manifest, service worker, iconos, offline.html
│   ├── nginx.conf           # configuración de desarrollo
│   ├── nginx.production.conf# HTTPS/redirect para producción
│   └── Dockerfile
├── firmware/
│   ├── common/              # Protocolo, ESP-NOW HAL (PMK/LMK) y utilidades
│   ├── field/               # Nodo de campo ESP32 (primario y secundario)
│   ├── gateway/             # Gateway ESP-NOW ↔ serial (ESP32 y ESP8266)
│   ├── camera/              # Nodo cámara ESP32-CAM
│   ├── bringup/             # Bring-up ESP8266 campo/gateway
│   └── tools/               # Utilidades de diagnóstico (i2c_probe)
├── config/
│   └── actuators.yaml       # HAL actuadores (pins, tipo, max_on)
├── docs/
│   ├── vscode-setup.md      # Configurar VS Code, tareas y depuración
│   └── api.http             # Ejemplos REST Client
├── data/                    # Volumen persistente (DB + fotos)
├── .vscode/                 # Tareas, depuración, extensiones
├── invernaderoauto.code-workspace  # Workspace multi-root
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🌱 Cultivos Pre-cargados (Zona Santa Lucía Cotzumalguapa)

Clima: Aw (Sabana tropical), 368 msnm, 25.7°C media, 31.5°C máx, HR 72%, 3156mm/año

| Cultivo | Temp Día | Temp Noche | HR | Suelo | Fuente |
|---------|----------|------------|-----|-------|--------|
| Tomate | 22-26°C | 13-16°C | 55-60% | 40-70% | FAO a1374s, INTA, Tesi 1993 |
| Pimiento/Chile | 22-28°C | 16-18°C | 65-70% | 40-70% | FAO i3359s, INTA |
| Pepino | 24-28°C | 18-20°C | 70-85% | 50-80% | UTADEO Manual Pepino |
| Melón | 24-30°C | 18-21°C | 50-70% | 40-70% | INTA, Montero/Anton |
| Sandía | 24-32°C | 20-24°C | 50-70% | 40-70% | INTA Grupo E |
| Berenjena | 22-26°C | 15-18°C | 60-75% | 45-75% | INTA Grupo E |
| Calabacín | 24-28°C | 15-18°C | 60-80% | 45-75% | INTA Grupo D |
| Frijol | 22-28°C | 16-18°C | 55-75% | 40-70% | INTA, FAO |
| Maíz Dulce | 24-30°C | 15-20°C | 55-75% | 45-75% | FAO |
| Cilantro | 18-25°C | 12-18°C | 55-75% | 45-75% | PortalFruticola |
| **Lechuga** ⚠️ | 15-20°C | 10-15°C | 60-80% | 50-80% | INIA - **Difícil en calor** |
| **Fresa** ⚠️ | 15-25°C | 8-13°C | 60-80% | 50-80% | FAO - **Difícil en calor** |

⚠️ = Marcado como difícil en clima local (supera 30°C frecuente). Requiere variedades termotolerantes + sombreo.

## 🔧 Configuración Avanzada

### Variables de entorno (.env)
```bash
DATABASE_URL=sqlite+aiosqlite:///./data/greenhouse.db
JWT_SECRET_KEY=tu-clave-secreta-32-bytes
SIMULATE=true
SIM_TELEMETRY_INTERVAL_SEC=30
SIM_PHOTO_INTERVAL_MIN=30
OPENWEATHER_API_KEY=
WEATHER_LAT=14.3333
WEATHER_LON=-91.0167
WEATHER_CACHE_TTL_SEC=600
```

### Actuadores (config/actuators.yaml)
Define pins, tipo (relay/mosfet), active_high, max_on_seconds. El firmware y simulador leen este archivo.

## 🌤️ Clima (OpenWeather)

El backend consulta el clima exterior y lo muestra en el dashboard y en la
página **Clima** (`/clima`). Es **informativo**: no controla el riego ni los
actuadores. Útil para decidir cuándo regar (si viene lluvia, la
evapotranspiración baja) y para vigilar tormentas.

1. Crea una cuenta en [openweathermap.org](https://openweathermap.org/api) y
   copia tu API key (el plan gratuito basta).
2. Ponla en `.env` y reinicia el backend:

   ```bash
   OPENWEATHER_API_KEY=tu_api_key
   ```

Sin clave configurada la sección de clima se oculta con un aviso, sin afectar
al resto del sistema.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `OPENWEATHER_API_KEY` | vacío | Clave de OpenWeather (solo en el backend) |
| `WEATHER_ENABLED` | `true` | Activa/desactiva la integración |
| `WEATHER_LAT` / `WEATHER_LON` | `14.3333` / `-91.0167` | Ubicación (Santa Lucía Cotzumalguapa) |
| `WEATHER_LOCATION_NAME` | `Santa Lucía Cotzumalguapa` | Nombre mostrado en la UI |
| `WEATHER_UNITS` / `WEATHER_LANG` | `metric` / `es` | Unidades y idioma de las descripciones |
| `WEATHER_CACHE_TTL_SEC` | `600` | Caché del pronóstico (protege la cuota gratuita) |
| `WEATHER_STALE_MAX_SEC` | `7200` | Tiempo máximo de servir datos viejos si OpenWeather falla |

Endpoints:

```bash
# Pronóstico normalizado (requiere sesión)
GET /api/weather/overview?hours=48
```

El plan gratuito da pasos de 3 h y 5 días de pronóstico (`pop` de lluvia y mm
acumulados); por eso el detalle fino de "lluvia en la próxima hora" no está
disponible. Los datos son de OpenWeather y el pronóstico no sustituye los
avisos oficiales (INSIVUMEH/CONRED).

## 📱 PWA y alertas de riego

La interfaz se puede instalar en el teléfono y enviar una notificación cuando
el suelo pide agua. Incluye navegación móvil, tablas en tarjetas, modo offline,
aviso persistente en el dashboard y Web Push en segundo plano.

```bash
# 1. Generar las claves VAPID (una vez; quedan en config/, ignoradas por git)
bash scripts/generate_vapid_keys.sh

# 2. Reconstruir la API y el frontend
docker compose up -d --build api frontend
```

Requisitos y pasos detallados: **[docs/pwa-notificaciones.md](docs/pwa-notificaciones.md)**.

> Las notificaciones, la instalación y el service worker exigen **HTTPS** (o
> `localhost`). En una IP LAN por HTTP el navegador las bloquea; la app lo
> avisa y mantiene el banner de riego dentro de la interfaz.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `NOTIFICATIONS_ENABLED` | `true` | Activa el vigilante de riego y los push. |
| `VAPID_PUBLIC_KEY_PATH` | `./config/vapid_public.pem` | Clave pública VAPID. |
| `VAPID_PRIVATE_KEY_PATH` | `./config/vapid_private.pem` | Clave privada VAPID (600). |
| `VAPID_SUBJECT` | `mailto:admin@greenhouse.local` | Contacto VAPID. |
| `IRRIGATION_CHECK_SEC` | `60` | Frecuencia de evaluación. |
| `IRRIGATION_REMINDER_HOURS` | `6` | Recordatorio mientras siga seco. |
| `IRRIGATION_MIN_VALID_SENSORS` | `1` | Sensores válidos mínimos. |
| `IRRIGATION_MAX_AGE_MIN` | `10` | No alertar con telemetría más vieja. |

La evaluación vive en `backend/api/app/irrigation.py` (histéresis compartida con
la automatización) y el envío en `backend/api/app/notifications.py`. El umbral
se configura en **Configuración → Humedad del Suelo**: `on_below_pct` dispara la
alerta y `off_above_pct` la resuelve.

Auditoría completa de la interfaz, hallazgos y estado de cada corrección:
**[docs/ui-audit.md](docs/ui-audit.md)**.

## 🔐 Seguridad

El detalle completo está en **[docs/seguridad.md](docs/seguridad.md)**.

- **Login:** bloqueo persistente por usuario (5 fallos/15 min) y por IP
  (20 fallos/15 min), con `429` + `Retry-After`, mensaje genérico y verificación
  dummy para no enumerar cuentas.
- **Borde:** Nginx limita `/api/auth/login` a 10 req/min por IP; Fail2ban
  opcional en `deploy/fail2ban/`. La API solo se publica en `127.0.0.1:8000`.
- **Sesión:** cookie `HttpOnly` + `SameSite=lax` (+ `Secure` en producción), sin
  JWT en `localStorage`; el WebSocket ya no acepta tokens en la URL.
- **CSRF:** comprobación de `Origin` en escrituras autenticadas por cookie.
- **Cabeceras:** CSP, HSTS, `nosniff`, `DENY`, COOP/CORP y Permissions-Policy.
- **API:** `/docs` deshabilitado en producción; CORS con orígenes explícitos.
- **Dependencias:** `pip-audit` y `npm audit` en verde y ejecutados en CI.

```bash
# Auditoría de dependencias
docker compose exec -T api pip install -q pip-audit && docker compose exec -T api pip-audit -r requirements.txt
cd frontend && npm audit

# Fail2ban (host)
cat deploy/fail2ban/README.md
```

> Para producción: `ENVIRONMENT=production`, HTTPS real y
> `AUTH_COOKIE_SECURE=true` (es el valor por defecto en producción). La API se
> niega a arrancar en producción con una cookie no segura.


## 🧪 Tests

```bash
# Backend
cd backend/api
pip install -r requirements.txt
DEVICE_API_TOKEN=test-device-token JWT_SECRET_KEY=test-secret-key-not-for-production pytest tests -q

# Frontend
cd frontend
npm ci
npm run lint
npm test
npm run build

# Lógica del firmware en host (requiere `pio run -e field` una vez)
bash firmware/field/tools/run_logic_tests.sh
bash firmware/gateway/scripts/check_payloads.sh
```

CI (`.github/workflows/ci.yml`) ejecuta pytest, lint, Vitest, build de frontend,
las pruebas de lógica y compila los tres nodos en cada push.

## 📡 Protocolo ESP-NOW (Para firmware Fase 5)

```
TELEMETRY: {ver, dev, seq, ts, soil[6]{adc,pct,ok}, bme{t,rh,p}, act[5], rssi}
CMD: {set_config, timesync, reboot, purge}
ACK/CHUNK: {seq, total, idx, crc16}
```

Gateway → Pi: JSON-lines + CRC16 a 115200 baudios por USB CDC.

## 🛑 Fail-Safe Implementado

- Sensor inválido **o congelado** (varianza ~0 durante 8 muestras) → actuador OFF
- Histéresis obligatoria (no on/off simple)
- `max_on_seconds` por actuador (bomba 900s, vent/hum 7200s); `0` significa
  "usar el default", nunca "ilimitado"
- `min_off_seconds` tras un corte por máximo (bomba 300s) y rearme solo con
  histéresis recuperada: se acabó el ciclo 15 min ON / 10 s OFF
- Arranque → pines de relé en OFF **antes** de `Serial.begin()`
- Watchdog de aplicación: si el `loop()` no avanza, una tarea fuerza `allOff()`
- Arranque → OFF hasta config NVS válida; se rechaza una versión de config
  inferior a la persistida
- Riego deshabilitado por defecto (`irrigation.enabled=false`)
- Watchdog comunicación 5min → evento persistido en `events` y alerta en la UI

## 📝 Próximos Pasos (Fase 5 - Firmware)

1. ~~Gateway ESP32 + bridge serial~~ (hecho: `firmware/gateway`, `backend/serial_bridge`)
2. Implementar `firmware/field` con PlatformIO sobre `firmware/common`
3. Drivers: BME280 I2C, 6x ADC1 capacitivo, UART CAM
4. NVS para config + calibración seco/húmedo por sensor
5. HAL actuadores leyendo `actuators.yaml`
6. Probar en banco sin 110V (LED en pines) → integrar

## 📄 Licencia

Proyecto académico / prototipo. Sin garantías. Uso bajo tu responsabilidad.
