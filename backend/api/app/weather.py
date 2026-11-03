"""OpenWeather integration: current conditions and rain forecast.

This module only informs: the control loop in ``automation.py`` (and the
firmware port) never depends on it. Everything degrades gracefully -- no key,
a dead upstream or a bad key must leave the rest of the API untouched.

Design notes:

* The API key stays on the server. The frontend only talks to ``/api/weather``.
* Raw responses are cached for ``WEATHER_CACHE_TTL_SEC`` so the free tier quota
  is spent a couple of times per hour, and re-normalised per request so asking
  for a different ``hours`` window costs nothing.
* On an upstream error the last good payload is served stale (up to
  ``WEATHER_STALE_MAX_SEC``) instead of breaking the dashboard.

Uses the free OpenWeather endpoints (current + 5 day / 3 hour forecast), so
rain has a 3 hour resolution. The Spanish ``description`` comes from ``lang``.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
CURRENT_URL = f"{OPENWEATHER_BASE_URL}/weather"
FORECAST_URL = f"{OPENWEATHER_BASE_URL}/forecast"

# A 3 hour step counts as rain from these probabilities up.
RAIN_LIKELY_PROBABILITY = 0.6
RAIN_POSSIBLE_PROBABILITY = 0.3
RAIN_SOON_HOURS = 6

MAX_HOURS = 120
DEFAULT_HOURS = 48

FetchJson = Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]


class WeatherUnavailable(Exception):
    """Raised when no weather data can be produced for a request."""


def _iso_utc(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _local(timestamp: int, offset_seconds: int) -> datetime:
    """Timestamp as the greenhouse's local wall clock (timezone-aware UTC)."""
    return datetime.fromtimestamp(timestamp + offset_seconds, tz=timezone.utc)


class WeatherService:
    """Fetches, caches and normalises OpenWeather data for the greenhouse."""

    def __init__(self, settings_obj=settings, fetch_json: Optional[FetchJson] = None) -> None:
        self.settings = settings_obj
        self._fetch_json = fetch_json or self._http_fetch_json
        self._lock = asyncio.Lock()
        self._raw: Optional[Tuple[Dict[str, Any], Dict[str, Any]]] = None
        self._fetched_at: Optional[datetime] = None
        self._monotonic_at: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self.settings.OPENWEATHER_API_KEY) and bool(self.settings.WEATHER_ENABLED)

    async def get_overview(self, hours: int = DEFAULT_HOURS) -> Dict[str, Any]:
        hours = max(6, min(int(hours), MAX_HOURS))
        if not self.configured:
            message = (
                "El clima exterior está desactivado"
                if not self.settings.WEATHER_ENABLED
                else "OpenWeather no está configurado"
            )
            return self._empty_overview(hours, message)

        raw, fetched_at, stale, error = await self._load()
        current_raw, forecast_raw = raw
        return self._normalize(current_raw, forecast_raw, fetched_at, stale, error, hours)

    def reset_cache(self) -> None:
        self._raw = None
        self._fetched_at = None
        self._monotonic_at = 0.0

    # ------------------------------------------------------------------
    # Fetching and caching
    # ------------------------------------------------------------------

    def _params(self) -> Dict[str, Any]:
        return {
            "lat": self.settings.WEATHER_LAT,
            "lon": self.settings.WEATHER_LON,
            "units": self.settings.WEATHER_UNITS,
            "lang": self.settings.WEATHER_LANG,
            "appid": self.settings.OPENWEATHER_API_KEY,
        }

    async def _http_fetch_json(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.settings.WEATHER_TIMEOUT_SEC) as client:
            response = await client.get(url, params=params)
        if response.status_code == 401:
            raise WeatherUnavailable("La API key de OpenWeather no es válida")
        if response.status_code == 429:
            raise WeatherUnavailable("Se alcanzó el límite de consultas de OpenWeather")
        if response.status_code >= 400:
            logger.warning("OpenWeather respondió HTTP %s", response.status_code)
            raise WeatherUnavailable("OpenWeather respondió con un error")
        try:
            return response.json()
        except ValueError as exc:
            raise WeatherUnavailable("OpenWeather devolvió una respuesta inválida") from exc

    async def _load(self) -> Tuple[Tuple[Dict, Dict], datetime, bool, Optional[str]]:
        """Return (raw, fetched_at, stale, error), or raise WeatherUnavailable."""
        if self._fresh():
            return self._raw, self._fetched_at, False, None  # type: ignore[return-value]

        async with self._lock:
            if self._fresh():
                return self._raw, self._fetched_at, False, None  # type: ignore[return-value]
            try:
                params = self._params()
                current, forecast = await asyncio.gather(
                    self._fetch_json(CURRENT_URL, params),
                    self._fetch_json(FORECAST_URL, params),
                )
            except WeatherUnavailable as exc:
                return self._stale_or_raise(str(exc))
            except Exception as exc:  # network error, timeout, bad JSON
                logger.warning("OpenWeather request failed: %s", exc)
                return self._stale_or_raise("No se pudo conectar con OpenWeather")

            self._raw = (current, forecast)
            self._fetched_at = datetime.now(timezone.utc)
            self._monotonic_at = time.monotonic()
            return self._raw, self._fetched_at, False, None

    def _fresh(self) -> bool:
        return (
            self._raw is not None
            and self._fetched_at is not None
            and time.monotonic() - self._monotonic_at < self.settings.WEATHER_CACHE_TTL_SEC
        )

    def _stale_or_raise(self, error: str) -> Tuple[Tuple[Dict, Dict], datetime, bool, Optional[str]]:
        if self._raw is not None and self._fetched_at is not None:
            age = (datetime.now(timezone.utc) - self._fetched_at).total_seconds()
            if age < self.settings.WEATHER_STALE_MAX_SEC:
                return self._raw, self._fetched_at, True, error
        raise WeatherUnavailable(error)

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def _empty_overview(self, hours: int, error: str) -> Dict[str, Any]:
        return {
            "configured": False,
            "stale": False,
            "error": error,
            "fetched_at": None,
            "hours": hours,
            "units": self.settings.WEATHER_UNITS,
            "location": None,
            "current": None,
            "rain": None,
            "hourly": [],
            "daily": [],
        }

    def _normalize(
        self,
        current_raw: Dict[str, Any],
        forecast_raw: Dict[str, Any],
        fetched_at: Optional[datetime],
        stale: bool,
        error: Optional[str],
        hours: int,
    ) -> Dict[str, Any]:
        city = forecast_raw.get("city") or {}
        offset = int(city.get("timezone", current_raw.get("timezone", 0)) or 0)

        entries = self._timeline(forecast_raw.get("list") or [])
        now = int(datetime.now(timezone.utc).timestamp())
        hourly = [e for e in entries if e["dt"] <= now + hours * 3600]
        current = self._normalize_current(current_raw)

        return {
            "configured": True,
            "stale": stale,
            "error": error,
            "fetched_at": fetched_at,
            "hours": hours,
            "units": self.settings.WEATHER_UNITS,
            "location": {
                "name": self.settings.WEATHER_LOCATION_NAME
                or city.get("name")
                or current_raw.get("name"),
                "country": city.get("country") or (current_raw.get("sys") or {}).get("country"),
                "lat": self.settings.WEATHER_LAT,
                "lon": self.settings.WEATHER_LON,
                "timezone_offset": offset,
            },
            "current": current,
            "rain": self._rain_summary(current, entries, offset, now),
            "hourly": hourly,
            "daily": self._aggregate_daily(entries, offset),
        }

    @staticmethod
    def _normalize_current(raw: Dict[str, Any]) -> Dict[str, Any]:
        weather = (raw.get("weather") or [{}])[0]
        main = raw.get("main") or {}
        wind = raw.get("wind") or {}
        rain = raw.get("rain") or {}
        sys_info = raw.get("sys") or {}
        dt = raw.get("dt")
        return {
            "time": _iso_utc(int(dt)) if dt else None,
            "temperature": main.get("temp"),
            "feels_like": main.get("feels_like"),
            "humidity": main.get("humidity"),
            "pressure": main.get("pressure"),
            "wind_speed": wind.get("speed"),
            "wind_gust": wind.get("gust"),
            "wind_deg": wind.get("deg"),
            "clouds": (raw.get("clouds") or {}).get("all"),
            "visibility": raw.get("visibility"),
            "rain_1h": rain.get("1h"),
            "description": weather.get("description"),
            "main": weather.get("main"),
            "icon": weather.get("icon"),
            "sunrise": _iso_utc(int(sys_info["sunrise"])) if sys_info.get("sunrise") else None,
            "sunset": _iso_utc(int(sys_info["sunset"])) if sys_info.get("sunset") else None,
        }

    @staticmethod
    def _timeline(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        entries = []
        for item in items:
            dt = item.get("dt")
            if dt is None:
                continue
            weather = (item.get("weather") or [{}])[0]
            main = item.get("main") or {}
            wind = item.get("wind") or {}
            rain = item.get("rain") or {}
            entries.append({
                "dt": int(dt),
                "time": _iso_utc(int(dt)),
                "temperature": main.get("temp"),
                "humidity": main.get("humidity"),
                "pressure": main.get("pressure"),
                "wind_speed": wind.get("speed"),
                "wind_deg": wind.get("deg"),
                "clouds": (item.get("clouds") or {}).get("all"),
                "pop": item.get("pop") or 0.0,
                "rain_mm": rain.get("3h") or rain.get("1h") or 0.0,
                "description": weather.get("description"),
                "main": weather.get("main"),
                "icon": weather.get("icon"),
            })
        return entries

    @staticmethod
    def _rain_summary(
        current: Dict[str, Any],
        entries: List[Dict[str, Any]],
        offset: int,
        now: int,
    ) -> Dict[str, Any]:
        future = [e for e in entries if e["dt"] >= now]
        window_6h = [e for e in future if e["dt"] <= now + 6 * 3600]
        window_24h = [e for e in future if e["dt"] <= now + 24 * 3600]

        probability_6h = max((e["pop"] for e in window_6h), default=0.0)
        probability_24h = max((e["pop"] for e in window_24h), default=0.0)
        rain_24h = sum((e["rain_mm"] or 0.0) for e in window_24h)

        first_rain = next(
            (
                e
                for e in future
                if (e["rain_mm"] or 0.0) > 0 or e["pop"] >= RAIN_LIKELY_PROBABILITY
            ),
            None,
        )
        rain_now = (current.get("rain_1h") or 0.0) > 0

        if rain_now:
            status = "raining"
        elif (
            first_rain is not None
            and first_rain["dt"] <= now + RAIN_SOON_HOURS * 3600
            and (first_rain["pop"] >= RAIN_LIKELY_PROBABILITY or (first_rain["rain_mm"] or 0.0) > 0)
        ):
            status = "rain_soon"
        elif probability_24h >= RAIN_LIKELY_PROBABILITY:
            status = "likely"
        elif probability_24h >= RAIN_POSSIBLE_PROBABILITY:
            status = "possible"
        else:
            status = "dry"

        percent_24h = int(round(probability_24h * 100))
        if status == "raining":
            summary = f"Está lloviendo ({current.get('rain_1h'):.1f} mm en la última hora)"
        elif status == "rain_soon" and first_rain is not None:
            hour = _local(first_rain["dt"], offset).strftime("%H:%M")
            summary = f"Lluvia probable desde las {hour} ({int(round(first_rain['pop'] * 100))}%)"
        elif status == "likely":
            summary = f"Probabilidad de lluvia del {percent_24h}% en las próximas 24 h"
        elif status == "possible":
            summary = f"Posibilidad baja de lluvia ({percent_24h}%)"
        else:
            summary = "Sin lluvia prevista en las próximas 24 h"

        first_at = None
        first_probability = None
        if first_rain is not None and status != "raining":
            first_at = _iso_utc(first_rain["dt"])
            first_probability = round(first_rain["pop"], 2)

        return {
            "status": status,
            "summary": summary,
            "next_6h_probability": round(probability_6h, 2),
            "next_24h_probability": round(probability_24h, 2),
            "next_24h_mm": round(rain_24h, 1),
            "first_rain_at": first_at,
            "first_rain_probability": first_probability,
        }

    @staticmethod
    def _aggregate_daily(entries: List[Dict[str, Any]], offset: int) -> List[Dict[str, Any]]:
        days: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for entry in entries:
            local = _local(entry["dt"], offset)
            key = local.date().isoformat()
            if key not in days:
                days[key] = {
                    "date": key,
                    "temp_min": None,
                    "temp_max": None,
                    "wind_max": None,
                    "icon": None,
                    "description": None,
                    "_humidity": [],
                    "_pop": 0.0,
                    "_rain_mm": 0.0,
                    "_midday_distance": None,
                }
                order.append(key)
            day = days[key]

            temp = entry["temperature"]
            if temp is not None:
                day["temp_min"] = temp if day["temp_min"] is None else min(day["temp_min"], temp)
                day["temp_max"] = temp if day["temp_max"] is None else max(day["temp_max"], temp)
            if entry["humidity"] is not None:
                day["_humidity"].append(entry["humidity"])
            if entry["wind_speed"] is not None:
                day["wind_max"] = (
                    entry["wind_speed"]
                    if day["wind_max"] is None
                    else max(day["wind_max"], entry["wind_speed"])
                )
            day["_pop"] = max(day["_pop"], entry["pop"] or 0.0)
            day["_rain_mm"] += entry["rain_mm"] or 0.0

            # Keep the description/icon from the step closest to midday.
            distance = abs(local.hour - 12)
            if day["_midday_distance"] is None or distance < day["_midday_distance"]:
                day["_midday_distance"] = distance
                day["icon"] = entry["icon"]
                day["description"] = entry["description"]

        result = []
        for key in order[:5]:
            day = days[key]
            humidity = day.pop("_humidity")
            day["humidity_avg"] = int(round(sum(humidity) / len(humidity))) if humidity else None
            day["pop_max"] = round(day.pop("_pop"), 2)
            day["rain_mm"] = round(day.pop("_rain_mm"), 1)
            day.pop("_midday_distance", None)
            result.append(day)
        return result


weather_service = WeatherService()
