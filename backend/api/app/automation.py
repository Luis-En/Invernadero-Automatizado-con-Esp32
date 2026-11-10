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

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

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

# Minimum OFF time after a max-ON cut. The pump is the critical one: an
# immediate restart keeps pressure in the line and overheats the motor.
DEFAULT_MIN_OFF_SECONDS = {
    "fan": 0,
    "humidifier": 0,
    "pump": 300,
}

# A probe that returns the same value for this many cycles is considered
# stuck. Eight samples at the 10 s field cadence is 80 s, long enough to
# ignore normal quantization noise.
STUCK_SAMPLES = 8
STUCK_EPSILON = {"temperature": 0.02, "humidity": 0.05, "soil": 0.05}


@dataclass
class ActuatorRuntime:
    """Tracks continuous ON time, max-ON trips and off/cooldown state."""

    on_since: Dict[str, float] = field(default_factory=dict)
    off_since: Dict[str, float] = field(default_factory=dict)
    limit_blocked: Dict[str, bool] = field(default_factory=dict)
    limit_recovered: Dict[str, bool] = field(default_factory=dict)

    def mark(self, name: str, state: bool, now: float) -> None:
        if state and name not in self.on_since:
            self.on_since[name] = now
        elif not state:
            if name in self.on_since:
                self.off_since[name] = now
            self.on_since.pop(name, None)

    def elapsed(self, name: str, now: float) -> float:
        start = self.on_since.get(name)
        return (now - start) if start is not None else 0.0

    def cooldown_left(self, name: str, now: float, min_off: float) -> float:
        if min_off <= 0:
            return 0.0
        off_at = self.off_since.get(name)
        if off_at is None:
            return 0.0
        return max(0.0, min_off - (now - off_at))


class SensorMonitor:
    """Detects a frozen probe from the variance of its recent samples.

    A disconnected probe usually reads a rail value, which the validators
    already reject. A probe that is still connected but frozen (water ingress,
    stuck ADC, flat battery) keeps producing a plausible value, so only a
    variance check can catch it.
    """

    def __init__(self, samples: int = STUCK_SAMPLES,
                 epsilon: Optional[Dict[str, float]] = None) -> None:
        self.samples = max(3, samples)
        self.epsilon = {**STUCK_EPSILON, **(epsilon or {})}
        self._temperature: Deque[float] = deque(maxlen=self.samples)
        self._humidity: Deque[float] = deque(maxlen=self.samples)
        self._soil: List[Deque[float]] = [
            deque(maxlen=self.samples) for _ in range(6)
        ]
        self._stuck = {"temperature": False, "humidity": False, "soil": False}

    def _update_channel(self, name: str, history: Deque[float], value: Optional[float]) -> bool:
        if value is None:
            history.clear()
            self._stuck[name] = False
            return False
        history.append(float(value))
        if len(history) < self.samples:
            self._stuck[name] = False
            return False
        # Soil channels are named soil_0..soil_5 but share the "soil" epsilon.
        epsilon = self.epsilon.get(name, self.epsilon["soil"])
        stuck = (max(history) - min(history)) <= epsilon
        self._stuck[name] = stuck
        return stuck

    def update(self, temperature: Optional[float], humidity: Optional[float],
               soil_values: Optional[List[Optional[float]]] = None,
               valid_flags: Optional[List[bool]] = None) -> None:
        self._update_channel("temperature", self._temperature, temperature)
        self._update_channel("humidity", self._humidity, humidity)
        if soil_values is None:
            return
        any_stuck = False
        for index, value in enumerate(soil_values[:6]):
            ok = valid_flags[index] if valid_flags and index < len(valid_flags) else True
            stuck = self._update_channel(f"soil_{index}", self._soil[index], value if ok else None)
            any_stuck = any_stuck or stuck
        self._stuck["soil"] = any_stuck

    def stuck(self, name: str) -> bool:
        return self._stuck.get(name, False)


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


def _apply_safety_limit(
    name: str,
    desired: bool,
    runtime: ActuatorRuntime,
    now: float,
    limit: Optional[float],
    min_off: float,
) -> bool:
    """Apply max-ON and cooldown to one actuator.

    After a max-ON cut the actuator stays blocked until both conditions hold:
    the hysteresis demand recovered (the value crossed the OFF threshold) and
    the minimum OFF time elapsed. This prevents the 15 min ON / 10 s OFF
    oscillation the pump had before.
    """
    blocked = runtime.limit_blocked.get(name, False)

    if blocked:
        if not desired:
            runtime.limit_recovered[name] = True
        off_at = runtime.off_since.get(name)
        cooldown_done = off_at is not None and (now - off_at) >= max(0.0, min_off)
        if runtime.limit_recovered.get(name, False) and cooldown_done:
            runtime.limit_blocked[name] = False
            runtime.limit_recovered[name] = False
        else:
            return False

    if desired and limit and limit > 0 and runtime.elapsed(name, now) >= limit:
        runtime.limit_blocked[name] = True
        runtime.limit_recovered[name] = False
        return False

    return desired


def compute_actuator_states(
    config: dict,
    temperature: Optional[float],
    humidity: Optional[float],
    soil_average: Optional[float],
    current_states: Dict[str, bool],
    runtime: ActuatorRuntime,
    now: float,
    manual_override: Optional[Dict[str, bool]] = None,
    sensor_monitor: Optional[SensorMonitor] = None,
) -> Dict[str, bool]:
    """Compute the full actuator state set for one control cycle."""
    hysteresis = config.get("hysteresis", {})
    safety = config.get("safety", {})
    max_on = {**DEFAULT_MAX_ON_SECONDS, **safety.get("max_on_seconds", {})}
    min_off = {**DEFAULT_MIN_OFF_SECONDS, **safety.get("min_off_seconds", {})}
    irrigation_enabled = config.get("irrigation", {}).get("enabled", False)

    # A frozen-but-plausible probe is treated exactly like a missing one.
    if sensor_monitor is not None:
        if sensor_monitor.stuck("temperature"):
            temperature = None
        if sensor_monitor.stuck("humidity"):
            humidity = None
        if sensor_monitor.stuck("soil"):
            soil_average = None

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

    # --- Hard maximum ON time + off cooldown --------------------------------
    for name in ("fan_1", "fan_2"):
        states[name] = _apply_safety_limit(
            name, states[name], runtime, now, max_on["fan"], min_off["fan"]
        )
    for name in ("humidifier_1", "humidifier_2"):
        states[name] = _apply_safety_limit(
            name, states[name], runtime, now, max_on["humidifier"], min_off["humidifier"]
        )
    states["pump"] = _apply_safety_limit(
        "pump", states["pump"], runtime, now, max_on["pump"], min_off["pump"]
    )

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
