"""SlowAPI rate limiter shared by routers.

The key is the resolved client IP (honouring TRUSTED_PROXIES), not the raw
socket address. Storage defaults to memory because the app runs one Uvicorn
worker; set RATE_LIMIT_STORAGE_URI=redis://... to share limits across workers.
"""

from slowapi import Limiter

from app.config import settings
from app.security import client_ip


def rate_limit_key(request) -> str:
    return client_ip(request)


limiter = Limiter(
    key_func=rate_limit_key,
    enabled=settings.RATE_LIMIT_ENABLED,
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    default_limits=[],
)
