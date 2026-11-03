"""Weather (OpenWeather) service and endpoint tests.

No test touches the network: the service is given a fake ``fetch_json`` and the
endpoint is exercised through a dependency override.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.main import app
from app.routes.weather import get_weather_service
from app.weather import WeatherService, WeatherUnavailable


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _settings(**overrides):
    base = {
        "OPENWEATHER_API_KEY": "test-key",
        "WEATHER_ENABLED": True,
        "WEATHER_LAT": 14.3333,
        "WEATHER_LON": -91.0167,
        "WEATHER_LOCATION_NAME": "Santa Lucía Cotzumalguapa",
        "WEATHER_UNITS": "metric",
        "WEATHER_LANG": "es",
        "WEATHER_CACHE_TTL_SEC": 600,
        "WEATHER_STALE_MAX_SEC": 7200,
        "WEATHER_TIMEOUT_SEC": 5.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _current_payload(dt: int, rain_1h=0.0):
    payload = {
        "coord": {"lat": 14.3333, "lon": -91.0167},
        "weather": [{"id": 500, "main": "Rain", "description": "lluvia ligera", "icon": "10d"}],
        "main": {"temp": 29.1, "feels_like": 33.0, "pressure": 1009, "humidity": 87},
        "wind": {"speed": 1.2, "deg": 304, "gust": 3.7},
        "clouds": {"all": 95},
        "visibility": 4930,
        "dt": dt,
        "sys": {"country": "GT", "sunrise": dt - 20000, "sunset": dt + 20000},
        "timezone": -21600,
        "name": "Santa Lucía Cotzumalguapa",
    }
    if rain_1h:
        payload["rain"] = {"1h": rain_1h}
    return payload


def _forecast_payload(dt0: int, steps: int = 40):
    items = []
    for i in range(steps):
        dt = dt0 + i * 3 * 3600
        item = {
            "dt": dt,
            "main": {"temp": 28.0 - i * 0.1, "humidity": 80, "pressure": 1010},
            "weather": [{"id": 500, "main": "Rain", "description": "lluvia ligera", "icon": "10d"}],
            "clouds": {"all": 90},
            "wind": {"speed": 2.0, "deg": 90},
            "visibility": 8000,
            "pop": 0.1,
        }
        if i == 1:
            item["pop"] = 0.72
            item["rain"] = {"3h": 2.4}
        items.append(item)
    return {
        "cod": "200",
        "cnt": steps,
        "list": items,
        "city": {
            "name": "Santa Lucía Cotzumalguapa",
            "country": "GT",
            "timezone": -21600,
        },
    }


def _fake_fetch(calls, current=None, forecast=None, fail=False):
    async def fetch(url, params):
        calls.append(url)
        if fail:
            raise WeatherUnavailable("No se pudo conectar con OpenWeather")
        return current if url.endswith("/weather") else forecast

    return fetch


async def test_not_configured_returns_empty_overview():
    service = WeatherService(settings_obj=_settings(OPENWEATHER_API_KEY=""))
    overview = await service.get_overview(hours=24)
    assert overview["configured"] is False
    assert overview["hourly"] == []
    assert overview["current"] is None


async def test_overview_normalizes_current_forecast_and_rain():
    dt0 = _now()
    calls = []
    service = WeatherService(
        settings_obj=_settings(),
        fetch_json=_fake_fetch(calls, _current_payload(dt0), _forecast_payload(dt0)),
    )

    overview = await service.get_overview(hours=48)

    assert overview["configured"] is True
    assert overview["stale"] is False
    assert overview["location"]["country"] == "GT"
    assert overview["current"]["temperature"] == 29.1
    assert overview["current"]["description"] == "lluvia ligera"
    # 2 calls per refresh: current + forecast.
    assert len(calls) == 2
    assert len(overview["hourly"]) <= 17
    assert overview["rain"]["status"] == "rain_soon"
    assert overview["rain"]["next_24h_mm"] > 0
    assert overview["rain"]["first_rain_at"] is not None
    assert len(overview["daily"]) == 5


async def test_cache_avoids_second_upstream_call():
    dt0 = _now()
    calls = []
    service = WeatherService(
        settings_obj=_settings(),
        fetch_json=_fake_fetch(calls, _current_payload(dt0), _forecast_payload(dt0)),
    )

    await service.get_overview(hours=24)
    await service.get_overview(hours=120)

    assert len(calls) == 2  # second request served from cache


async def test_stale_fallback_serves_last_good_payload():
    dt0 = _now()
    calls = []

    async def flaky(url, params):
        calls.append(url)
        if len(calls) > 2:
            raise WeatherUnavailable("OpenWeather respondió con un error")
        return _current_payload(dt0) if url.endswith("/weather") else _forecast_payload(dt0)

    service = WeatherService(settings_obj=_settings(), fetch_json=flaky)
    first = await service.get_overview(hours=24)
    assert first["stale"] is False

    service._monotonic_at = 0.0  # expire the cache without waiting
    second = await service.get_overview(hours=24)

    assert second["stale"] is True
    assert second["error"] == "OpenWeather respondió con un error"
    assert second["current"]["temperature"] == 29.1


async def test_unavailable_without_cache_raises():
    service = WeatherService(
        settings_obj=_settings(),
        fetch_json=_fake_fetch([], fail=True),
    )
    with pytest.raises(WeatherUnavailable):
        await service.get_overview(hours=24)


class _FakeService:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    async def get_overview(self, hours=48):
        if self.error:
            raise WeatherUnavailable(self.error)
        return self.data


def _fake_overview():
    return {
        "configured": True,
        "stale": False,
        "error": None,
        "fetched_at": "2026-10-17T15:00:00Z",
        "hours": 48,
        "units": "metric",
        "location": {"name": "Santa Lucía Cotzumalguapa", "country": "GT"},
        "current": {"temperature": 29.1, "description": "lluvia ligera", "icon": "10d"},
        "rain": {
            "status": "rain_soon",
            "summary": "Lluvia probable desde las 15:00 (72%)",
            "next_6h_probability": 0.72,
            "next_24h_probability": 0.9,
            "next_24h_mm": 12.4,
        },
        "hourly": [],
        "daily": [],
    }


@pytest.fixture
def _weather_override():
    def _apply(service):
        app.dependency_overrides[get_weather_service] = lambda: service

    yield _apply
    app.dependency_overrides.pop(get_weather_service, None)


async def test_endpoint_requires_auth(client):
    resp = await client.get("/api/weather/overview")
    assert resp.status_code == 401


async def test_endpoint_returns_overview(client, auth_viewer, _weather_override):
    _weather_override(_FakeService(data=_fake_overview()))
    resp = await client.get("/api/weather/overview?hours=24", headers=auth_viewer)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["current"]["temperature"] == 29.1
    assert body["rain"]["status"] == "rain_soon"


async def test_endpoint_returns_503_when_unavailable(client, auth_viewer, _weather_override):
    _weather_override(_FakeService(error="No se pudo conectar con OpenWeather"))
    resp = await client.get("/api/weather/overview", headers=auth_viewer)
    assert resp.status_code == 503
    assert "OpenWeather" in resp.json()["detail"]
