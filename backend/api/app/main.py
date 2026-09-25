from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import init_db
from app.routes import auth, crops, config, photos, events
from app import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed.ensure_seed_data()
    yield


app = FastAPI(
    title="Greenhouse Automation API",
    description="Backend for greenhouse monitoring and automation system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(crops.router)
app.include_router(config.router)
app.include_router(photos.router)
app.include_router(events.router)

_photo_dir = Path(settings.photo_storage_absolute)
if _photo_dir.exists():
    app.mount("/photos", StaticFiles(directory=str(_photo_dir)), name="photos")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "greenhouse-api"}