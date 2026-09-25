"""Automation and fail-safe logic tests (pure functions, no HTTP)."""
from app.automation import (
    ActuatorRuntime,
    compute_actuator_states,
    soil_average,
    valid_soil,
    valid_temperature,
)

BASE_CONFIG = {
    "hysteresis": {
        "temp": {"on_above": 30.0, "off_below": 27.5},
        "humidity": {"on_below": 60.0, "off_above": 68.0},
        "soil": {"on_below_pct": 35, "off_above_pct": 45},
    },
    "irrigation": {"enabled": True},
    "safety": {"max_on_seconds": {"fan": 7200, "humidifier": 7200, "pump": 900}},
}

OFF = {"fan_1": False, "fan_2": False, "humidifier_1": False, "humidifier_2": False, "pump": False}


def _run(temp, hum, soil, current=OFF, config=BASE_CONFIG, now=0.0, runtime=None, manual=None):
    return compute_actuator_states(
        config,
        temperature=temp,
        humidity=hum,
        soil_average=soil,
        current_states=current,
        manual_override=manual,
        runtime=runtime or ActuatorRuntime(),
        now=now,
    )


def test_fan_turns_on_above_threshold():
    states = _run(temp=31.0, hum=70.0, soil=50.0)
    assert states["fan_1"] and states["fan_2"]


def test_fan_uses_hysteresis_not_single_setpoint():
    # Above OFF threshold but below ON threshold: should remain OFF.
    states = _run(temp=28.5, hum=70.0, soil=50.0)
    assert not states["fan_1"]


def test_fan_stays_on_within_deadband():
    on = _run(temp=31.0, hum=70.0, soil=50.0)
    still_on = _run(temp=28.5, hum=70.0, soil=50.0, current=on)
    assert still_on["fan_1"]


def test_fan_turns_off_below_off_threshold():
    on = _run(temp=31.0, hum=70.0, soil=50.0)
    off = _run(temp=27.0, hum=70.0, soil=50.0, current=on)
    assert not off["fan_1"]


def test_humidifier_turns_on_when_dry():
    states = _run(temp=25.0, hum=55.0, soil=50.0)
    assert states["humidifier_1"] and states["humidifier_2"]


def test_pump_runs_when_soil_dry_and_irrigation_enabled():
    states = _run(temp=25.0, hum=70.0, soil=30.0)
    assert states["pump"]


def test_pump_blocked_when_irrigation_disabled():
    config = {**BASE_CONFIG, "irrigation": {"enabled": False}}
    states = _run(temp=25.0, hum=70.0, soil=30.0, config=config)
    assert not states["pump"]


def test_invalid_temperature_forces_fan_off():
    on = _run(temp=31.0, hum=70.0, soil=50.0)
    states = _run(temp=None, hum=70.0, soil=50.0, current=on)
    assert not states["fan_1"]


def test_impossible_temperature_forces_fan_off():
    on = _run(temp=31.0, hum=70.0, soil=50.0)
    states = _run(temp=999.0, hum=70.0, soil=50.0, current=on)
    assert not states["fan_1"]


def test_invalid_humidity_forces_humidifiers_off():
    on = _run(temp=25.0, hum=55.0, soil=50.0)
    states = _run(temp=25.0, hum=None, soil=50.0, current=on)
    assert not states["humidifier_1"]


def test_invalid_soil_forces_pump_off():
    on = _run(temp=25.0, hum=70.0, soil=30.0)
    states = _run(temp=25.0, hum=70.0, soil=None, current=on)
    assert not states["pump"]


def test_pump_max_on_limit():
    runtime = ActuatorRuntime()
    states = OFF
    # Turn on at t=0, stay dry, then at t=901s the pump must be cut.
    states = _run(temp=25.0, hum=70.0, soil=30.0, current=states, runtime=runtime, now=0.0)
    assert states["pump"]
    states = _run(temp=25.0, hum=70.0, soil=30.0, current=states, runtime=runtime, now=901.0)
    assert not states["pump"]


def test_manual_override_wins():
    states = _run(temp=25.0, hum=70.0, soil=50.0, manual={"fan_1": True, "fan_2": True})
    assert states["fan_1"] and states["fan_2"]


def test_soil_average_ignores_invalid_sensors():
    avg = soil_average([40.0, None, 60.0], valid_flags=[True, False, True])
    assert avg == 50.0


def test_soil_average_none_when_all_invalid():
    assert soil_average([None, None], valid_flags=[False, False]) is None


def test_validators_reject_out_of_range():
    assert not valid_temperature(1000)
    assert not valid_soil(150)
    assert valid_temperature(25.0)
