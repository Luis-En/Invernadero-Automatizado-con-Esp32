# Seguridad del backend y del frontend

Fecha: 2026-11-06  
Alcance: API FastAPI, autenticación, sesiones, Nginx, contenedores, frontend
React/PWA y dependencias.

## Resumen de controles implementados

| Área | Control |
|------|---------|
| Fuerza bruta | SlowAPI 5/min + bloqueo persistente por usuario/IP + límite en Nginx + Fail2ban opcional |
| Contraseñas | bcrypt coste 12, mínimo 12 caracteres, rehash automático de hashes legados |
| Enumeración | Mensaje genérico, verificación dummy para usuarios inexistentes |
| Sesión web | Cookie `HttpOnly`, `SameSite=lax`, `Secure` en producción, sin token en `localStorage` |
| WebSocket | Autenticación por cookie o `Authorization: Bearer`; ya no acepta `?token=` |
| CSRF | `SameSite` + comprobación de `Origin` en métodos de escritura autenticados por cookie |
| JWT | PyJWT, algoritmo fijado, `exp`/`iat`/`nbf` obligatorios, tipo `access` |
| Cabeceras | CSP, HSTS, `nosniff`, `DENY`, COOP/CORP, Permissions-Policy |
| API | Puerto publicado solo en loopback; `/docs` deshabilitado en producción |
| Público/Admin | Lectura pública redactada; escrituras solo rol `admin` bajo `/api/admin` |
| Auditoría | `audit_logs` para logins y todas las acciones administrativas |
| Fotos | Rutas confinadas al directorio de fotos y validación de cabecera JPEG |
| SSRF | Endpoints de Web Push validados y bloqueo de rangos privados |
| Dependencias | `pip-audit` y `npm audit` sin vulnerabilidades conocidas |
| Contenedores | `cap_drop`, `no-new-privileges`, límites de recursos y logs rotables |

## 1. Protección contra fuerza bruta

### En la aplicación

Cada intento fallido se contabiliza en la tabla `auth_throttle` (SQLite), no en
memoria: reiniciar el proceso **no** borra el bloqueo.

- Por **usuario**: 5 fallos en 15 min → bloqueo 15 min.
- Por **IP**: 20 fallos en 15 min → bloqueo 60 min.
- Al alcanzar el umbral se devuelve `429` con `Retry-After`.
- El bloqueo se comprueba antes de verificar la contraseña, así que también
  protege el coste de bcrypt.
- Un login correcto limpia ambos contadores.
- Los intentos de usuarios inexistentes también cuentan y reciben la misma
  respuesta, para no revelar qué cuentas existen.
- Se registra un evento `AUTH_LOCKOUT` (con IP hasheada) visible para el admin.
- Las filas se podan a los 7 días.

Variables:

```bash
LOGIN_MAX_FAILURES=5
LOGIN_WINDOW_SEC=900
LOGIN_LOCKOUT_SEC=900
LOGIN_IP_MAX_FAILURES=20
LOGIN_IP_WINDOW_SEC=900
LOGIN_IP_LOCKOUT_SEC=3600
```

### En el borde (Nginx)

`/api/auth/login` acepta 10 peticiones/minuto por IP con un burst de 5
(`limit_req zone=login burst=5 nodelay`). Devuelve 429 y queda en el access log.

Además, el puerto de la API se publica como `127.0.0.1:8000:8000`: desde la LAN
solo se puede llegar a la API a través de Nginx en `:5173`, sin saltarse el
límite.

### Fail2ban (opcional)

Instalación y verificación: **`deploy/fail2ban/README.md`**. El filtro lee
`data/logs/nginx/access.log`, y la acción banea en la cadena `DOCKER-USER`
(necesaria con puertos publicados por Docker).

- 5 respuestas 401/403/429 en 10 min → 1 hora de DROP, con incremento hasta 1
  semana.
- `ignoreip` incluye solo loopback.

Sin Fail2ban, el bloqueo de la aplicación y el límite de Nginx siguen activos.

## 2. Sesiones y CSRF

- El login devuelve el usuario y establece la cookie `greenhouse_session`:
  `HttpOnly`, `SameSite=lax`, `Path=/`, `Max-Age` igual a la expiración del JWT.
- En producción (`ENVIRONMENT=production`) `Secure` se activa por defecto. La
  API **no arranca** en producción con una cookie no segura.
- El frontend ya **no guarda el JWT en `localStorage`**. Al recargar, recupera
  la sesión con `GET /api/auth/me` usando la cookie.
- `POST /api/auth/logout` borra la cookie.
- El WebSocket se autentica con la cookie. Se eliminó el token en la query
  string para que no acabe en logs de Nginx/Uvicorn.
- Los clientes máquina (bridge, pruebas, integraciones) siguen usando
  `Authorization: Bearer`.
- En métodos `POST/PUT/PATCH/DELETE` autenticados por cookie, si el navegador
  envía `Origin`, debe coincidir con el host o con `CORS_ORIGINS`; si no, 403.

Variables:

```bash
AUTH_COOKIE_NAME=greenhouse_session
AUTH_COOKIE_SAMESITE=lax
# AUTH_COOKIE_SECURE=true   # por defecto true en producción
```

`SameSite=none` exige `AUTH_COOKIE_SECURE=true` y no se recomienda.

## 3. Contraseñas y JWT

- Contraseñas de 12 a 72 bytes UTF-8 (límite real de bcrypt).
- La política exige minúscula, mayúscula, número y símbolo al **crear o cambiar**
  una contraseña. El login no la aplica: rechazar una contraseña heredada en el
  inicio de sesión bloquearía cuentas en vez de protegerlas.
- bcrypt con coste 12.
- Los hashes `sha256_crypt` heredados se aceptan una vez y se reemplazan por
  bcrypt en el siguiente login correcto.
- Usuarios inexistentes se comparan contra un hash dummy para igualar tiempos.
- JWT firmado con HS256, con `exp`, `iat`, `nbf`, `sub`, `role` y `type=access`.
- Se exige `exp`, `sub` e `iat` al decodificar; un token de otro tipo se rechaza.
- El secreto debe tener al menos 16 caracteres; el arranque falla con el valor
  de ejemplo.

Recomendación: baja `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` a 60–480 según el uso. Un
token robado sigue siendo válido hasta su expiración: no hay lista de revocación
por sesión. Rotar `JWT_SECRET_KEY` cierra todas las sesiones.

## 4. Cabeceras, CORS y exposición

- Nginx: CSP estricta, `frame-ancestors 'none'`, HSTS, `nosniff`, `DENY`,
  COOP/CORP, Permissions-Policy y `server_tokens off`.
- API: `Cache-Control: no-store` y CSP `default-src 'none'` en `/api/`.
- CORS solo con orígenes explícitos; `*` con credenciales se rechaza al
  arrancar.
- `/docs`, `/redoc` y `/openapi.json` se deshabilitan cuando
  `ENVIRONMENT=production`, salvo `ENABLE_DOCS=true`.
- El puerto 8000 no se publica en la LAN.
- Nginx oculta la cabecera `Server` del upstream y Uvicorn arranca con
  `--no-server-header`.

## 5. Fotos, archivos y SSRF

- Las rutas de fotos se resuelven y deben quedar dentro de `PHOTO_STORAGE_PATH`;
  una fila manipulada con `/etc/passwd` devuelve 404.
- Un archivo reensamblado debe empezar por la firma JPEG (`FF D8 FF`); si no, se
  elimina y se devuelve 400.
- Los chunks tienen CRC16, límite por chunk y por foto, y límite por dispositivo
  y minuto.
- Los endpoints de suscripción push exigen HTTPS público y rechazan loopback,
  rangos privados, link-local, reservados y `.local`.
- No hay SQL crudo ni `dangerouslySetInnerHTML`; React escapa el contenido.

## 6. Contenedores y dependencias

- `cap_drop: ALL` en API y bridge. La API reañade `DAC_OVERRIDE` y `FOWNER`
  porque los volúmenes pertenecen al usuario del host y la base debe quedar en
  modo `600`; el bridge reañade `DAC_OVERRIDE` para el dispositivo serial.
- `no-new-privileges:true` en API, bridge y frontend.
- Límites de CPU/memoria y logs de Docker con rotación.
- Acceso de Nginx persistido en `data/logs/nginx/` para auditoría/Fail2ban.
- El servidor de desarrollo Vite escucha en `127.0.0.1` por defecto;
  `VITE_DEV_HOST=0.0.0.0` solo debe usarse en una red de confianza.
- La base SQLite se fuerza a modo `600` al arrancar (contiene hashes y
  telemetría). `data/`, `data/photos/` y `data/logs/` quedan en `700` para el
  usuario del host; `.env`, las claves VAPID y las copias de `backups/` quedan
  en `600/700` (`scripts/backup.sh` aplica `umask 077`).
- Dependencias fijadas y auditadas:
  - `pip-audit -r requirements.txt` → **0 vulnerabilidades conocidas**.
  - `npm audit` (incluye dev) → **0 vulnerabilidades**.
  - CI ejecuta ambas auditorías en cada push.

La API sigue ejecutándose como root dentro del contenedor por la propiedad de
los volúmenes `data/` creados por versiones anteriores. Es una deuda conocida:
en un despliegue nuevo se puede ejecutar como UID 1000 y hacer
`chown -R 1000:1000 data config`.

## 7. Verificación realizada

- Login correcto por Nginx: `200`, cookie `HttpOnly; SameSite=lax`.
- `GET /api/auth/me` solo con cookie: `200`.
- Logout: `204` y `me` posterior: `401`.
- 5 contraseñas incorrectas seguidas: `401 401 401 401 401 429`.
- Evento `AUTH_LOCKOUT` creado y visible en la API.
- WebSocket conectado con cookie sin token en la URL.
- Ruta de foto fuera del almacenamiento: `404`.
- Tests backend: **126** (incluye lockout, SlowAPI, cookie, CSRF, IP, hashes legados,
  endpoints públicos, roles admin/viewer y auditoría,
  fotos y cabeceras).
- Tests frontend: **16**.

## 8. Checklist de despliegue

1. `JWT_SECRET_KEY` y `DEVICE_API_TOKEN` aleatorios (mínimo 16 caracteres;
   recomendado 32 bytes).
2. `ADMIN_PASSWORD` fuerte y único.
3. HTTPS real (Tailscale Serve, Caddy o Cloudflare Tunnel).
4. `ENVIRONMENT=production` y `AUTH_COOKIE_SECURE=true` (o dejar el default).
5. `CORS_ORIGINS` con los orígenes exactos; nunca `*`.
6. Firewall: permitir 5173 solo desde la red/VPN; 8000 permanece en loopback.
7. Instalar Fail2ban si el equipo está expuesto.
8. Copias de `data/greenhouse.db`, `config/*.pem` y `.env` con permisos 600.
9. Revisar `data/logs/nginx` y los eventos `AUTH_LOCKOUT`.
10. Mantener `pip-audit` y `npm audit` en verde.


## 9. Superficie pública, roles y auditoría (v2)

- `/api/public/*` es lectura sin sesión y devuelve datos redactados: no incluye
  `device_id`, RSSI, secuencia, notas internas ni rutas de archivos. El
  WebSocket público solo transmite telemetría y limita a 100 conexiones.
- `/api/admin/*` exige rol `admin`. Un token de `viewer` recibe `403`; sin token,
  `401`. Esto se aplica a actuadores, cultivos, configuración, logs y salud.
- `audit_logs` registra `auth.login_success`, `auth.login_failed`,
  `auth.login_blocked`, `user.create`, `actuator.control`, `crop.*`,
  `crop.params.*` y `config.apply`. El admin los consulta en
  `GET /api/admin/logs` o en `/admin/logs`.
- SlowAPI añade límites por IP: login 5/min, actuadores 10/min, escrituras
  30/min y chunks de foto 600/min. El almacenamiento en memoria asume un solo
  worker; para varios usa `RATE_LIMIT_STORAGE_URI=redis://...`.
- La API y el frontal solo escuchan en `127.0.0.1` en producción. El túnel debe
  enviar `X-Forwarded-Proto: https`; sin él, la API responde `403 HTTPS
  requerido` y Nginx redirige a HTTPS.
- El servidor de desarrollo Vite escucha en loopback; `VITE_DEV_HOST=0.0.0.0`
  solo para pruebas en red confiable.
- En Dokploy las claves VAPID se generan en el volumen nombrado `vapid_keys`
  (`VAPID_AUTO_GENERATE=true`), nunca en el repositorio. La base y las fotos
  viven en `greenhouse_data`.

## 10. Riesgos residuales

- No hay MFA ni recuperación de contraseña autoservicio.
- No hay revocación por sesión; rotar el secreto cierra todas.
- El token sigue apareciendo en el cuerpo del login (los clientes máquina lo
  necesitan), aunque el navegador no lo persiste.
- El token de dispositivo es compartido por todos los gateways; rotarlo requiere
  actualizar el firmware.
- El enlace con el gateway es USB serial local; no hay broker expuesto en la LAN.
- `config/passwd` de Mosquitto debe ser legible por el contenedor del broker;
  contiene hashes, no contraseñas en claro. Restringe el acceso al host.
- Si se usa un túnel/proxy, `$remote_addr` puede ser el proxy y el baneo por IP
  debe hacerse en el perímetro.
- La API es un solo worker; el estado del vigilante de riego no se comparte
  entre réplicas.
