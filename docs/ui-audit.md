# Auditoría de la interfaz web y plan de corrección

Fecha: 2026-11-03  
Alcance: `frontend/` (React 18 + Vite + Recharts) y la API que alimenta la
interfaz (`backend/api`).  
Método: revisión de código, ejecución real con Docker Compose, inspección de la
interfaz a 390×844 px y 1440×900 px, y verificación de los flujos de API con
`curl` y `pytest`.

## Resumen ejecutivo

La interfaz funcionaba en escritorio, pero no era utilizable con comodidad en
un teléfono: el encabezado medía 826 px dentro de un viewport de 390 px, las
tablas de configuración/cultivos/eventos no tenían una versión móvil, los
formularios tenían etiquetas sin asociar y no existía ninguna base PWA ni de
notificaciones.

Se corrigieron los hallazgos de severidad alta y media. El resultado es una app
instalable (manifest + service worker + iconos + modo offline), navegación
móvil tipo aplicación, tablas convertidas en tarjetas, modales tipo *bottom
sheet* con foco atrapado y un sistema completo de alertas de riego por Web Push
con respaldo local y aviso persistente en el dashboard.

| Área | Antes | Después |
|------|-------|---------|
| Ancho mínimo real del encabezado | 826 px (desborde) | ≤ 390 px |
| Navegación móvil | Enlaces fuera de pantalla | Barra inferior + cajón lateral |
| Tablas a 390 px | Scroll horizontal de 8 columnas | Tarjetas con etiquetas |
| Objetivo táctil mínimo | 20–38 px | 44 px |
| PWA | Sin manifest, SW ni iconos | Instalable + offline + actualización |
| Notificación de riego | No existía | Push en segundo plano + respaldo local |
| Bundle inicial (gzip) | 193.96 kB | 66.66 kB |
| Etiquetas de formulario sin asociar | Login, Config, Crops | Asociadas o con `aria-label` |
| `100vh` en móvil | Login/layout | `100dvh` + `safe-area-inset-*` |

## Hallazgos y estado

Severidad: **Crítica** impide el uso; **Alta** degrada tareas principales;
**Media** afecta accesibilidad/experiencia; **Baja** mejora recomendable.

### Responsive y layout

| ID | Severidad | Hallazgo y evidencia | Corrección | Estado |
|----|-----------|----------------------|------------|--------|
| R1 | Crítica | El `header` con 7 enlaces medía 826 px en un viewport de 390 px; los últimos enlaces quedaban fuera de pantalla. | Cajón lateral accesible y barra inferior de 5 accesos; navegación de escritorio desde 901 px. | Corregido |
| R2 | Alta | `.grid-6/.grid-4/.grid-3/.grid-2` colapsaban a **una** columna a ≤768 px, generando páginas de 6.000 px. | `auto-fit` con `minmax()`; 2 columnas de sensores/fotos en teléfono. | Corregido |
| R3 | Alta | Tablas de 5–8 columnas solo con scroll horizontal; ilegibles en teléfono. | Modo `.table-cards` con `data-label`, `caption` y `scope`; el encabezado sigue disponible para lectores de pantalla. | Corregido |
| R4 | Alta | Modales con `max-height: 90vh`, cuerpo de 70vh y sin safe area; el teclado móvil podía tapar acciones. | Componente `Modal` en portal, *bottom sheet* en móvil, cuerpo con scroll propio y `100dvh`. | Corregido |
| R5 | Alta | Botones de 20–38 px; enlaces sueltos de 20 px. | Objetivo táctil de 44 px en botones, navegación y campos; enlaces de cabecera con 24 px mínimo. | Corregido |
| R6 | Media | `100vh` en login/layout provocaba saltos con la barra del navegador. | `100dvh` con respaldo `100vh` y paddings `env(safe-area-inset-*)`. | Corregido |
| R7 | Media | Recharts con altura fija y etiquetas densas en pantallas pequeñas. | Altura `clamp(220px, 40vw, 300px)` y `minTickGap`; contenedores fluidos. | Corregido |
| R8 | Media | Tabla de configuración y catálogo se desbordaban en escritorio estrecho. | Contenedor con scroll táctil y versión tarjeta por debajo de 720 px. | Corregido |
| R9 | Baja | El selector de clima/historial no siempre tenía etiqueta visible. | `label` asociado en Historial y `aria-label` en Dashboard. | Corregido |

### Accesibilidad (WCAG 2.2 AA)

| ID | Severidad | Hallazgo y evidencia | Corrección | Estado |
|----|-----------|----------------------|------------|--------|
| A1 | Alta | Los `label` de Login, Config y Crops no tenían `htmlFor`/`id`; el nombre accesible del campo estaba vacío. | Todos los campos tienen `id` + `label`, o `aria-label` cuando el texto visible no basta. | Corregido |
| A2 | Alta | No había *skip link*, `main` identificable ni `aria-current` en la navegación. | Skip link, `main#main-content`, `aria-current="page"` y `nav` con nombre accesible. | Corregido |
| A3 | Alta | Los modales no atrapaban el foco, no cerraban con Escape ni devolvían el foco. | Hook `useDialog`: foco inicial, trampa de Tab, Escape, bloqueo de scroll y restauración. | Corregido |
| A4 | Alta | Los errores y avisos aparecían sin `role="alert"`/`aria-live`. | Alertas críticas con `role="alert"`; avisos de estado con `role="status"`. | Corregido |
| A5 | Alta | Los gráficos eran SVG sin alternativa textual. | `role="img"` con resumen de último/mín/máx por gráfico; resumen por sensor en suelo. | Corregido |
| A6 | Media | Los encabezados de tabla no tenían `scope`, las tablas no tenían `caption` ni región desplazable accesible. | `caption` oculto, `scope="col"`, `tabIndex=0`/`role="region"` en tablas de solo scroll. | Corregido |
| A7 | Media | El filtro de eventos no anunciaba el estado seleccionado. | `aria-pressed` en cada pestaña de severidad. | Corregido |
| A8 | Media | `--color-warning: #f77f00` sobre blanco daba ~2.9:1; también se usaban rojos claros en Historial. | Naranja de texto `#b45309`, rojo `#b91c1c`, azul `#1d4ed8`; fondos suaves separados. | Corregido |
| A9 | Media | No había estilo de foco uniforme ni soporte de movimiento reducido. | `:focus-visible` global y `prefers-reduced-motion`. | Corregido |
| A10 | Media | Login sin `autocomplete`, sin `inputmode` ni estado de carga anunciado. | `autocomplete="username"/"current-password"`, `autoCapitalize` off, estados `role="status"`. | Corregido |
| A11 | Baja | Emojis decorativos podían leerse dos veces. | `aria-hidden="true"` en iconos decorativos; etiquetas textuales junto a estados. | Corregido |
| A12 | Baja | El checkbox de riego no tenía un área táctil clara. | Etiqueta clicable de 44 px y `aria-label`. | Corregido |

### PWA e instalación

| ID | Severidad | Hallazgo y evidencia | Corrección | Estado |
|----|-----------|----------------------|------------|--------|
| P1 | Alta | Sin `manifest`, iconos, `theme-color`, `apple-touch-icon` ni service worker. | Manifest completo, iconos 192/512/maskable/apple/badge y metadatos iOS. | Corregido |
| P2 | Alta | Sin funcionamiento offline ni shell cacheado. | `sw.js` con shell, assets, navegación *network-first* y página `offline.html`. | Corregido |
| P3 | Media | Sin flujo de instalación ni aviso de actualización. | Banner `beforeinstallprompt`, instrucciones iOS y aviso “nueva versión”. | Corregido |
| P4 | Media | `viewport` sin `viewport-fit=cover`; sin safe areas. | `viewport-fit=cover` y `env(safe-area-inset-*)`. | Corregido |
| P5 | Media | El bundle inicial cargaba todas las páginas y Recharts. | Rutas con `React.lazy`; el bundle inicial bajó de 193.96 a 66.66 kB gzip. | Corregido |
| P6 | Crítica (operativa) | En una IP LAN por HTTP el navegador no permite service worker, instalación ni notificaciones. | Documentado y con aviso dentro de la app; requiere HTTPS (ver `docs/pwa-notificaciones.md`). | Limitación documentada |
| P7 | Baja | La CSP no declaraba `worker-src` ni `manifest-src`. | CSP ampliada, `Permissions-Policy` y cache correcta para `sw.js`. | Corregido |

### Notificaciones de riego

| ID | Severidad | Hallazgo y evidencia | Corrección | Estado |
|----|-----------|----------------------|------------|--------|
| N1 | Alta | No existía ningún aviso de riego, ni en pantalla ni en el teléfono. | Banner persistente en Dashboard + panel de notificaciones + Web Push. | Corregido |
| N2 | Alta | No había una evaluación única de “riego necesario”; el dashboard solo pintaba umbrales sueltos. | `app/irrigation.py` con histéresis compartida por `/status` y el vigilante. | Corregido |
| N3 | Crítica | Una lectura vieja podía declarar riego necesario con el campo desconectado. | `IRRIGATION_MAX_AGE_MIN` (10 min) y `telemetry_stale`; no se alerta con datos viejos. | Corregido |
| N4 | Alta | Riesgo de aviso repetido por oscilación del sensor. | Estado con histéresis, recordatorio cada 6 h y evento único por episodio. | Corregido |
| N5 | Alta | Sin claves VAPID ni almacenamiento de suscripciones. | Script de claves, modelo `push_subscriptions`, migración 0002 y endpoints. | Corregido |
| N6 | Alta | Un endpoint de push arbitrario podía apuntar a la red interna (SSRF). | Validación HTTPS + rechazo de loopback, privadas, link-local, reservadas y `.local`. | Corregido |
| N7 | Media | Suscripciones muertas (404/410) se acumularían. | Se desactivan automáticamente al enviar. | Corregido |
| N8 | Media | El permiso se pediría sin contexto. | Solo desde un clic en el panel, con explicación y estado del permiso. | Corregido |
| N9 | Media | iPhone requiere instalar la app para push. | Instrucciones dentro del cajón y en la documentación. | Corregido |
| N10 | Media | Sin alternativa si no hay VAPID o HTTPS. | Alertas locales con la app abierta y banner in-app siempre disponible. | Corregido |
| N11 | Baja | No había forma de comprobar la cadena completa. | Botón “Enviar prueba” y endpoint `/api/notifications/test`. | Corregido |

### Seguridad, privacidad y rendimiento

| ID | Severidad | Hallazgo | Estado |
|----|-----------|----------|--------|
| S1 | Alta | Clave privada VAPID nunca debe versionarse. | `*.pem` en `.gitignore`, permisos 600, generación local. |
| S2 | Media | El JWT se guarda en `localStorage` (expuesto ante XSS). | Residual; se mitiga con CSP estricta. Recomendación: cookie `HttpOnly` + CSRF. |
| S3 | Media | El payload de push debe ser mínimo. | Solo título, humedad, umbral y URL interna. |
| S4 | Baja | El catálogo de cultivos mostraba “—” porque `/api/crops/all` no incluía parámetros. | Corregido con `selectinload(Crop.params)`. |
| S5 | Baja | El texto de fotos decía “cada 3 minutos” aunque la simulación usa 30 min. | Texto neutral basado en configuración. |

## Verificación realizada

- `npm run lint` → sin errores.
- `npm test` → 16 pruebas (5 archivos).
- `npm run build` → correcto; rutas divididas en chunks.
- `pytest` en el contenedor → **126 pruebas** (se omite únicamente
  `test_serial_contract.py`, que espera un montaje `/app/serial_bridge` no
  presente en este contenedor; es una limitación del entorno, no del cambio).
- API real: `/api/notifications/config` devuelve la clave pública VAPID;
  `/api/config/status` devuelve `soil_avg_pct`, `irrigation_needed` y
  `telemetry_stale`.
- Vigilante real: al publicar una lectura de suelo al 15.5 % se creó el evento
  `IRRIGATION_NEEDED` de severidad `critical` (y se habría enviado push si
  hubiera suscripciones).
- Navegación verificada a 390×844 y 1440×900: cajón, barra inferior, tablas
  tarjeta, modal de cultivos, panel de notificaciones y galería.

## Recomendaciones pendientes (no bloqueantes)

1. Servir la app por HTTPS en la LAN (Tailscale Serve, Caddy o certificado
   local) para habilitar instalación y push en teléfonos reales.
2. Ejecutar Lighthouse y axe en un dispositivo físico; el entorno de auditoría
   no permite completar la instalación ni conceder permisos.
3. Migrar el JWT a cookie `HttpOnly` + `SameSite=Strict` y añadir CSRF.
4. Añadir modo oscuro con `prefers-color-scheme` si se usará de noche.
5. Valorar notificaciones de “campo desconectado” además de riego.

---

## Segunda auditoría — 2026-11-09

Alcance: revisión de código de `frontend/`, build de producción, navegador real a
320, 390, 768 y 1440 px, comprobación del manifest/service worker/cachés y prueba
offline con el servidor apagado. La API de prueba se sirvió con datos simulados
para aislar la interfaz.

### Resumen

La base ya era sólida (shell responsive, tablas tarjeta, modal *bottom sheet*,
PWA instalable y push de riego). Esta pasada encontró problemas de **borde**
que solo aparecen en anchos concretos, en el arranque sin red y en los
despliegues: el nav de escritorio se recortaba entre 1240 y 1439 px, el banner
de riego comprimía el diagnóstico en móvil, los *chunks* diferidos no estaban
cacheados y, sin red, la app cerraba la sesión y podía quedar en blanco.

| Área | Antes | Después |
|------|-------|---------|
| Nav de escritorio | Recortado a 1240 px (“Con…”) | Patrón móvil hasta 1439; completo desde 1440 |
| Banner de riego en 390 px | Texto en columna de ~200 px | Acción a fila completa; texto legible |
| Filtros de Eventos en 390 px | “Crítico” cortado | Envuelven en ≤480 px |
| Chunks diferidos offline | Solo los ya visitados | 25/25 precacheados por manifest de build |
| Sesión sin red | Redirección a login / pantalla en blanco | Última sesión conocida + banner + reintento |
| Umbrales de sensores | 30/40 fijos, podían contradecir el banner | `soil_threshold_pct` real (admin y público) |
| Tablas con scroll | Región no enfocable | `tabIndex=0`, `role=region`, `aria-label` |
| Bundle inicial (gzip) | 66.66 kB | 67.61 kB (+0.95 kB, sin dependencias nuevas) |

### Responsive y layout

| ID | Severidad | Hallazgo y evidencia | Corrección | Estado |
|----|-----------|----------------------|------------|--------|
| R10 | Alta | A 1240 px el nav de escritorio se recortaba: “Configuración” aparecía como “Con…” y los badges de dispositivo se solapaban. El corte estaba en 1101 px, antes de que el contenido cupiera. | El patrón móvil (drawer + barra inferior) se mantiene hasta 1439 px; el nav completo aparece desde 1440 px, donde se verificó que cabe. | Corregido |
| R11 | Alta | En 390 px el botón “Revisar riego” del banner dejaba el diagnóstico en una columna de ~200 px. | `.irrigation-banner` envuelve y la acción ocupa una fila completa en ≤640 px. | Corregido |
| R12 | Media | En Eventos, la pestaña “Crítico” quedaba cortada a 390 px. | Las pestañas envuelven en ≤480 px y reducen su padding. | Corregido |
| R13 | Media | Las cifras principales usaban `fontSize: '3rem'` en línea, sin adaptarse a 320 px. | Clases `.metric-value` / `.metric-unit` con `clamp()`; 30 px en móvil, 48 px en escritorio. | Corregido |
| R14 | Media | “Detalles” de Auditoría se alineaba a la derecha y partía el JSON en varias líneas ilegibles. | Las celdas largas (Detalles, Acción, Recurso) pasan a bloque a la izquierda; Detalles usa monoespaciado y `overflow-wrap: anywhere`. | Corregido |
| R15 | Media | A 320 px los `legend` de Configuración se solapaban con el borde del `fieldset` y “(Histéresis)” se partía. | Títulos cortos (“Temperatura”, “Humedad ambiental”, “Humedad del suelo”) y fondo del `legend` igual al de la tarjeta. | Corregido |
| R16 | Baja | `.grid-6` y `.photo-grid` no daban dos columnas en 320/360 px. | Mínimos reducidos a 104 px y 132 px respectivamente. | Corregido |
| R17 | Baja | Las safe areas solo cubrían arriba/abajo; en horizontal con notch el contenido podía quedar bajo la cámara. | `env(safe-area-inset-left/right)` en header, main, footer, drawer, toasts y barra inferior. | Corregido |
| R18 | Baja | En móvil el indicador de conexión se reducía a un punto suelto junto a la campana y se confundía con una alerta. | Se oculta en ≤640 px; el cajón conserva “Datos en vivo / Reconectando…”. | Corregido |
| R19 | Media | El botón “Actualizar” del dashboard se deshabilitaba sin WebSocket, justo cuando el usuario necesita forzar una lectura. | El botón siempre está disponible; el polling HTTP sigue funcionando sin WebSocket. | Corregido |
| R20 | Media | Si la primera carga de telemetría fallaba, el dashboard mostraba el spinner para siempre. | Estado de error explícito con “Reintentar”. | Corregido |
| R21 | Baja | En páginas públicas con sesión iniciada se abría un segundo WebSocket de administración además del público. | El contexto de administración solo abre WS en `/admin/*`; en público refresca estado cada 60 s para la campana y las alertas locales. | Corregido |

### Accesibilidad (WCAG 2.2 AA)

| ID | Severidad | Hallazgo y evidencia | Corrección | Estado |
|----|-----------|----------------------|------------|--------|
| A13 | Media | En Eventos, “Reconocido” usaba `badge-off` sin la clase base `badge`, así que perdía la píldora y el contraste del estado. | `badge badge-off` / `badge badge-warning`. | Corregido |
| A14 | Media | Las cinco tablas con scroll horizontal no eran enfocables por teclado (el estilo `:focus-visible` existía pero no se usaba). | `tabIndex={0}`, `role="region"` y `aria-label` en Config, Eventos, Cultivos, Auditoría y Usuarios. | Corregido |
| A15 | Media | Al cambiar de ruta en la SPA no había anuncio ni movimiento de foco; un lector de pantalla seguía en el enlace anterior. | `RouteAnnouncer`: foco en `main#main-content` sin scroll y anuncio `aria-live` con el título de la página. | Corregido |
| A16 | Baja | Los botones de actuador no exponían su estado ni la operación en curso. | `aria-pressed`, `aria-busy` y `aria-label="Encender/Apagar <nombre>"`. | Corregido |
| A17 | Baja | La campana no indicaba si el panel estaba abierto. | `aria-expanded` en el botón. | Corregido |
| A18 | Baja | Al ocultar el texto del indicador de conexión en móvil, el estado quedaba sin nombre accesible. | `role="status"`, `aria-live="polite"` y `aria-label` descriptivo. | Corregido |
| A19 | Baja | La herramienta de inspección marcó los campos de alta de usuario sin nombre accesible, aunque tenían `label for`. | `aria-label` explícito añadido a usuario, email y contraseña. | Corregido |

### PWA, offline y notificaciones

| ID | Severidad | Hallazgo y evidencia | Corrección | Estado |
|----|-----------|----------------------|------------|--------|
| P8 | Crítica | Sin red, `/api/auth/me` fallaba y se interpretaba como “sin sesión”: la app redirigía a login. Si la ruta no se había visitado, su chunk no estaba cacheado y quedaba una pantalla en blanco. | Se recuerda el último usuario (solo id/usuario/rol, nunca credenciales), `authOffline` evita la redirección y muestra un banner con reintento; los chunks se precachean. | Corregido |
| P9 | Alta | Los chunks de ruta (`React.lazy`) no se cacheaban hasta visitarlos, así que offline solo funcionaban las páginas ya abiertas. | Vite emite `asset-manifest.json` en cada build; el SW precachea todos los JS/CSS y, en cada navegación online, refresca el manifest y purga assets de builds anteriores. | Corregido |
| P10 | Media | `offline.html` usaba `onclick="location.reload()"`, bloqueado por la CSP `script-src 'self'`; el botón “Reintentar” no hacía nada. | Sustituido por un enlace real `href="/"` con el mismo aspecto de botón. | Corregido |
| P11 | Media | En iOS las instrucciones de instalación solo aparecían dentro del cajón de administración. | El banner de instalación muestra los pasos de Safari en el contenido principal cuando no hay `beforeinstallprompt`. | Corregido |
| P12 | Media | Los atajos del manifest apuntaban a `/eventos`, que redirige al login de administración. | Atajos públicos `/`, `/fotos`, `/clima`; añadidos `launch_handler` y `prefer_related_applications`. | Corregido |
| P13 | Media | Una suscripción push rotada por el navegador, o un redespliegue con BD nueva, dejaba de enviar avisos aunque el teléfono siguiera suscrito. | La app reenvía la suscripción existente al cargar (upsert idempotente) y atiende `pushsubscriptionchange` del SW para renovarla. | Corregido |
| P14 | Baja | El push no distinguía alertas críticas y podía descartarse con el resto. | `requireInteraction` en alertas críticas, `timestamp` y `renotify` con `tag`. | Corregido |
| P15 | Baja | El SW tenía una versión fija (`v1`), así que los assets nuevos no se precacheaban en despliegues normales. | Versión `v4` + refresco por `asset-manifest.json`, independiente del despliegue. | Corregido |
| N12 | Media | El dashboard coloreaba los sensores con umbrales fijos 30/40 y podía contradecir el banner y el push configurados. | Usa `soil_threshold_pct`; `/api/public/telemetry` expone `soil_threshold_pct` y `soil_off_above_pct` (solo los umbrales, sin el resto de la configuración). | Corregido |
| N13 | Baja | `soil_avg_general` nulo podía imprimir “undefined%” en el banner público. | Formateador `fmtPct` con guion. | Corregido |
| N14 | Media | `.env.example` traía `VAPID_AUTO_GENERATE=false`, así que una instalación nueva no podía enviar push sin un paso manual. | El ejemplo usa `true`; Dokploy ya lo hacía. | Corregido |

### Verificación realizada

- `npm run lint` → sin errores.
- `npm test` → **20 pruebas** en 6 archivos, incluidas las nuevas de aviso local
  de riego y del estado offline de `RequireAuth`.
- `npm run build` → correcto; 25 assets en `asset-manifest.json`.
- Navegador real: 320, 390, 768, 1439 y 1440 px; dashboard admin y público,
  configuración, cultivos, eventos, auditoría, clima, cajón y modal de
  notificaciones.
- PWA: manifest servido como `application/manifest+json`, 3 atajos, service
  worker `v4` activo, **25/25 assets precacheados**, `offline.html` y shell en
  caché, `PushManager` disponible en contexto seguro.
- Offline real: con el servidor apagado se abrió `/admin/usuarios` (ruta nunca
  visitada) y la app renderizó la última sesión, el banner de desconexión y el
  error de API, sin redirección ni pantalla en blanco.
- Backend: `python3` validó la sintaxis de `schemas.py` y `routes/public.py`.
  `pytest` no está instalado en este entorno, así que la suite de API no se
  ejecutó aquí; el campo nuevo de telemetría pública queda cubierto por
  `tests/test_public_endpoints.py`.

### Limitaciones que siguen abiertas

1. **HTTPS es obligatorio** para instalar y para push en un teléfono real. En
   una IP LAN por HTTP el banner y las alertas locales siguen funcionando, pero
   el navegador no permite SW, instalación ni permisos.
2. La prueba de push de extremo a extremo (permiso real + servicio de push)
   requiere un dispositivo y un origen HTTPS; en este entorno el permiso está
   denegado por el navegador de auditoría.
3. Queda pendiente probar en un iPhone físico con iOS 16.4+ (instalación desde
   Safari y push en modo *standalone*).
4. Modo oscuro y notificaciones de “campo desconectado” siguen siendo mejoras
   no bloqueantes.
