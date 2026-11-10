"""Administrative API. Every route requires role=admin."""

from fastapi import APIRouter, Depends

from app.dependencies import require_role
from app.routes.admin import actuators, config, crops, health, logs, users

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_role("admin"))],
)

router.include_router(actuators.router)
router.include_router(crops.router)
router.include_router(config.router)
router.include_router(logs.router)
router.include_router(health.router)
router.include_router(users.router)
