"""Shared irrigation-need assessment.

Both the dashboard status endpoint and the background notifier use these
functions so the banner, the event log and the push notification can never
disagree about whether the crop needs water.
"""

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

DEFAULT_ON_BELOW_PCT = 35.0
DEFAULT_OFF_ABOVE_PCT = 45.0


@dataclass(frozen=True)
class IrrigationAssessment:
    needed: bool
    known: bool
    soil_avg: Optional[float]
    on_below: float
    off_above: float
    valid_sensors: int
    reason: str = ""


def thresholds_from_config(config: Optional[dict]) -> tuple[float, float]:
    """Read the soil hysteresis pair, tolerating old/partial documents."""
    soil = ((config or {}).get("hysteresis") or {}).get("soil") or {}
    try:
        on_below = float(soil.get("on_below_pct", DEFAULT_ON_BELOW_PCT))
    except (TypeError, ValueError):
        on_below = DEFAULT_ON_BELOW_PCT
    try:
        off_above = float(soil.get("off_above_pct", DEFAULT_OFF_ABOVE_PCT))
    except (TypeError, ValueError):
        off_above = DEFAULT_OFF_ABOVE_PCT

    # A corrupt config where OFF <= ON would make the pump chatter forever.
    if off_above <= on_below:
        off_above = on_below + 10.0
    return on_below, off_above


def usable_soil(values: Iterable[Optional[float]], flags: Optional[Sequence[bool]] = None) -> list:
    usable = []
    for index, value in enumerate(values):
        ok = flags[index] if flags is not None and index < len(flags) else True
        if not ok or value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if 0.0 <= numeric <= 100.0:
            usable.append(numeric)
    return usable


def assess_irrigation(
    values: Iterable[Optional[float]],
    flags: Optional[Sequence[bool]] = None,
    config: Optional[dict] = None,
    previously_needed: bool = False,
    min_valid_sensors: int = 1,
) -> IrrigationAssessment:
    """Return whether irrigation is needed.

    The state machine mirrors the actuator logic: enter the "needed" state at
    or below ``on_below_pct`` and leave it at or above ``off_above_pct``. That
    hysteresis prevents an alert storm around a single threshold.
    """
    on_below, off_above = thresholds_from_config(config)
    usable = usable_soil(values, flags)

    if len(usable) < max(1, min_valid_sensors):
        return IrrigationAssessment(
            needed=False,
            known=False,
            soil_avg=None,
            on_below=on_below,
            off_above=off_above,
            valid_sensors=len(usable),
            reason="sin sensores de suelo válidos",
        )

    average = sum(usable) / len(usable)
    if previously_needed:
        needed = average < off_above
    else:
        needed = average <= on_below

    return IrrigationAssessment(
        needed=needed,
        known=True,
        soil_avg=average,
        on_below=on_below,
        off_above=off_above,
        valid_sensors=len(usable),
        reason=(
            f"humedad media {average:.1f}% "
            f"(encender <= {on_below:.0f}%, apagar >= {off_above:.0f}%)"
        ),
    )


def soil_from_reading(reading) -> tuple[list, list]:
    """Extract the six soil percentages and validity flags from a Reading."""
    return (
        [
            reading.soil_pct_a1,
            reading.soil_pct_a2,
            reading.soil_pct_a3,
            reading.soil_pct_b1,
            reading.soil_pct_b2,
            reading.soil_pct_b3,
        ],
        [
            bool(reading.soil_ok_a1),
            bool(reading.soil_ok_a2),
            bool(reading.soil_ok_a3),
            bool(reading.soil_ok_b1),
            bool(reading.soil_ok_b2),
            bool(reading.soil_ok_b3),
        ],
    )
