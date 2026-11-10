# PWA y notificaciones de riego

La interfaz es una PWA instalable y puede avisar al teléfono cuando la humedad
del suelo cae por debajo del umbral configurado. Este documento cubre la
instalación, las claves VAPID, HTTPS y la resolución de problemas.

## 1. Requisito imprescindible: HTTPS

Los navegadores solo permiten **service worker, instalación de PWA y
notificaciones** en un *contexto seguro*:

- `https://…` con un certificado válido, o
- `http://localhost` / `http://127.0.0.1` (solo para pruebas en el mismo equipo).

Abrir `http://192.168.1.50:5173` desde un teléfono **no** habilita ninguna de
las tres cosas. La app lo detecta y lo explica; el banner de riego y las
alertas locales siguen funcionando dentro de la app.

Opciones recomendadas para la LAN:

1. **Tailscale Serve** (más simple): instala Tailscale en la Raspberry Pi y en
   el teléfono y sirve el puerto 5173 con HTTPS automático.
   ```bash
   tailscale serve --bg 5173
   ```
2. **Caddy** como proxy inverso con certificado propio (o `mkcert`), confiando
   el certificado en el teléfono.
3. **Cloudflare Tunnel** si la Raspberry tiene salida a Internet.

No uses certificados autofirmados sin instalarlos en el teléfono: el navegador
los rechaza y el service worker no se registra.

## 2. Generar las claves VAPID

Las claves identifican al servidor ante el servicio de push del navegador. Se
generan una vez y se guardan fuera de git (`*.pem` ya está ignorado):

```bash
cd /home/luis/Proyectos/InvernaderoAuto
bash scripts/generate_vapid_keys.sh
```

Crea:

- `config/vapid_private.pem` (permisos 600, **nunca compartir**)
- `config/vapid_public.pem`

El contenedor de la API ya monta `./config` en `/app/config`. Reinicia:

```bash
docker compose up -d --build api
```

> Alternativa sin pasos manuales: deja `VAPID_AUTO_GENERATE=true` en el `.env`
> (es el valor de `.env.example` y de Dokploy). La API genera el par una sola
> vez en el primer arranque y lo guarda con permisos 600 en el volumen. Nunca
> sobrescribe claves existentes.

Comprueba el estado con una sesión de administrador:

```bash
curl -s http://localhost:8000/api/notifications/config \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Debe devolver `"push_supported": true` y una `vapid_public_key` en base64url.

> Al rotar las claves (`FORCE=1 bash scripts/generate_vapid_keys.sh`) todas las
> suscripciones existentes dejan de ser válidas: hay que desactivar y volver a
> activar las notificaciones en cada teléfono.

## 3. Instalar la app en el teléfono

### Android / Chrome

1. Abre la URL HTTPS.
2. Menú ⋮ → **Instalar aplicación** (o usa el banner “Instala el invernadero”).
3. Abre la app instalada, inicia sesión.
4. Toca la campana 🔔 → **Activar notificaciones push**.
5. Acepta el permiso y pulsa **Enviar prueba**.

### iPhone / iPad (iOS 16.4+)

1. Abre la URL HTTPS en **Safari**.
2. Compartir → **Añadir a pantalla de inicio**. La app muestra estos pasos
   directamente en el contenido principal cuando detecta iOS.
3. Abre la app **desde el icono** (no desde Safari).
4. Inicia sesión → campana 🔔 → **Activar notificaciones push**.

En iOS las notificaciones web solo existen con la PWA instalada; si abres la
web en una pestaña normal, no aparecerá el permiso.

## 4. Cuándo se avisa

El backend evalúa la última lectura cada `IRRIGATION_CHECK_SEC` (60 s):

1. Toma las seis humedades de suelo válidas (`soil_ok = true` y 0–100 %).
2. Calcula la media.
3. Aplica la histéresis de la configuración activa:
   - entra en “riego necesario” cuando la media es **≤ `on_below_pct`** (35 % por
     defecto);
   - sale cuando la media es **≥ `off_above_pct`** (45 % por defecto).
4. Si la lectura tiene más de `IRRIGATION_MAX_AGE_MIN` minutos (10 por
   defecto), **no alerta**: evita avisos de riego con el campo desconectado.
5. En la transición a seco crea un evento `IRRIGATION_NEEDED`, lo publica por
   WebSocket y envía un push.
6. Mientras siga seco, recuerda como máximo cada
   `IRRIGATION_REMINDER_HOURS` (6 h).
7. Al recuperarse crea `IRRIGATION_RESOLVED` (sin push).

El dashboard muestra siempre un banner de **Riego necesario** cuando
`/api/config/status` lo indica, aunque no haya permiso de notificaciones.

### Respaldo local (sin claves VAPID)

Si el servidor no tiene claves, el panel permite **alertas locales**: se usa el
service worker para mostrar una notificación al pasar de húmedo a seco mientras
la app está abierta o en segundo plano. Tiene un límite de una alerta cada 6 h.
Si existe una suscripción push, las alertas locales se omiten para no duplicar.

### Ciclo de vida de la suscripción

- Si el navegador rota el endpoint (`pushsubscriptionchange`), el service worker
  avisa a la app abierta; la app crea la nueva suscripción con la clave VAPID y
  la guarda en la API.
- Cada vez que se abre el panel, si el navegador ya tiene una suscripción, se
  reenvía a la API con un *upsert* idempotente. Esto repara una base de datos
  recreada o un despliegue nuevo sin obligar al usuario a desactivar y activar.
- La API desactiva automáticamente los endpoints que responden 404/410.

### Funcionamiento sin conexión

El service worker precachea el *shell*, `offline.html` y **todos** los chunks
JS/CSS del build desde `asset-manifest.json` (generado por Vite). Por eso una
ruta que nunca se había abierto, como `/admin/usuarios`, también funciona sin
red después de la primera instalación.

Si `/api/auth/me` falla por falta de red, la app conserva el último usuario
conocido (solo id, usuario y rol; nunca el token ni la contraseña) y muestra un
banner con “Reintentar” en lugar de redirigir al login. Las lecturas de
telemetría **no** se cachean a propósito: se muestran los últimos valores en
memoria y el aviso de datos desactualizados.

## 5. Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `NOTIFICATIONS_ENABLED` | `true` | Activa el vigilante y el envío de push. |
| `VAPID_PUBLIC_KEY_PATH` | `./config/vapid_public.pem` | Ruta de la clave pública. |
| `VAPID_PRIVATE_KEY_PATH` | `./config/vapid_private.pem` | Ruta de la clave privada. |
| `VAPID_SUBJECT` | `mailto:admin@greenhouse.local` | Contacto exigido por VAPID. |
| `VAPID_AUTO_GENERATE` | `true` en `.env.example` | Genera el par de claves en el primer arranque si no existen. |
| `IRRIGATION_CHECK_SEC` | `60` | Intervalo de evaluación (mínimo 15 s). |
| `IRRIGATION_REMINDER_HOURS` | `6` | Recordatorio mientras siga seco. |
| `IRRIGATION_MIN_VALID_SENSORS` | `1` | Sensores válidos mínimos para evaluar. |
| `IRRIGATION_MAX_AGE_MIN` | `10` | Antigüedad máxima de la lectura. |

Las rutas se resuelven contra `/app` dentro de Docker, donde `./config` es el
volumen `./config` del repositorio.

## 6. API

| Método | Ruta | Quién | Uso |
|--------|------|-------|-----|
| `GET` | `/api/notifications/config` | Sesión | Estado, clave pública y umbrales. |
| `POST` | `/api/notifications/subscribe` | Sesión | Alta/actualización de una suscripción. |
| `DELETE` | `/api/notifications/subscribe` | Sesión | Baja de la suscripción del usuario. |
| `POST` | `/api/notifications/test` | Sesión | Push de prueba a los dispositivos del usuario. |

Un endpoint de push debe ser HTTPS público; se rechazan `localhost`, rangos
privados, link-local, reservados y dominios `.local` para evitar SSRF. Las
suscripciones que devuelven 404/410 se desactivan automáticamente.

## 7. Probar sin teléfono

```bash
# 1. Comprobar que el servidor tiene claves
curl -s http://localhost:8000/api/notifications/config -H "Authorization: Bearer $TOKEN"

# 2. Enviar una prueba a las suscripciones del usuario
curl -s -X POST http://localhost:8000/api/notifications/test -H "Authorization: Bearer $TOKEN"

# 3. Simular suelo seco (detén antes el serial-bridge para que no lo pise)
curl -s -X POST http://localhost:8000/api/config/telemetry \
  -H "X-Device-Token: $DEVICE_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"timestamp":"2026-01-01T12:00:00Z","temperature":26,"humidity":70,"pressure":1013,
       "soil_adc":[2000,2000,2000,2000,2000,2000],
       "soil_pct":[15,16,17,14,15,16],"soil_ok":[true,true,true,true,true,true],
       "fan_1_state":false,"fan_2_state":false,"humidifier_1_state":false,
       "humidifier_2_state":false,"pump_state":false,"rssi":-60,
       "device_id":"field_esp32","sequence":999}'
```

Ajusta la marca de tiempo a la hora UTC actual; el vigilante ignora lecturas de
más de 10 minutos.

Pruebas automáticas:

```bash
docker compose exec -T api python -m pytest tests/test_notifications.py -q
```

## 8. Problemas frecuentes

**“Permiso denegado”.** El navegador recordó un bloqueo anterior. Ajustes del
sitio → Notificaciones → Permitir. En Chrome de escritorio se puede restablecer
desde el icono del candado.

**“El servidor no tiene claves VAPID”.** Falta ejecutar el script o la API se
reinició antes de crear los archivos. Verifica que `/app/config/vapid_private.pem`
existe dentro del contenedor.

**No aparece el botón de instalar.** La URL no es HTTPS o ya está instalada. En
iOS no hay banner del navegador: la propia app muestra los pasos de
Compartir → Añadir a pantalla de inicio.

**La prueba dice 404 “No hay dispositivos suscritos”.** Activa primero las
notificaciones en ese teléfono; la prueba solo llega a las suscripciones del
usuario actual.

**El push llega pero al tocarlo no abre.** Comprueba que la app esté instalada y
que la URL de `url` sea `/`.

**Avisos duplicados.** No deberían: las alertas locales se omiten si existe una
suscripción push. Si ejecutas varios procesos de la API, cada uno tiene su
propio vigilante; usa un solo worker de Uvicorn.

**Tras un despliegue, una página no abre sin conexión.** Abre la app una vez con
red; el service worker lee `asset-manifest.json`, descarga los chunks nuevos y
purga los de builds anteriores. Si aparece el aviso “nueva versión”, pulsa
**Actualizar** para activar el service worker nuevo.
