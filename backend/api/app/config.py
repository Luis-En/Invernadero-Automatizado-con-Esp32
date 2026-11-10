from pathlib import Path
from typing import List, Optional
import ipaddress
import json
import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


DEFAULT_JWT_SECRET = "change-this-in-production"


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/greenhouse.db"
    JWT_SECRET_KEY: str = DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    # Session cookie for the browser. HttpOnly keeps the token away from
    # JavaScript; Secure defaults to true in production (use HTTPS). Bearer
    # tokens remain supported for devices, tests and API clients.
    AUTH_COOKIE_NAME: str = "greenhouse_session"
    AUTH_COOKIE_SECURE: Optional[str] = None
    AUTH_COOKIE_SAMESITE: str = "lax"
    # Login throttling (per IP and per username).
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_WINDOW_SEC: int = 900
    LOGIN_LOCKOUT_SEC: int = 900
    LOGIN_IP_MAX_FAILURES: int = 20
    LOGIN_IP_WINDOW_SEC: int = 900
    LOGIN_IP_LOCKOUT_SEC: int = 3600
    # Edge rate limiting (SlowAPI). Storage can be memory:// or redis://.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STORAGE_URI: str = "memory://"
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_ACTUATOR: str = "10/minute"
    RATE_LIMIT_WRITE: str = "30/minute"
    RATE_LIMIT_PHOTOS: str = "600/minute"
    # Proxy/HTTPS deployment.
    TRUSTED_PROXIES: str = "127.0.0.1/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,100.64.0.0/10,::1/128"
    PUBLIC_BASE_URL: str = ""
    REQUIRE_HTTPS: Optional[str] = None
    AUDIT_LOG_ENABLED: bool = True
    # Disable interactive API docs in production unless explicitly enabled.
    ENABLE_DOCS: Optional[str] = None
    # Shared secret used by the serial bridge / gateways for device endpoints.
    # Empty disables device ingestion (fail closed) instead of leaving the
    # telemetry and photo routes open.
    DEVICE_API_TOKEN: str = ""
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    PHOTO_STORAGE_PATH: str = "./data/photos"
    PHOTO_MAX_SIZE_MB: int = 5
    PHOTO_MAX_TOTAL_CHUNKS: int = 512
    PHOTO_MAX_CHUNKS_PER_MINUTE: int = 600
    PHOTO_RETENTION_DAYS: int = 30
    # Initial admin. When ADMIN_PASSWORD is empty no default account is
    # seeded, so a fresh deployment cannot be logged into with admin123.
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""
    ADMIN_EMAIL: str = "admin@greenhouse.local"
    # Weather (OpenWeather). The key stays server-side; the frontend only
    # talks to /api/weather.
    OPENWEATHER_API_KEY: str = ""
    WEATHER_ENABLED: bool = True
    WEATHER_LAT: float = 14.3333
    WEATHER_LON: float = -91.0167
    WEATHER_LOCATION_NAME: str = "Santa Lucía Cotzumalguapa"
    WEATHER_UNITS: str = "metric"
    WEATHER_LANG: str = "es"
    WEATHER_CACHE_TTL_SEC: int = 600
    WEATHER_STALE_MAX_SEC: int = 7200
    WEATHER_TIMEOUT_SEC: float = 8.0

    # Serial bridge command endpoint. The bridge owns the USB serial link to the
    # gateway and exposes this HTTP endpoint for actuator commands.
    SERIAL_BRIDGE_URL: str = "http://serial-bridge:8081"
    SERIAL_BRIDGE_TIMEOUT_SECONDS: float = 10.0

    # Web Push notifications for irrigation alerts. The VAPID key pair is
    # generated with scripts/generate_vapid_keys.sh and kept out of git.
    NOTIFICATIONS_ENABLED: bool = True
    VAPID_PUBLIC_KEY_PATH: str = "./config/vapid_public.pem"
    VAPID_PRIVATE_KEY_PATH: str = "./config/vapid_private.pem"
    VAPID_SUBJECT: str = "mailto:admin@greenhouse.local"
    VAPID_AUTO_GENERATE: bool = False
    IRRIGATION_CHECK_SEC: int = 60
    IRRIGATION_REMINDER_HOURS: float = 6.0
    IRRIGATION_MIN_VALID_SENSORS: int = 1
    # Older readings are stale; never alert from them.
    IRRIGATION_MAX_AGE_MIN: int = 10
    # Anchor for relative sqlite/photo paths when running from /app/app in Docker.
    APP_ROOT: str = "/app"

    class Config:
        extra = "ignore"  # Root .env also contains serial/frontend settings.
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, str):
            value = self.CORS_ORIGINS.strip()
            if not value:
                return []
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = [item.strip() for item in value.split(",") if item.strip()]
            if isinstance(parsed, str):
                return [parsed]
            return list(parsed)
        return self.CORS_ORIGINS

    @property
    def photo_max_bytes(self) -> int:
        return max(1, self.PHOTO_MAX_SIZE_MB) * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"prod", "production"}

    @property
    def auth_cookie_secure(self) -> bool:
        raw = (self.AUTH_COOKIE_SECURE or "").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        return self.is_production

    @property
    def docs_enabled(self) -> bool:
        raw = (self.ENABLE_DOCS or "").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        return not self.is_production

    @property
    def require_https(self) -> bool:
        raw = (self.REQUIRE_HTTPS or "").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        return self.is_production

    @property
    def trusted_proxy_networks(self) -> List:
        networks = []
        for item in (self.TRUSTED_PROXIES or "").split(","):
            candidate = item.strip()
            if not candidate:
                continue
            try:
                networks.append(ipaddress.ip_network(candidate, strict=False))
            except ValueError:
                logger.warning("TRUSTED_PROXIES entry is not a CIDR: %s", candidate)
        return networks

    @property
    def database_url_absolute(self) -> str:
        """Resolve a relative sqlite path against APP_ROOT.

        In Docker the app runs from /app/app, so './data/greenhouse.db' must
        be anchored to /app -> /app/data/greenhouse.db. Outside Docker (when
        /app does not exist) the URL is left untouched.
        """
        prefix = "sqlite+aiosqlite:///./"
        if not self.DATABASE_URL.startswith(prefix):
            return self.DATABASE_URL
        if Path(self.APP_ROOT).exists():
            relative = self.DATABASE_URL[len(prefix):]
            return "sqlite+aiosqlite:///" + str(Path(self.APP_ROOT) / relative)
        return self.DATABASE_URL

    @property
    def photo_storage_absolute(self) -> str:
        if self.PHOTO_STORAGE_PATH.startswith("./") and Path(self.APP_ROOT).exists():
            return str(Path(self.APP_ROOT) / self.PHOTO_STORAGE_PATH[2:])
        return self.PHOTO_STORAGE_PATH

    def _resolve_path(self, value: str) -> Path:
        if value.startswith("./") and Path(self.APP_ROOT).exists():
            return Path(self.APP_ROOT) / value[2:]
        return Path(value)

    @property
    def vapid_public_key_path(self) -> Path:
        return self._resolve_path(self.VAPID_PUBLIC_KEY_PATH)

    @property
    def vapid_private_key_path(self) -> Path:
        return self._resolve_path(self.VAPID_PRIVATE_KEY_PATH)

    @property
    def push_configured(self) -> bool:
        return (
            self.NOTIFICATIONS_ENABLED
            and self.vapid_public_key_path.is_file()
            and self.vapid_private_key_path.is_file()
        )


settings = Settings()


def validate_settings() -> None:
    """Fail closed on unsafe production configuration.

    The API refuses to start with the shipped JWT secret. Device ingestion is
    allowed to be disabled explicitly, but that is logged as a warning so the
    operator knows telemetry will be rejected.
    """
    secret = (settings.JWT_SECRET_KEY or "").strip()
    if not secret or secret == DEFAULT_JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET_KEY is the default value. Set a random secret "
            "(for example: openssl rand -hex 32) before starting the API."
        )
    if len(secret) < 16:
        raise RuntimeError("JWT_SECRET_KEY must be at least 16 characters long.")

    samesite = (settings.AUTH_COOKIE_SAMESITE or "lax").lower()
    if samesite not in {"lax", "strict", "none"}:
        raise RuntimeError("AUTH_COOKIE_SAMESITE must be lax, strict or none.")
    if samesite == "none" and not settings.auth_cookie_secure:
        raise RuntimeError("AUTH_COOKIE_SAMESITE=none requires AUTH_COOKIE_SECURE=true.")

    origins = settings.cors_origins_list
    if any(origin.strip() == "*" for origin in origins):
        raise RuntimeError(
            "CORS_ORIGINS cannot contain '*' when credentials are enabled. "
            "List the exact frontend origins instead."
        )

    token = (settings.DEVICE_API_TOKEN or "").strip()
    if token and len(token) < 16:
        raise RuntimeError("DEVICE_API_TOKEN must be at least 16 characters long.")

    admin_password = settings.ADMIN_PASSWORD or ""
    if admin_password and len(admin_password) < 12:
        raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters long.")

    public_base = (settings.PUBLIC_BASE_URL or "").strip()
    if settings.is_production and public_base and not public_base.startswith("https://"):
        raise RuntimeError("PUBLIC_BASE_URL must use https:// in production.")

    # Trigger parsing so malformed CIDRs are logged during startup.
    _ = settings.trusted_proxy_networks

    if settings.is_production and not settings.auth_cookie_secure:
        raise RuntimeError(
            "AUTH_COOKIE_SECURE must be enabled in production. Serve the app over HTTPS."
        )
