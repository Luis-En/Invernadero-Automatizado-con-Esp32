"""Real-time actuator fan-out to admin and public WebSocket clients."""

from app.realtime import broadcast_actuator_state


async def test_actuator_state_fans_out_to_both_managers(monkeypatch):
    from app.routes.config import manager
    from app.routes.public import public_manager

    received = []

    async def fake_broadcast(message):
        received.append(message)

    monkeypatch.setattr(manager, "broadcast", fake_broadcast)
    monkeypatch.setattr(public_manager, "broadcast", fake_broadcast)

    await broadcast_actuator_state("fan_2", True, source="manual")

    assert len(received) == 2
    assert all(message["type"] == "actuator_state" for message in received)
    assert all(message["data"]["actuator"] == "fan_2" for message in received)
    assert all(message["data"]["state"] is True for message in received)
