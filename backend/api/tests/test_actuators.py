from unittest.mock import patch
import pytest
from app.mqtt_commands import CommandTimeout, CommandUnavailable, CommandRejected


async def test_command_requires_admin(client, auth_viewer):
    response = await client.post("/api/actuators/fan_1/command", json={"state": True}, headers=auth_viewer)
    assert response.status_code == 403


async def test_command_requires_login(client):
    response = await client.post("/api/actuators/fan_1/command", json={"state": True})
    assert response.status_code == 401


@pytest.mark.parametrize("actuator", ["fan_1", "fan_2", "humidifier_1", "humidifier_2", "pump"])
@pytest.mark.parametrize("state", [True, False])
async def test_command_ack(client, auth_admin, actuator, state):
    if actuator == "pump" and state:
        await client.post("/api/config/apply", json={"config_json": {"irrigation": {"enabled": True}}}, headers=auth_admin)
    ack = {"command_id": "test", "actuator": actuator, "state": state, "status": "applied"}
    with patch("app.routes.actuators.send_command", return_value=ack) as send:
        response = await client.post(f"/api/actuators/{actuator}/command", json={"state": state}, headers=auth_admin)
        assert response.status_code == 200, response.text
        assert response.json()["state"] is state
        assert "confirmed_at" in response.json()
        send.assert_called_once_with(actuator, state)


@pytest.mark.parametrize("actuator,payload", [("unknown", {"state": True}), ("fan_1", {"state": "false"}), ("fan_1", {"state": 1})])
async def test_invalid_commands(client, auth_admin, actuator, payload):
    with patch("app.routes.actuators.send_command") as send:
        response = await client.post(f"/api/actuators/{actuator}/command", json=payload, headers=auth_admin)
        assert response.status_code == 422
        send.assert_not_called()


async def test_pump_interlock(client, auth_admin):
    await client.post("/api/config/apply", json={"config_json": {"irrigation": {"enabled": False}}}, headers=auth_admin)
    with patch("app.routes.actuators.send_command") as send:
        response = await client.post("/api/actuators/pump/command", json={"state": True}, headers=auth_admin)
        assert response.status_code == 409
        send.assert_not_called()


@pytest.mark.parametrize("error,code", [(CommandTimeout("timeout"), 504), (CommandUnavailable("offline"), 503), (CommandRejected("rejected"), 409)])
async def test_delivery_errors(client, auth_admin, error, code):
    with patch("app.routes.actuators.send_command", side_effect=error):
        response = await client.post("/api/actuators/fan_1/command", json={"state": True}, headers=auth_admin)
        assert response.status_code == code
