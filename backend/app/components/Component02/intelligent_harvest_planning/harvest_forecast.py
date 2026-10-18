"""Three-day weather comparison for harvest planning (not an agronomic model)."""

from datetime import datetime, timedelta
import math
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
import requests

router = APIRouter(prefix="/component02", tags=["Harvest planning"])
TIMEZONE = "Asia/Colombo"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
VARIABLES = {
    "rainfall_mm": "precipitation_sum",
    "rain_probability_percent": "precipitation_probability_max",
    "temperature_min_c": "temperature_2m_min",
    "temperature_max_c": "temperature_2m_max",
    "wind_max_m_s": "wind_speed_10m_max",
    "weather_code": "weather_code",
}


def compare_forecast(payload, today):
    dates = [(today + timedelta(days=offset)).isoformat() for offset in range(1, 4)]
    daily = payload.get("daily", {})
    times = daily.get("time", [])
    days = []
    for date in dates:
        day = {"date": date}
        index = times.index(date) if date in times else None
        for name, variable in VARIABLES.items():
            values = daily.get(variable) or []
            value = values[index] if index is not None and index < len(values) else None
            valid = isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)
            if valid and name in ("rainfall_mm", "wind_max_m_s", "weather_code"):
                valid = value >= 0
            if valid and name == "rain_probability_percent":
                valid = 0 <= value <= 100
            day[name] = round(value, 2) if valid else None
        day["complete"] = all(day[name] is not None for name in VARIABLES)
        if day["complete"] and day["temperature_min_c"] > day["temperature_max_c"]:
            day["complete"] = False
        day["thunderstorm"] = day["weather_code"] in (95, 96, 99)
        days.append(day)

    best = None
    if not all(day["complete"] for day in days):
        status = "incomplete"
        message = "Some forecast values are missing. Refresh before choosing a harvest day."
    else:
        candidates = [day for day in days if not day["thunderstorm"]]
        if not candidates:
            status = "unfavourable"
            message = "Thunderstorms are forecast on all three days. No harvest day is recommended."
        else:
            # Transparent ordering, not a calibrated crop suitability score.
            best = min(candidates, key=lambda day: (
                day["rainfall_mm"], day["rain_probability_percent"],
                day["wind_max_m_s"], day["temperature_max_c"], day["date"],
            ))
            status = "available"
            message = "Best weather match among the next three days, prioritising lower rainfall."

    cautions = []
    if best and best["rainfall_mm"] > 0:
        cautions.append("Rain is still forecast on this day. Recheck the forecast and wait for a dry break before harvesting.")
    if best and best["rain_probability_percent"] >= 50:
        cautions.append("Rain is more likely than not during part of this day.")
    if best and (best["wind_max_m_s"] >= 10 or best["temperature_max_c"] >= 35):
        cautions.append("Strong wind or high daytime heat is forecast; check local conditions before starting field work.")
    return {
        "success": True, "source": "Open-Meteo", "timezone": TIMEZONE,
        "forecast_date": today.isoformat(), "days": days,
        "best_date": best["date"] if best else None,
        "status": status, "message": message, "cautions": cautions,
        "method": "Exclude thunderstorms, then compare rainfall, rain probability, maximum wind and maximum temperature, in that order. Equal conditions favour the earlier day.",
    }


@router.get("/harvest-forecast")
def harvest_forecast(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
):
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    try:
        response = requests.get(FORECAST_URL, params={
            "latitude": latitude, "longitude": longitude,
            "daily": ",".join(VARIABLES.values()),
            "timezone": TIMEZONE, "wind_speed_unit": "ms",
            "temperature_unit": "celsius", "precipitation_unit": "mm",
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=3)).isoformat(),
        }, timeout=20)
        response.raise_for_status()
        result = compare_forecast(response.json(), today)
    except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=502, detail="The three-day weather forecast is unavailable. Please try again.") from exc
    result["location"] = {"latitude": latitude, "longitude": longitude}
    result["updated_at"] = datetime.now(ZoneInfo(TIMEZONE)).isoformat()
    return result
