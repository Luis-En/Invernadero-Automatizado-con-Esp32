from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_current_active_user
from app.schemas import WeatherOverview
from app.weather import WeatherService, WeatherUnavailable, weather_service

router = APIRouter(prefix="/api/weather", tags=["weather"])


def get_weather_service() -> WeatherService:
    return weather_service


@router.get("/overview", response_model=WeatherOverview)
async def get_weather_overview(
    hours: int = Query(48, ge=6, le=120, description="Hours of hourly forecast to include"),
    user=Depends(get_current_active_user),
    service: WeatherService = Depends(get_weather_service),
):
    try:
        return await service.get_overview(hours=hours)
    except WeatherUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
