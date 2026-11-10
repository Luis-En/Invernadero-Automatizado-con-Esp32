"""Firmware <-> backend parity cases.

These are the same scenarios exercised by
`firmware/field/tools/logic_tests.cpp` (CI runs both). Keeping them in one
place documents the intended equivalence: hysteresis, fail-safe on invalid
readings, max-ON cut, and the pump cooldown with hysteresis recovery.
"""
from app.automation import ActuatorRuntime, compute_actuator_states

CONFIG = {
    "hysteresis": {
        "temp": {"on_above": 30.0, "off_below": 27.5},
        "humidity": {"on_below": 60.0, "off_above": 68.0},
        "soil": {"on_below_pct": 35, "off_above_pct": 45},
    },
    "irrigation": {"enabled": True},
    "safety": {
        "max_on_seconds": {"fan": 7200, "humidifier": 7200, "pump": 900},
        "min_off_seconds": {"fan": 0, "humidifier": 0, "pump": 300},
    },
}

OFF = {
    "fan_1": False, "fan_2": False, "humidifier_1": False,
    "humidifier_2": False, "pump": False,
}


def _run(temp, hum, soil, current=None, runtime=None, now=0.0):
    return compute_actuator_states(
        CONFIG,
        temperature=temp,
        humidity=hum,
        soil_average=soil,
        current_states=current or OFF,
        runtime=runtime or ActuatorRuntime(),
        now=now,
    )


def test_hysteresis_matches_firmware_case():
    on = _run(31.0, 70.0, 50.0)
    assert on["fan_1"] and on["fan_2"]
    deadband = _run(28.5, 70.0, 50.0, current=on)
    assert deadband["fan_1"]
    off = _run(27.0, 70.0, 50.0, current=deadband)
    assert not off["fan_1"]


def test_impossible_temperature_never_leaves_fan_on():
    on = _run(31.0, 70.0, 50.0)
    impossible = _run(999.0, 70.0, 50.0, current=on)
    assert not impossible["fan_1"]


def test_pump_cooldown_and_recovery_match_firmware_case():
    runtime = ActuatorRuntime()
    states = _run(25.0, 70.0, 30.0, runtime=runtime, now=0.0)
    assert states["pump"]

    states = _run(25.0, 70.0, 30.0, current=states, runtime=runtime, now=901.0)
    assert not states["pump"]

    # Still dry: no restart until the soil crosses the OFF threshold.
    states = _run(25.0, 70.0, 30.0, current=states, runtime=runtime, now=1300.0)
    assert not states["pump"]

    # Wet sample marks the hysteresis as recovered.
    states = _run(25.0, 70.0, 50.0, current=states, runtime=runtime, now=1301.0)
    assert not states["pump"]

    # A new dry demand after the cooldown is allowed again.
    states = _run(25.0, 70.0, 30.0, current=states, runtime=runtime, now=1302.0)
    assert states["pump"]
