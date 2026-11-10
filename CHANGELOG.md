# Changelog

All notable changes to this project. Format based on Keep a Changelog and
[Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-11-06 — Public access with roles

### Added

- Public, unauthenticated read-only API (`/api/public/telemetry`, history,
  photos, weather, crops) with redacted payloads and a public WebSocket that
  only broadcasts telemetry.
- Public dashboard/gallery/weather at `/`, `/fotos` and `/clima`; the previous
  authenticated interface moved to `/admin/*`.
- Admin-only API under `/api/admin/*` for actuators, crops, configuration,
  audit logs and detailed health. Viewer accounts receive 403.
- Audit trail (`audit_logs`) for successful/failed/blocked logins and every
  admin action, with filters at `GET /api/admin/logs`.
- SlowAPI limits (login 5/min, actuators 10/min, writes 30/min, photo chunks
  600/min) and the `RATE_LIMIT_*` configuration.
- HTTPS enforcement middleware for production (`X-Forwarded-Proto`) and a
  production Nginx config with HTTP→HTTPS redirect and health endpoint.
- Production compose override, `scripts/setup_first_admin.sh`, and
  `docs/deploy-public.md`.
- Dokploy + Cloudflare Tunnel deployment file (`docker-compose.dokploy.yml`),
  remote serial bridge compose, automatic VAPID generation and
  `docs/deploy-dokploy-cloudflare.md`.

## [Unreleased]

### Security

- Login brute-force protection: persistent per-username and per-IP lockouts,
  `429` + `Retry-After`, generic errors, dummy bcrypt verification for unknown
  users and `AUTH_LOCKOUT` events (`docs/seguridad.md`).
- Nginx rate limit for `/api/auth/login` (10 req/min per IP), API published only
  on `127.0.0.1:8000`, and optional Fail2ban integration that bans in
  `DOCKER-USER` (`deploy/fail2ban/`).
- Browser sessions moved to an `HttpOnly`, `SameSite` cookie; the JWT is no
  longer stored in `localStorage`, and the WebSocket no longer accepts tokens
  in the query string. Added logout endpoint and Origin-based CSRF guard.
- Migrated JWT from python-jose to PyJWT with required `exp`/`sub`/`iat` and
  token-type validation.
- Password policy: 12–72 UTF-8 bytes, bcrypt cost 12, automatic rehash of
  legacy `sha256_crypt` hashes on login.
- Production hardening: `/docs` disabled in production, CORS wildcard rejected,
  Secure-cookie enforcement, hardened security headers (CSP/HSTS/COOP/CORP),
  `server_tokens off`, `--no-server-header`, capability drops and
  `no-new-privileges` for containers.
- Photos: stored paths confined to the photo root and reassembled files must be
  valid JPEGs.
- Dependencies upgraded to remove all known CVEs (FastAPI/Starlette,
  python-multipart, PyJWT, cryptography, python-dotenv, pytest, React Router 7,
  Vite 8 and Vitest 5). CI now runs `pip-audit` and `npm audit`.

### Added

- Field boot banner with role and firmware version, so the flashed build is
  identifiable before the radio initialization.
- PWA: installable manifest, service worker with offline shell, app icons,
  install prompt, update notice and iOS metadata (`docs/pwa-notificaciones.md`).
- Irrigation alerts: shared hysteresis assessment, persistent dashboard banner,
  background Web Push watcher, VAPID key generation, per-device subscriptions,
  test notification and `IRRIGATION_NEEDED` / `IRRIGATION_RESOLVED` events.
  Alerts are suppressed when telemetry is older than `IRRIGATION_MAX_AGE_MIN`.
- Responsive app shell: mobile drawer plus bottom navigation, card-style tables,
  bottom-sheet modals, 44 px touch targets and safe-area support.
- Accessibility: labelled form fields, skip link, focus trap/Escape/restore in
  dialogs, `aria-current`, live regions, accessible chart summaries, table
  captions/scopes, reduced-motion support and WCAG-AA text colours.
- Frontend route-level code splitting (initial bundle 193.96 kB → 64.35 kB gzip).
- `docs/ui-audit.md` with the full interface audit and per-finding status.

### Changed

- Desktop navigation now appears only from 1440 px; below that the app keeps the
  drawer + bottom-navigation pattern, so no link is clipped on 1240–1439 px
  laptops.
- Dashboard metrics use fluid `clamp()` sizes; sensor colours follow the
  configured soil threshold instead of fixed 30/40 values.
- Public pages reuse the admin status poll only every 60 s and do not open a
  second admin WebSocket, reducing phone battery/network use.

### Removed

- MQTT control channel (backend, firmware and broker config). Actuator
  commands now go through the authenticated admin API, and device ingestion
  uses the shared `DEVICE_API_TOKEN` over HTTP.

### Fixed

- Offline PWA: the last known user (id/username/role, no credentials) is kept
  when `/api/auth/me` fails with a network error, so routes no longer redirect
  to login or render blank. All lazy chunks are precached from a Vite-generated
  `asset-manifest.json`, refreshed and pruned on every online navigation.
- `offline.html` retry button works under the CSP (was an inline `onclick`).
- iOS shows the install instructions in the main content, not only in the admin
  drawer.
- Push subscriptions are re-synced on app load and renewed on
  `pushsubscriptionchange`; critical alerts use `requireInteraction`.
- Mobile layout: irrigation banner action, event tabs, audit details, fieldset
  legends, safe-area insets, photo/sensor grids and the connection indicator.
- Accessible table scroll regions, SPA route announcements, actuator
  `aria-pressed`/`aria-busy`, bell `aria-expanded` and explicit field labels.
- `/api/crops/all` now includes each crop's parameters (the catalogue showed
  only dashes).
- `/api/config/status` reports the soil average, threshold, valid sensor count
  and staleness so the dashboard can explain an irrigation alert.
- Photos page no longer claims a fixed 3-minute capture interval.
- Reference `SensorMonitor` no longer raises `KeyError("soil_0")` after eight
  samples; the simulator keeps publishing telemetry instead of stalling.
  Regression test added.

## [1.2.0] - 2026-11-03

### Security (P0)

- Control configuration is validated on both sides: physical bounds, ordered
  ON/OFF hysteresis, and `max_on_seconds = 0` now means "use the default",
  never "unlimited". Negative values are rejected instead of wrapping to
  ~49 days.
- Pump cooldown: after a max-ON cut the pump requires `min_off_seconds`
  (default 300 s) **and** a recovered hysteresis demand before it can restart.
- Device authentication: telemetry, photo chunks, config confirmation, events
  and the WebSocket require a shared `DEVICE_API_TOKEN` / user JWT. The static
  `/photos` mount is gone; images are served by the authenticated router.
- ESP-NOW supports PMK + LMK and a pinned gateway MAC, with duplicate/old
  sequence rejection and refusal of config versions older than NVS.
- No default `admin123`/`viewer123` accounts. The API refuses to start with the
  shipped JWT secret; `ADMIN_PASSWORD` creates the initial admin.
- Password hashing defaults to bcrypt (existing sha256 hashes still verify).
- Frozen sensors are detected from the variance of the last 8 samples.
- Field node: application watchdog forces `allOff()` if the loop stalls;
  relay pins are driven OFF before `Serial.begin()`.
- `wifi_photo` checks buffers before `memcpy` and answers 503 when an upload
  is dropped.

### Added (P1)

- Persisted gateway events (`FIELD_OFFLINE`, `CAMERA_OFFLINE`, …) through
  `POST /api/events/device`; manual commands write `actuator_log`.
- Validated telemetry schema with ranges, 6-slot arrays and UTC-normalized
  timestamps; absurd clocks are rejected.
- Photo limits: `PHOTO_MAX_SIZE_MB`, total chunk cap and per-device rate limit.
- Static frontend served by Nginx with relative API URLs and a same-origin
  WebSocket path.
- Alembic migrations (`backend/api/alembic`), CI workflow, npm lockfile,
  ESLint config and Vitest tests.
- Backup script (`scripts/backup.sh`).
- Automated-logic parity test between the Python reference and the firmware
  cases.

### Changed

- Spanish route names (`/fotos`, `/historial`, `/eventos`, `/configuracion`,
  `/cultivos`) with legacy redirects.
- Config UI uses `??` instead of `||`, so a valid `0` is preserved.
- Frontend parses naive backend timestamps as UTC.

### Fixed

- Dashboard timezone offset for naive UTC timestamps.
- Telemetry WebSocket no longer reconnects when the history range changes.
- Camera retries `esp_camera_init` after a failure and runs capture/upload in
  a task instead of blocking the main loop.
- `field_scan` skips ADC2 pins (GPIO25/26) that cannot work with the radio on.
- ESP8266 persists the epoch only when it changes by more than 60 s and pairs
  `EEPROM.begin()`/`EEPROM.end()`.

## [1.1.0] - 2026-09-13

- Initial public snapshot: FastAPI backend, React dashboard, serial bridge,
  field/gateway/camera firmware and ESP-NOW protocol.
