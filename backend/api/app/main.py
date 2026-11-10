import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings, validate_settings
from app.database import init_db
from app.routes import auth, crops, config, photos, events, actuators, weather, notifications, public
from app.routes.admin import router as admin_router
from app.notifications import (
    ensure_vapid_keys,
    start_irrigation_watcher,
    stop_irrigation_watcher,
)
from app.rate_limit import limiter
from app import seed

logger = logging.getLogger(__name__)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_settings()
    if not (settings.DEVICE_API_TOKEN or "").strip():
        logger.warning(
            "DEVICE_API_TOKEN is empty: telemetry and photo chunk ingestion "
            "will reject every device request."
        )
    await init_db()
    await seed.ensure_seed_data()
    ensure_vapid_keys()
    if settings.push_configured:
        logger.info("Web Push de riego habilitado")
    elif settings.NOTIFICATIONS_ENABLED:
        logger.warning(
            "Web Push deshabilitado: faltan %s o %s",
            settings.vapid_public_key_path,
            settings.vapid_private_key_path,
        )
    start_irrigation_watcher()
    try:
        yield
    finally:
        await stop_irrigation_watcher()


docs_enabled = settings.docs_enabled
app = FastAPI(
    title="Greenhouse Automation API",
    description="Backend for greenhouse monitoring and automation system",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

cors_origins = list(settings.cors_origins_list)
if (settings.PUBLIC_BASE_URL or "").strip():
    public_origin = urlparse(settings.PUBLIC_BASE_URL.strip())
    if public_origin.scheme and public_origin.netloc:
        origin = f"{public_origin.scheme}://{public_origin.netloc}"
        if origin not in cors_origins:
            cors_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Token", "X-Requested-With"],
    expose_headers=["Retry-After"],
    max_age=600,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def enforce_https(request: Request, call_next):
    """In production behind a TLS proxy, every API call must be HTTPS.

    /health is exempt so the container healthcheck can probe it locally. The
    proxy must forward X-Forwarded-Proto: https (see nginx.production.conf).
    """
    if settings.require_https and request.url.path.startswith("/api/"):
        forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
        if forwarded != "https" and request.url.scheme != "https":
            return JSONResponse(
                status_code=403,
                content={"detail": "HTTPS requerido"},
            )
    return await call_next(request)


@app.middleware("http")
async def csrf_origin_guard(request: Request, call_next):
    """Reject cross-site unsafe requests.

    SameSite already blocks most CSRF. This is defence in depth: any browser
    unsafe method that carries an Origin header must come from the same origin
    (or an explicitly allowed CORS origin). Non-browser clients such as the
    serial bridge do not send Origin and are unaffected.
    """
    if request.method in UNSAFE_METHODS:
        origin = request.headers.get("origin")
        if origin:
            host = request.headers.get("host", "")
            allowed = set(settings.cors_origins_list)
            if host:
                # TLS may terminate at Tailscale/Caddy/Cloudflare before Nginx,
                # so accept both schemes for the same public host.
                allowed.add(f"http://{host}")
                allowed.add(f"https://{host}")
            parsed = urlparse(origin)
            if not parsed.scheme or not parsed.netloc or origin not in allowed:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Origen de la petición no permitido"},
                )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), camera=(), microphone=()"
    )

    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    if forwarded_proto == "https" or request.url.scheme == "https":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )

    if request.url.path.startswith("/api/") or request.url.path == "/openapi.json":
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Pragma", "no-cache")
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
    return response


app.include_router(actuators.router)
app.include_router(auth.router)
app.include_router(crops.router)
app.include_router(config.router)
app.include_router(photos.router)
app.include_router(events.router)
app.include_router(weather.router)
app.include_router(notifications.router)
app.include_router(public.router)
app.include_router(admin_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "greenhouse-api"}
