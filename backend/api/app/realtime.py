"""Real-time fan-out for actuator changes.

The field node reports actuator states with each telemetry frame, but a manual
command must be visible immediately to every public visitor and every admin
dashboard. This helper broadcasts the confirmed state to both WebSocket groups.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def broadcast_actuator_state(
    actuator: str,
    state: bool,
    source: str = "manual",
) -> None:
    message = {
        "type": "actuator_state",
        "data": {
            "actuator": actuator,
            "state": bool(state),
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Admin dashboards.
    try:
        from app.routes.config import manager

        await manager.broadcast(message)
    except Exception:  # noqa: BLE001 - a socket failure must not fail the command
        logger.warning("No se pudo difundir el estado del actuador a los admins")

    # Public dashboard/visitors.
    try:
        from app.routes.public import public_manager

        await public_manager.broadcast(message)
    except Exception:  # noqa: BLE001
        logger.warning("No se pudo difundir el estado del actuador al público")
