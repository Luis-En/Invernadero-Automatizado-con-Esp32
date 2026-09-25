"""Automation and fail-safe rules for the greenhouse.

This module is the single reference implementation of the control logic that
the ESP32 field node also runs. Keeping it here lets the backend simulate and
test the exact same decisions that the firmware will make.

Rules (in order of priority):

1. Safety first: an invalid/out-of-range sensor reading forces the related
   actuator OFF. A broken sensor must never hold an actuator ON forever.
2. Hysteresis: actuators turn on at one threshold and off at a different one,
   so relays do not chatter around a single setpoint.
3. Hard limits: every actuator has a maximum continuous ON time.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

TEMP_MIN_VALID = -10.0
TEMP_MAX_VALID = 60.0
HUM_MIN_VALID = 0.0
HUM_MAX_VALID = 100.0
SOIL_MIN_VALID = 0.0
SOIL_MAX_VALID = 100.0

DEFAULT_MAX_ON_SECONDS = {
    "fan": 7200,
    "humidifier": 7200,
    "pump": 900,
}


@dataclass
class ActuatorRuntime:
    """Tracks how long each actuator has been continuously ON."""
    on_since: Dict[str, float] = field(default_factory=dict)

    def mark(self, name: str, state: bool, now: float) -> None:
        if state and name not in self.on_since:
            self.on_since[name] = now
        elif not state:
            self.on_since.pop(name, None)

    def elapsed(self, name: str, now: float) -> float:
        start = self.on_since.get(name)
        return (now - start) if start is not None else 0.0


def valid_temperature(value: Optional[float]) -> bool:
    return value is not None and TEMP_MIN_VALID <= value <= TEMP_MAX_VALID


def valid_humidity(value: Optional[float]) -> bool:
    return value is not None and HUM_MIN_VALID <= value <= HUM_MAX_VALID


def valid_soil(value: Optional[float]) -> bool:
    return value is not None and SOIL_MIN_VALID <= value <= SOIL_MAX_VALID


def _hysteresis_decision(
    current: bool,
    value: Optional[float],
    on_below: Optional[float] = None,
    off_above: Optional[float] = None,
    on_above: Optional[float] = None,
    off_below: Optional[float] = None,
) -> bool:
    """Return the next state using hysteresis.

    Either (on_below/off_above) for "turn on when low" actuators, or
    (on_above/off_below) for "turn on when high" actuators.
    """
    if value is None:
        return False

    if on_above is not None and off_below is not None:
        if not current and value >= on_above:
            return True
        if current and value <= off_below:
            return False
        return current

    if on_below is not None and off_above is not None:
        if not current and value <= on_below:
            return True
        if current and value >= off_above:
            return False
        return current

    return current


def compute_actuator_states(
    config: dict,
    temperature: Optional[float],
    humidity: Optional[float],
    soil_average: Optional[float],
    current_states: Dict[str, bool],
    runtime: ActuatorRuntime,
    now: float,
    manual_override: Optional[Dict[str, bool]] = None,
) -> Dict[str, bool]:
    """Compute the full actuator state set for one control cycle."""
    hysteresis = config.get("hysteresis", {})
    safety = config.get("safety", {})
    max_on = {**DEFAULT_MAX_ON_SECONDS, **safety.get("max_on_seconds", {})}
    irrigation_enabled = config.get("irrigation", {}).get("enabled", False)

    temp_hyst = hysteresis.get("temp", {"on_above": 30.0, "off_below": 27.5})
    hum_hyst = hysteresis.get("humidity", {"on_below": 60.0, "off_above": 68.0})
    soil_hyst = hysteresis.get("soil", {"on_below_pct": 35, "off_above_pct": 45})

    states = dict(current_states)

    # --- Ventilation (temperature driven) -----------------------------------
    if not valid_temperature(temperature):
        states["fan_1"] = states["fan_2"] = False
    else:
        fan = _hysteresis_decision(
            states.get("fan_1", False),
            temperature,
            on_above=temp_hyst.get("on_above", 30.0),
            off_below=temp_hyst.get("off_below", 27.5),
        )
        states["fan_1"] = states["fan_2"] = fan

    # --- Humidifiers (ambient humidity driven) ------------------------------
    if not valid_humidity(humidity):
        states["humidifier_1"] = states["humidifier_2"] = False
    else:
        hum = _hysteresis_decision(
            states.get("humidifier_1", False),
            humidity,
            on_below=hum_hyst.get("on_below", 60.0),
            off_above=hum_hyst.get("off_above", 68.0),
        )
        states["humidifier_1"] = states["humidifier_2"] = hum

    # --- Pump (soil moisture driven) ----------------------------------------
    if not irrigation_enabled or not valid_soil(soil_average):
        states["pump"] = False
    else:
        states["pump"] = _hysteresis_decision(
            states.get("pump", False),
            soil_average,
            on_below=soil_hyst.get("on_below_pct", 35),
            off_above=soil_hyst.get("off_above_pct", 45),
        )

    # --- Hard maximum ON time ------------------------------------------------
    for name in ("fan_1", "fan_2"):
        if _exceeds_limit(states, name, max_on["fan"], runtime, now):
            states[name] = False
    for name in ("humidifier_1", "humidifier_2"):
        if _exceeds_limit(states, name, max_on["humidifier"], runtime, now):
            states[name] = False
    if _exceeds_limit(states, "pump", max_on["pump"], runtime, now):
        states["pump"] = False

    # --- Manual override (admin) --------------------------------------------
    if manual_override:
        for name, value in manual_override.items():
            if name in states and isinstance(value, bool):
                states[name] = value

    for name, state in states.items():
        runtime.mark(name, state, now)

    return states


def _exceeds_limit(
    states: Dict[str, bool],
    name: str,
    limit: Optional[float],
    runtime: ActuatorRuntime,
    now: float,
) -> bool:
    if not states.get(name):
        return False
    if not limit:
        return False
    return runtime.elapsed(name, now) >= limit


def soil_average(
    soil_values: List[Optional[float]], valid_flags: Optional[List[bool]] = None
) -> Optional[float]:
    usable = []
    for i, value in enumerate(soil_values):
        ok = valid_flags[i] if valid_flags else True
        if ok and valid_soil(value):
            usable.append(value)
    if not usable:
        return None
    return sum(usable) / len(usable)
