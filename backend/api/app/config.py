from pathlib import Path
from typing import List
import json
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/greenhouse.db"
    JWT_SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    PHOTO_STORAGE_PATH: str = "./data/photos"
    PHOTO_MAX_SIZE_MB: int = 5
    PHOTO_RETENTION_DAYS: int = 30
    # Anchor for relative sqlite/photo paths when running from /app/app in Docker.
    APP_ROOT: str = "/app"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, str):
            return json.loads(self.CORS_ORIGINS)
        return self.CORS_ORIGINS

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


settings = Settings()
