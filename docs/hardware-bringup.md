# Puesta en marcha con ESP32 (arquitectura Wi-Fi)

Arquitectura actual: la cámara manda las fotos **por Wi-Fi** al nodo de campo,
y el campo las reenvía al gateway por ESP-NOW. El gateway va por USB a la
Raspberry Pi (o al PC), que las guarda y las muestra en la web.

```
ESP32-CAM ──WiFi (AP del campo)──▶ ESP32 CAMPO ──ESP-NOW──▶ ESP32 GATEWAY ──USB──▶ Raspberry Pi
   │                                   │                                                  │
 captura JPEG                   6 sensores + BME280                               FastAPI + WebSocket
                                 automatización                                    Dashboard en tiempo real
```

No hace falta router: el nodo de campo levanta su propia red Wi-Fi y la cámara
se conecta a ella.

## Placas necesarias

| Nodo | Placa | Entorno PlatformIO |
|------|-------|--------------------|
| Campo | ESP32 (DevKit) | `field` o `field_bringup` |
| Gateway | ESP32 (DevKit) | `gateway` |
| Cámara | ESP32-CAM AI-Thinker | `camera` |

> Las tres placas deben estar en el **canal 6** (ya configurado) para que
> ESP-NOW y el AP de la cámara coincidan.

---

## Paso 1 — Sensor de humedad en el nodo de campo

**Cableado del sensor capacitivo v1.2:**

| Sensor | ESP32 campo |
|--------|-------------|
| VCC | 3V3 |
| GND | GND |
| AOUT | GPIO35 ("D35") |

### Configurar qué sensores están conectados

En `firmware/field/include/config.h`, `FIELD_SOIL_MASK` indica qué sondas están
físicamente puestas. Con solo la de D35:

```c
#define FIELD_SOIL_MASK 0x08   // bit 3 = B1 = GPIO35
```

| Bit | Sensor | GPIO |
|-----|--------|------|
| 0 | A1 | 32 |
| 1 | A2 | 33 |
| 2 | A3 | 34 |
| 3 | B1 | **35 (D35)** |
| 4 | B2 | 36 |
| 5 | B3 | 39 |

Para el invernadero completo con 6 sondas: `0x3F`.

Las sondas **no conectadas se reportan como inválidas** (no como "desconectadas
cada ciclo"), así que el dashboard no muestra falsos problemas.

### Flashear el campo en modo bring-up

```bash
cd firmware/field
pio run -e field_bringup -t upload
pio device monitor
```

`field_bringup` muestrea cada 2 s y publica cada 5 s para que la web se
actualice casi en vivo mientras pruebas los sensores.

**Calibración:** igual que en el ESP8266, por comandos serial:
- sonda al aire → escribe `cal dry`
- sonda en agua → escribe `cal wet`
- `show` para ver la lectura

> La calibración por comandos serial se implementó en el firmware del ESP8266.
> En el ESP32 el cálculo usa `SOIL_DRY_DEFAULT`/`SOIL_WET_DEFAULT`; si quieres
> comandos de calibración también ahí, dímelo y los agrego.

---

## Paso 2 — Gateway ESP32 por USB

**Cableado:** gateway por USB al PC (o a la Raspberry Pi). Nada más.

```bash
cd firmware/gateway
pio run -e gateway -t upload
pio device monitor
```

Verás `hello` del gateway y, cuando el campo esté encendido, `telemetry`.

---

## Paso 3 — Cámara ESP32-CAM por Wi-Fi

**Conexión:** alimenta la ESP32-CAM (5V por el shield USB o fuente). No necesita
cables de datos; se conecta a la red `invernadero-campo` que levanta el campo.

```bash
cd firmware/camera
pio run -e camera -t upload
pio device monitor
```

Debes ver:

```
[camera] camera ready
[camera] Wi-Fi connected  ssid=invernadero-campo
[camera] POST -> http://192.168.4.1/photo
[camera] frame 1 uploaded
```

Y en el monitor del **campo**:

```
[photo] frame 1 received over WiFi: 30022 bytes
[photo] frame 1 forwarded as 151 chunks
```

---

## Paso 4 — Ver los datos en tiempo real en la web

Arranca el backend con el gateway real conectado por USB:

```bash
cd /home/luis/Proyectos/InvernaderoAuto
SERIAL_DEVICE=/dev/ttyUSB0 docker compose \
  -f docker-compose.yml -f docker-compose.serial.yml up -d
```

Averigua el puerto con `pio device list`.

Abre **http://localhost:5173** (admin / admin123). El Dashboard muestra:
- El sensor conectado (B1) con su porcentaje real
- Los demás como "Sin datos"
- "Campo" en verde
- La última fotografía
- Actualización automática por WebSocket en cada telemetría (cada 5 s en
  `field_bringup`)

---

## Cambiar las credenciales del Wi-Fi del campo

En `firmware/field/include/config.h`:

```c
#define FIELD_AP_SSID "invernadero-campo"
#define FIELD_AP_PASSWORD "invernadero123"
#define FIELD_AP_CHANNEL 6
```

Y en `firmware/camera/include/config.h` deben coincidir:

```c
#define CAM_WIFI_SSID "invernadero-campo"
#define CAM_WIFI_PASSWORD "invernadero123"
#define CAM_WIFI_CHANNEL 6
#define CAM_FIELD_HOST "192.168.4.1"   // IP del AP del campo
```

> La contraseña debe tener **8 caracteres o más** o el ESP32 no arranca el AP.

---

## Solución de problemas

| Síntoma | Causa probable |
|---------|----------------|
| La cámara no se conecta | SSID/clave distintos entre campo y cámara |
| La cámara se conecta pero el POST falla | `CAM_FIELD_HOST` no es `192.168.4.1`, o el campo reinició |
| El campo no reenvía la foto | Canal ESP-NOW ≠ canal del gateway (debe ser 6) |
| La web no muestra el sensor | `FIELD_SOIL_MASK` sin el bit del sensor conectado |
| Sensor siempre 0 % o 100 % | Falta calibrar (`cal dry` / `cal wet`) |
| `latest/file` da 404 | Aún no se ha reensamblado ninguna foto completa |

## Entornos de compilación

| Comando | Placa | Uso |
|---------|-------|-----|
| `pio run -e field_bringup` | ESP32 | **campo con sensor real, telemetría rápida** |
| `pio run -e field` | ESP32 | campo completo (6 sensores, 30 s) |
| `pio run -e gateway` | ESP32 | gateway ESP-NOW ↔ USB |
| `pio run -e camera` | ESP32-CAM | cámara por Wi-Fi |
| `pio run -e field_photo_test` | ESP32 | diagnóstico (solo UART, legado) |
