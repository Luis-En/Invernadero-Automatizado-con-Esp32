# Invernadero Automatizado - Santa Lucía Cotzumalguapa, Guatemala

Sistema completo de monitoreo y automatización para invernadero 19m x 4m con Raspberry Pi 5, ESP32 y sensores IoT.

## 🏗️ Arquitectura

```
ESP32-CAM ──WiFi (AP del campo)──▶ ESP32 Campo ──ESP-NOW 50m──▶ ESP32 Gateway ──USB──▶ RPi5
   captura JPEG                     6x suelo + BME280                  puente            │
                                     5 actuadores + automatización                        ▼
                                                                          FastAPI + SQLite + React
                                                                          (dashboard tiempo real vía WebSocket)
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

## 🚀 Despliegue Rápido (Simulación)

```bash
cd /home/luis/Proyectos/InvernaderoAuto

# 1. Configurar variables
cp .env.example .env
# Editar .env si necesitas cambiar puertos/paths

# 2. Levantar con Docker Compose
docker compose up --build -d

# 3. Ver logs
docker compose logs -f

# 4. Acceder a la UI
# http://localhost:5173
# Usuario: admin / admin123
# Usuario: viewer / viewer123
```

## 🧪 Verificación

```bash
# Backend API
curl http://localhost:8000/health

# Base de datos sembrada
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# WebSocket
# Abrir http://localhost:5173 -> Dashboard -> ver telemetría simulada cada 30s

# Fotos
# Cada 30min se genera foto dummy y aparece en /photos
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

Para verificar dos radios antes de armar el invernadero, presiona el botón en
una placa y el LED de la otra cambia (y viceversa). Compila para ESP32 y
ESP8266:

```bash
cd firmware/espnow_button_led
pio run -e esp32 -t upload
pio run -e esp8266 -t upload
```

## 🔧 Firmware

Tres nodos con PlatformIO, sobre una librería común (`firmware/common`) que
comparte el driver ESP-NOW, el protocolo y el CRC16:

| Nodo | Placa | Rol |
|------|-------|-----|
| `firmware/field` | ESP32 | 6 sensores de suelo + BME280, 5 actuadores, automatización y fail-safe |
| `firmware/gateway` | ESP32 | Puente ESP-NOW ↔ USB serial hacia la Raspberry Pi |
| `firmware/camera` | ESP32-CAM | Captura JPEG periódica → Wi-Fi al nodo de campo |

```bash
cd firmware/field   && pio run -e field     # compilar nodo de campo
cd firmware/gateway && pio run -e gateway   # compilar gateway
cd firmware/camera  && pio run -e camera    # compilar cámara
```

La lógica de automatización del firmware es un port fiel de
`backend/api/app/automation.py` y se prueba en el host con
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
│   │   ├── pages/           # Dashboard, Photos, History, Events, Config, Crops
│   │   ├── components/      # SensorCard, Charts, Layout
│   │   ├── context/         # AuthContext, TelemetryContext (WS)
│   │   └── api.js           # Cliente API + WS reconexión
│   └── Dockerfile
├── firmware/
│   ├── common/              # Protocolo, ESP-NOW HAL, botón, LED compartidos
│   ├── field/               # Nodo de campo ESP32
│   ├── gateway/             # Gateway ESP-NOW ↔ serial (ESP32 y ESP8266)
│   ├── camera/              # Nodo cámara ESP32-CAM
│   └── espnow_button_led/   # Prueba de enlace botón/LED (ESP32 y ESP8266)
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
```

### Actuadores (config/actuators.yaml)
Define pins, tipo (relay/mosfet), active_high, max_on_seconds. El firmware y simulador leen este archivo.

## 🧪 Tests

```bash
# Backend
cd backend/api
pip install -r requirements.txt pytest pytest-asyncio httpx
pytest app/test_main.py -v

# Frontend
cd frontend
npm install
npm run lint
npm run build
```

## 📡 Protocolo ESP-NOW (Para firmware Fase 5)

```
TELEMETRY: {ver, dev, seq, ts, soil[6]{adc,pct,ok}, bme{t,rh,p}, act[5], rssi}
CMD: {set_config, timesync, reboot, purge}
ACK/CHUNK: {seq, total, idx, crc16}
```

Gateway → Pi: JSON-lines + CRC16 a 115200 baudios por USB CDC.

## 🛑 Fail-Safe Implementado

- Sensor inválido → actuador OFF + evento
- Histéresis obligatoria (no on/off simple)
- `max_on_seconds` por actuador (bomba 900s, vent/hum 7200s)
- Arranque → OFF hasta config NVS válida
- Riego deshabilitado por defecto (`irrigation.enabled=false`)
- Watchdog comunicación 5min → alerta

## 📝 Próximos Pasos (Fase 5 - Firmware)

1. ~~Gateway ESP32 + bridge serial~~ (hecho: `firmware/gateway`, `backend/serial_bridge`)
2. Implementar `firmware/field` con PlatformIO sobre `firmware/common`
3. Drivers: BME280 I2C, 6x ADC1 capacitivo, UART CAM
4. NVS para config + calibración seco/húmedo por sensor
5. HAL actuadores leyendo `actuators.yaml`
6. Probar en banco sin 110V (LED en pines) → integrar

## 📄 Licencia

Proyecto académico / prototipo. Sin garantías. Uso bajo tu responsabilidad.