from pathlib import Path
import tempfile
import requests
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException
from ultralytics import YOLO


# ============================================================
# COMPONENT 02
# AI-POWERED PLANTATION HEALTH & CLIMATE STRESS ASSESSMENT
#
# YOLO11 + Open-Meteo
#
# Features:
#   1. YOLO11 Plantation Health Classification
#   2. Image Health Score
#   3. Open-Meteo current/hourly/daily Climate Data
#   4. Automatic Previous-Date Fallback
#   5. Heat Stress
#   6. Water Stress
#   7. Rainfall Stress
#   8. Humidity Stress
#   9. Wind Condition
#  10. Solar Radiation Condition
#  11. Climate Risk Score
#  12. Early Warning
#  13. AI Recommendations
# ============================================================


# ============================================================
# BASE DIRECTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# TRAINED YOLO11 MODEL
# ============================================================

MODEL_PATH = (
    BASE_DIR
    / "runs"
    / "plantation_health_yolo11n_updated_50epochs_v2"
    / "weights"
    / "best.pt"
)


# ============================================================
# CHECK MODEL
# ============================================================

if not MODEL_PATH.exists():

    raise FileNotFoundError(
        f"Trained model not found:\n{MODEL_PATH}"
    )


# ============================================================
# LOAD YOLO11 MODEL
# ============================================================

model = YOLO(str(MODEL_PATH))


print("=" * 70)
print("COMPONENT 02 - PLANTATION HEALTH API")
print("=" * 70)

print("YOLO11 model loaded successfully")
print(f"Model  : {MODEL_PATH}")
print(f"Classes: {model.names}")


# ============================================================
# OPEN-METEO
# ============================================================

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CLIMATE_TIMEZONE = "Asia/Colombo"
OPEN_METEO_HOURLY_PARAMETERS = (
    "temperature_2m,relative_humidity_2m,wind_speed_10m,"
    "precipitation,shortwave_radiation"
)
OPEN_METEO_DAILY_PARAMETERS = (
    "temperature_2m_max,temperature_2m_mean,temperature_2m_min,"
    "precipitation_sum,wind_speed_10m_max,shortwave_radiation_sum,"
    "et0_fao_evapotranspiration"
)


# ============================================================
# CLIMATE FALLBACK SETTINGS
# ============================================================

# If today's data is unavailable, check previous days.
#
# Example:
#
# 2026-08-14
#       ↓
# 2026-08-13
#       ↓
# 2026-08-12
#       ↓
# ...
#
# Maximum 7 days backward.

MAX_CLIMATE_LOOKBACK_DAYS = 7
CLIMATE_HISTORY_DAYS = 14


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/component02",
    tags=["Component 02 - Plantation Health"]
)


# ============================================================
# HEALTH CLASSIFICATION RULE
# ============================================================

def canonical_health_class(class_name):
    """
    Keep the public API to two categories.

    The trained healthy class is the only class that can be
    returned as healthy. Every other class is treated as low
    health, including unexpected or future model labels.
    """

    normalized_name = str(class_name).strip().lower()
    normalized_name = normalized_name.replace("-", "_").replace(" ", "_")

    if normalized_name == "healthy":
        return "healthy"

    return "low_health"


def build_health_reason(prediction, low_health_image_count=None, image_count=None):
    """Explain the result without claiming a specific disease."""

    if prediction == "low_health":
        count_message = ""
        if low_health_image_count is not None and image_count is not None:
            count_message = (
                f"{low_health_image_count} of {image_count} uploaded image(s) "
                "were classified as low health. "
            )
        return (
            f"{count_message}The AI model detected visual patterns associated "
            "with reduced tea plant health. This classification does not "
            "identify a specific disease or cause, so the affected area should "
            "be checked in the field."
        )

    return "The AI model did not detect visual patterns associated with low health."


def extract_health_prediction(probabilities):
    """Convert model output into the API's healthy/low_health categories."""

    predicted_class_id = int(probabilities.top1)
    raw_predicted_class = model.names[predicted_class_id]

    # Aggregate all model outputs into the two public categories.
    category_probabilities = {
        "healthy": 0.0,
        "low_health": 0.0,
    }

    for class_id, probability in enumerate(probabilities.data):
        model_class = model.names[class_id]
        category = canonical_health_class(model_class)
        category_probabilities[category] += float(probability)

    predicted_class = canonical_health_class(raw_predicted_class)
    confidence = category_probabilities[predicted_class]

    return {
        "prediction": predicted_class,
        "confidence": confidence,
        "class_probabilities": {
            category: round(probability * 100, 2)
            for category, probability in category_probabilities.items()
        },
    }


# ============================================================
# HELPER
# CHECK VALID CLIMATE VALUE
# ============================================================

def is_valid_climate_value(value):
    """
    Open-Meteo returns null when a value is unavailable.
    """

    if value is None:
        return False

    try:

        numeric_value = float(value)

        if numeric_value <= -900:
            return False

        return True

    except (TypeError, ValueError):

        return False


# ============================================================
# HELPER
# CLEAN CLIMATE VALUE
# ============================================================

def clean_climate_value(value):
    """
    Convert a climate API value into a rounded float.

    Invalid values become None.
    """

    if not is_valid_climate_value(value):

        return None

    return round(
        float(value),
        2
    )


# ============================================================
# HELPER
# OPEN-METEO RESPONSE HELPERS
# ============================================================

def _open_meteo_url(start_date, end_date):
    """Choose forecast or archive API for the requested date range."""

    today = datetime.now().date()
    if (
        start_date >= today - timedelta(days=92)
        and end_date <= today + timedelta(days=16)
    ):
        return OPEN_METEO_FORECAST_URL

    return OPEN_METEO_ARCHIVE_URL


def fetch_open_meteo_payload(
    latitude: float,
    longitude: float,
    start_date,
    end_date,
    include_current=False,
):
    """Fetch local-time hourly and daily weather from Open-Meteo."""

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": OPEN_METEO_HOURLY_PARAMETERS,
        "daily": OPEN_METEO_DAILY_PARAMETERS,
        "timezone": CLIMATE_TIMEZONE,
        "wind_speed_unit": "ms",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    if include_current:
        params["current"] = (
            "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"
        )

    response = requests.get(
        _open_meteo_url(start_date, end_date),
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _average_valid(values):
    values = [value for value in values if is_valid_climate_value(value)]
    return sum(values) / len(values) if values else None


def _sum_valid(values):
    values = [value for value in values if is_valid_climate_value(value)]
    return sum(values) if values else None


def build_open_meteo_daily_records(payload):
    """Convert Open-Meteo hourly/daily arrays into API-compatible records."""

    hourly = payload.get("hourly", {})
    daily = payload.get("daily", {})
    hourly_by_date = {}

    for index, timestamp in enumerate(hourly.get("time", [])):
        date_key = timestamp[:10]
        hourly_by_date.setdefault(date_key, []).append({
            "temperature_c": hourly.get("temperature_2m", [])[index],
            "humidity_percent": hourly.get(
                "relative_humidity_2m", []
            )[index],
            "wind_speed_m_s": hourly.get("wind_speed_10m", [])[index],
            "rainfall_mm": hourly.get("precipitation", [])[index],
            "shortwave_radiation_w_m2": hourly.get(
                "shortwave_radiation", []
            )[index],
        })

    records = []
    daily_times = daily.get("time", [])
    for index, date_key in enumerate(daily_times):
        hours = hourly_by_date.get(date_key, [])
        hourly_temperatures = [hour["temperature_c"] for hour in hours]
        hourly_humidity = [hour["humidity_percent"] for hour in hours]
        hourly_wind = [hour["wind_speed_m_s"] for hour in hours]
        hourly_rainfall = [hour["rainfall_mm"] for hour in hours]
        hourly_radiation = [
            hour["shortwave_radiation_w_m2"] for hour in hours
        ]

        daily_mean_temperature = daily.get("temperature_2m_mean", [None])[index]
        daily_max_temperature = daily.get("temperature_2m_max", [None])[index]
        daily_min_temperature = daily.get("temperature_2m_min", [None])[index]
        daily_rainfall = daily.get("precipitation_sum", [None])[index]
        daily_wind_max = daily.get("wind_speed_10m_max", [None])[index]
        daily_radiation = daily.get("shortwave_radiation_sum", [None])[index]
        daily_et0 = daily.get("et0_fao_evapotranspiration", [None])[index]

        records.append({
            "date": date_key,
            "temperature_c": clean_climate_value(
                daily_mean_temperature
                if is_valid_climate_value(daily_mean_temperature)
                else _average_valid(hourly_temperatures)
            ),
            "temperature_max_c": clean_climate_value(
                daily_max_temperature
                if is_valid_climate_value(daily_max_temperature)
                else max(
                    [value for value in hourly_temperatures
                     if is_valid_climate_value(value)],
                    default=None,
                )
            ),
            "temperature_min_c": clean_climate_value(
                daily_min_temperature
                if is_valid_climate_value(daily_min_temperature)
                else min(
                    [value for value in hourly_temperatures
                     if is_valid_climate_value(value)],
                    default=None,
                )
            ),
            "rainfall_mm": clean_climate_value(
                daily_rainfall
                if is_valid_climate_value(daily_rainfall)
                else _sum_valid(hourly_rainfall)
            ),
            "humidity_percent": clean_climate_value(
                _average_valid(hourly_humidity)
            ),
            "wind_speed_m_s": clean_climate_value(
                _average_valid(hourly_wind)
            ),
            "wind_speed_max_m_s": clean_climate_value(daily_wind_max),
            "solar_radiation_kwh_m2_day": clean_climate_value(
                daily_radiation / 3.6
                if is_valid_climate_value(daily_radiation)
                else (
                    _sum_valid(hourly_radiation) / 1000
                    if _sum_valid(hourly_radiation) is not None
                    else None
                )
            ),
            "et0_mm": clean_climate_value(daily_et0),
        })

    return records


def fetch_open_meteo_climate_for_date(
    latitude: float,
    longitude: float,
    date_obj,
):
    """Fetch the best available current or daily value for one date."""

    payload = fetch_open_meteo_payload(
        latitude=latitude,
        longitude=longitude,
        start_date=date_obj,
        end_date=date_obj,
        include_current=date_obj == datetime.now().date(),
    )
    records = build_open_meteo_daily_records(payload)
    if not records:
        return None

    climate = records[0]
    current = payload.get("current", {})
    if current and date_obj == datetime.now().date():
        climate["temperature_c"] = clean_climate_value(
            current.get("temperature_2m")
        )
        climate["humidity_percent"] = clean_climate_value(
            current.get("relative_humidity_2m")
        )
        climate["wind_speed_m_s"] = clean_climate_value(
            current.get("wind_speed_10m")
        )

    return climate


def fetch_open_meteo_climate_window(
    latitude: float,
    longitude: float,
    end_date,
    days: int = CLIMATE_HISTORY_DAYS,
):
    """Fetch a multi-day Open-Meteo window for trend-based screening."""

    start_date = end_date - timedelta(days=days - 1)
    payload = fetch_open_meteo_payload(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
    )
    return build_open_meteo_daily_records(payload)


# ============================================================
# HELPER
# CHECK METEOROLOGICAL DATA
# ============================================================

def has_meteorological_data(climate):
    """
    We consider temperature, rainfall, humidity and wind
    as the main meteorological data.

    Solar radiation is handled separately because it can
    have a longer data latency.
    """

    required_values = [

        climate.get(
            "temperature_c"
        ),

        climate.get(
            "rainfall_mm"
        ),

        climate.get(
            "humidity_percent"
        ),

        climate.get(
            "wind_speed_m_s"
        )
    ]


    available_count = sum(

        value is not None

        for value in required_values
    )


    # At least one main climate value is available.
    return available_count > 0


# ============================================================
# HELPER
# GET LATEST AVAILABLE CLIMATE DATA
# ============================================================

def get_latest_available_climate(
    latitude: float,
    longitude: float,
    requested_date: str
):
    """
    Try requested date first.

    If data is unavailable, automatically check previous
    dates up to MAX_CLIMATE_LOOKBACK_DAYS.

    Example:

        Requested:
            2026-08-14

        Try:
            2026-08-14
            2026-08-13
            2026-08-12
            ...

    Returns:

        {
            "climate": {...},
            "data_date": "2026-08-12",
            "data_delay_days": 2,
            "data_status": "Latest Available"
        }
    """


    # --------------------------------------------------------
    # Validate requested date
    # --------------------------------------------------------

    try:

        requested_date_obj = datetime.strptime(
            requested_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid date format. "
                "Use YYYY-MM-DD."
            )
        )


    # --------------------------------------------------------
    # Search backwards
    # --------------------------------------------------------

    for days_back in range(
        0,
        MAX_CLIMATE_LOOKBACK_DAYS + 1
    ):

        candidate_date = (
            requested_date_obj
            - timedelta(days=days_back)
        )


        print(
            f"Open-Meteo: checking "
            f"{candidate_date}"
        )


        try:

            climate = fetch_open_meteo_climate_for_date(
                latitude=latitude,
                longitude=longitude,
                date_obj=candidate_date
            )


        except requests.RequestException:

            # If one date fails, continue checking
            # previous dates.

            continue


        # ----------------------------------------------------
        # Check whether data exists
        # ----------------------------------------------------

        if climate and has_meteorological_data(climate):

            data_delay_days = (
                requested_date_obj
                - candidate_date
            ).days


            if candidate_date > datetime.now().date():
                data_status = "Forecast"
            elif data_delay_days == 0:

                data_status = "Current"

            else:

                data_status = (
                    "Latest Available"
                )


            print(
                f"Open-Meteo: data found for "
                f"{candidate_date}"
            )


            return {

                "climate": climate,

                "data_date":
                    candidate_date.isoformat(),

                "data_delay_days":
                    data_delay_days,

                "data_status":
                    data_status
            }


    # --------------------------------------------------------
    # No data found
    # --------------------------------------------------------

    raise HTTPException(
        status_code=404,
        detail=(
            "Open-Meteo climate data is not available "
            f"for {requested_date} or the previous "
            f"{MAX_CLIMATE_LOOKBACK_DAYS} days."
        )
    )


def _average(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 2) if values else None


def _total(values):
    values = [value for value in values if value is not None]
    return round(sum(values), 2) if values else None


def _max_consecutive(values, predicate):
    longest = current = 0
    for value in values:
        if value is not None and predicate(value):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def build_stress_assessment(climate, history):
    """Build explainable, tea-focused indicators from climate trends.

    A single day's rainfall cannot establish plant water stress. The water
    indicator therefore uses a 14-day rainfall window and dry-day streak;
    the other indicators use short rolling windows to reduce noisy results.
    """

    ordered_history = history or [
        {
            "date": None,
            "temperature_c": climate.get("temperature_c"),
            "temperature_max_c": climate.get("temperature_max_c"),
            "temperature_min_c": climate.get("temperature_min_c"),
            "rainfall_mm": climate.get("rainfall_mm"),
            "humidity_percent": climate.get("humidity_percent"),
            "wind_speed_m_s": climate.get("wind_speed_m_s"),
            "solar_radiation_kwh_m2_day": climate.get(
                "solar_radiation_kwh_m2_day"
            ),
        }
    ]
    recent = ordered_history[-7:]
    rainfall_values = [day.get("rainfall_mm") for day in ordered_history]
    recent_rainfall = [day.get("rainfall_mm") for day in recent]
    temperature_values = [day.get("temperature_c") for day in recent]
    temperature_max_values = [
        day.get("temperature_max_c") or day.get("temperature_c")
        for day in recent
    ]
    humidity_values = [day.get("humidity_percent") for day in recent]
    wind_values = [day.get("wind_speed_m_s") for day in recent]
    solar_values = [
        day.get("solar_radiation_kwh_m2_day") for day in recent
    ]

    mean_temperature = _average(temperature_values)
    max_temperature = max(
        [value for value in temperature_max_values if value is not None],
        default=None,
    )
    rainfall_7d = _total(recent_rainfall)
    rainfall_14d = _total(rainfall_values)
    humidity_7d = _average(humidity_values)
    wind_7d = _average(wind_values)
    solar_7d = _average(solar_values)
    dry_days_14d = sum(
        value is not None and value < 1 for value in rainfall_values
    )
    dry_streak = _max_consecutive(
        rainfall_values,
        lambda value: value < 1,
    )
    latest_rainfall = climate.get("rainfall_mm")

    # Tea heat screening: mean/max temperature and a 7-day window are used
    # instead of treating one average temperature as a complete diagnosis.
    if max_temperature is None and mean_temperature is None:
        heat_stress = "Unknown"
    elif (max_temperature is not None and max_temperature >= 35) or (
        mean_temperature is not None and mean_temperature >= 30
    ):
        heat_stress = "High"
    elif (max_temperature is not None and max_temperature >= 30) or (
        mean_temperature is not None and mean_temperature >= 27
    ):
        heat_stress = "Medium"
    else:
        heat_stress = "Low"

    # Water stress needs a persistent dry period. If the API returned fewer
    # than seven days, avoid claiming High from a single dry day.
    if rainfall_14d is None:
        water_stress = "Unknown"
    elif len(ordered_history) < 7:
        water_stress = "Medium" if rainfall_14d < 2 else "Low"
    elif rainfall_14d < 10 and dry_days_14d >= 7 and dry_streak >= 5:
        water_stress = "High"
    elif (
        rainfall_14d < 25
        or (rainfall_7d is not None and rainfall_7d < 5 and dry_streak >= 4)
    ):
        water_stress = "Medium"
    else:
        water_stress = "Low"

    # Rainfall stress means excess rainfall/waterlogging risk, not lack of
    # rainfall. It is intentionally separate from Water Stress.
    if latest_rainfall is None and rainfall_7d is None:
        rainfall_stress = "Unknown"
    elif (
        (latest_rainfall is not None and latest_rainfall >= 50)
        or (rainfall_7d is not None and rainfall_7d >= 150)
    ):
        rainfall_stress = "High"
    elif (
        (latest_rainfall is not None and latest_rainfall >= 25)
        or (rainfall_7d is not None and rainfall_7d >= 75)
    ):
        rainfall_stress = "Medium"
    else:
        rainfall_stress = "Low"

    if humidity_7d is None:
        humidity_stress = "Unknown"
    elif humidity_7d >= 90 or any(
        value is not None and value >= 95 for value in humidity_values
    ):
        humidity_stress = "High"
    elif humidity_7d >= 80 or any(
        value is not None and value >= 90 for value in humidity_values
    ):
        humidity_stress = "Medium"
    else:
        humidity_stress = "Low"

    max_wind = max([value for value in wind_values if value is not None], default=None)
    if wind_7d is None and max_wind is None:
        wind_condition = "Unknown"
    elif max_wind is not None and max_wind >= 8 or (
        wind_7d is not None and wind_7d >= 5
    ):
        wind_condition = "High"
    elif max_wind is not None and max_wind >= 5 or (
        wind_7d is not None and wind_7d >= 3
    ):
        wind_condition = "Moderate"
    else:
        wind_condition = "Low"

    if solar_7d is None:
        solar_condition = "Unknown"
    elif solar_7d < 3:
        solar_condition = "Low"
    elif solar_7d < 6:
        solar_condition = "Moderate"
    else:
        solar_condition = "High"

    stress_score_map = {"Low": 0, "Medium": 50, "High": 100, "Unknown": 25}
    scored_indicators = [
        heat_stress,
        water_stress,
        rainfall_stress,
        humidity_stress,
        wind_condition,
    ]
    climate_risk_score = round(
        sum(stress_score_map.get(level, 25) for level in scored_indicators)
        / len(scored_indicators),
        2,
    )
    overall_climate_risk = (
        "High" if climate_risk_score >= 70
        else "Medium" if climate_risk_score >= 40
        else "Low"
    )

    stress_levels = [heat_stress, water_stress, rainfall_stress, humidity_stress]
    if "High" in stress_levels:
        early_warning = "Immediate Risk"
    elif "Medium" in stress_levels:
        early_warning = "Monitor Conditions"
    else:
        early_warning = "No Immediate Risk"

    history_days = len(ordered_history)
    confidence = (
        "High" if history_days >= 10
        else "Medium" if history_days >= 7
        else "Low"
    )

    details = {
        "heat_stress": {
            "status": heat_stress,
            "value": mean_temperature,
            "unit": "°C mean (7-day)",
            "message": (
                f"7-day mean {mean_temperature}°C; observed maximum "
                f"{max_temperature}°C. Uses mean and maximum temperature."
                if mean_temperature is not None and max_temperature is not None
                else "Temperature data is unavailable."
            ),
        },
        "water_stress": {
            "status": water_stress,
            "value": rainfall_14d,
            "unit": "mm rainfall (14-day)",
            "message": (
                f"{rainfall_14d}mm accumulated over {history_days} available "
                f"day(s), with {dry_streak} consecutive dry day(s)."
                if rainfall_14d is not None
                else "Rainfall history is unavailable."
            ),
        },
        "rainfall_stress": {
            "status": rainfall_stress,
            "value": latest_rainfall,
            "unit": "mm today",
            "message": (
                f"Today {latest_rainfall}mm; 7-day total {rainfall_7d}mm. "
                "Measures excess-rain/waterlogging risk."
                if latest_rainfall is not None and rainfall_7d is not None
                else "Rainfall data is unavailable."
            ),
        },
        "humidity_stress": {
            "status": humidity_stress,
            "value": humidity_7d,
            "unit": "% mean (7-day)",
            "message": (
                f"7-day mean humidity {humidity_7d}%; high humidity can "
                "increase disease pressure."
                if humidity_7d is not None
                else "Humidity data is unavailable."
            ),
        },
        "wind_condition": {
            "status": wind_condition,
            "value": wind_7d,
            "unit": "m/s mean (7-day)",
            "message": (
                f"7-day mean {wind_7d}m/s; maximum {max_wind}m/s."
                if wind_7d is not None and max_wind is not None
                else "Wind data is unavailable."
            ),
        },
        "solar_condition": {
            "status": solar_condition,
            "value": solar_7d,
            "unit": "kWh/m²/day mean (7-day)",
            "message": (
                f"7-day mean solar radiation {solar_7d}."
                if solar_7d is not None
                else "Solar radiation data is unavailable for this observation."
            ),
        },
    }

    return {
        "heat_stress": heat_stress,
        "water_stress": water_stress,
        "rainfall_stress": rainfall_stress,
        "humidity_stress": humidity_stress,
        "wind_condition": wind_condition,
        "solar_condition": solar_condition,
        "climate_risk_score": climate_risk_score,
        "overall_climate_risk": overall_climate_risk,
        "early_warning": early_warning,
        "details": details,
        "data_quality": {
            "available_days": history_days,
            "requested_window_days": CLIMATE_HISTORY_DAYS,
            "confidence": confidence,
            "method": "Tea-focused rule-based screening using Open-Meteo trends",
            "limitation": (
                "Weather data estimates climate pressure; confirm water stress "
                "with soil moisture, irrigation history and field observations."
            ),
        },
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@router.get("/health")
def health_check():

    return {

        "success": True,

        "component": "Component 02",

        "service":
            "Plantation Health Classification",

        "model":
            "YOLO11",

        "classes":
            model.names,

        "status":
            "ready"
    }


# ============================================================
# IMAGE PREDICTION
# ============================================================

@router.post("/predict")
async def predict_image(
    file: UploadFile = File(...)
):

    # --------------------------------------------------------
    # Allowed image types
    # --------------------------------------------------------

    allowed_extensions = {

        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }


    # --------------------------------------------------------
    # Validate filename
    # --------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file name provided."
        )


    file_extension = Path(
        file.filename
    ).suffix.lower()


    # --------------------------------------------------------
    # Validate extension
    # --------------------------------------------------------

    if file_extension not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG, PNG and WEBP "
                "images are allowed."
            )
        )


    # --------------------------------------------------------
    # Read image
    # --------------------------------------------------------

    image_bytes = await file.read()


    if not image_bytes:

        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty."
        )


    temp_path = None


    try:

        # ----------------------------------------------------
        # Create temporary image
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            suffix=file_extension,
            delete=False
        ) as temp_file:

            temp_file.write(
                image_bytes
            )

            temp_path = Path(
                temp_file.name
            )


        # ----------------------------------------------------
        # YOLO11 prediction
        # ----------------------------------------------------

        results = model.predict(

            source=str(temp_path),

            imgsz=224,

            device="mps",

            verbose=False
        )


        result = results[0]


        # ----------------------------------------------------
        # Classification check
        # ----------------------------------------------------

        if result.probs is None:

            raise RuntimeError(
                "YOLO model did not return "
                "classification probabilities."
            )


        probabilities = result.probs


        # ----------------------------------------------------
        # Top prediction
        # ----------------------------------------------------

        health_prediction = extract_health_prediction(
            probabilities
        )

        predicted_class = health_prediction["prediction"]
        confidence = health_prediction["confidence"]
        class_probabilities = health_prediction["class_probabilities"]


        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return {

            "success":
                True,

            "component":
                "Component 02",

            "service":
                "Plantation Health Classification",

            "model":
                "YOLO11",

            "prediction":
                predicted_class,

            "confidence":
                round(
                    confidence * 100,
                    2
                ),

            "class_probabilities":
                class_probabilities,

            "image":
                file.filename
        }


    except HTTPException:

        raise


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Prediction failed: {str(e)}"
            )
        )


    finally:

        # ----------------------------------------------------
        # Delete temporary image
        # ----------------------------------------------------

        if (
            temp_path is not None
            and temp_path.exists()
        ):

            temp_path.unlink()


# ============================================================
# GET CLIMATE DATA
# ============================================================

@router.get("/climate")
def get_climate_data(
    latitude: float,
    longitude: float,
    date: str
):

    try:

        # ----------------------------------------------------
        # Get latest available climate
        # ----------------------------------------------------

        climate_result = (
            get_latest_available_climate(
                latitude=latitude,
                longitude=longitude,
                requested_date=date
            )
        )


        climate = climate_result[
            "climate"
        ]


        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return {

            "success":
                True,

            "source":
            "Open-Meteo",

            "location": {

                "latitude":
                    latitude,

                "longitude":
                    longitude
            },

            "requested_date":
                date,

            "climate_data_date":
                climate_result[
                    "data_date"
                ],

            "data_delay_days":
                climate_result[
                    "data_delay_days"
                ],

            "data_status":
                climate_result[
                    "data_status"
                ],

            "climate":
                climate
        }


    except HTTPException:

        raise


    except requests.RequestException as e:

        raise HTTPException(
            status_code=502,
            detail=(
                "Open-Meteo API request failed: "
                f"{str(e)}"
            )
        )


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                "Climate data processing failed: "
                f"{str(e)}"
            )
        )


# ============================================================
# COMBINED PLANTATION HEALTH + CLIMATE ASSESSMENT
# ============================================================

@router.post("/assess")
async def assess_plantation(

    files: Optional[list[UploadFile]] = File(default=None),

    # Keep the original field for clients that still send one image.
    file: Optional[UploadFile] = File(default=None),

    latitude: float = 6.9497,

    longitude: float = 80.7891,

    date: str = "2026-08-10"

):

    # ========================================================
    # 1. VALIDATE IMAGES
    # ========================================================

    allowed_extensions = {

        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }


    uploaded_files = list(files or [])
    if file is not None:
        uploaded_files.append(file)

    if not uploaded_files:
        raise HTTPException(
            status_code=400,
            detail="Please upload at least one plantation image."
        )

    if len(uploaded_files) > 5:
        raise HTTPException(
            status_code=400,
            detail="You can upload a maximum of 5 plantation images."
        )

    temp_paths = []


    try:

        # ====================================================
        # 2. SAVE TEMPORARY IMAGES
        # ====================================================

        for uploaded_file in uploaded_files:
            if not uploaded_file.filename:
                raise HTTPException(
                    status_code=400,
                    detail="One of the uploaded files has no file name."
                )

            file_extension = Path(uploaded_file.filename).suffix.lower()
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Only JPG, JPEG, PNG and WEBP "
                        "images are allowed."
                    )
                )

            image_bytes = await uploaded_file.read()
            if not image_bytes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Uploaded image '{uploaded_file.filename}' is empty."
                )

            with tempfile.NamedTemporaryFile(
                suffix=file_extension,
                delete=False
            ) as temp_file:
                temp_file.write(image_bytes)
                temp_paths.append(Path(temp_file.name))


        # ====================================================
        # 3. YOLO11 IMAGE ANALYSIS
        # ====================================================

        results = model.predict(
            source=[str(path) for path in temp_paths],
            imgsz=224,
            device="mps",
            verbose=False
        )

        # ====================================================
        # 4. ANALYZE EACH IMAGE AND AGGREGATE PROBABILITIES
        # ====================================================

        image_results = []
        healthy_probability_total = 0.0
        low_health_probability_total = 0.0

        for uploaded_file, result in zip(uploaded_files, results):
            if result.probs is None:
                raise RuntimeError(
                    "YOLO model did not return classification probabilities."
                )

            health_prediction = extract_health_prediction(result.probs)
            per_image_probabilities = health_prediction["class_probabilities"]
            healthy_probability_total += per_image_probabilities["healthy"]
            low_health_probability_total += per_image_probabilities["low_health"]

            image_results.append({
                "file_name": uploaded_file.filename,
                "prediction": health_prediction["prediction"],
                "confidence": round(health_prediction["confidence"] * 100, 2),
                "class_probabilities": per_image_probabilities,
                "image_health_score": per_image_probabilities["healthy"],
            })

        image_count = len(image_results)
        class_probabilities = {
            "healthy": round(healthy_probability_total / image_count, 2),
            "low_health": round(low_health_probability_total / image_count, 2),
        }
        predicted_class = (
            "healthy"
            if class_probabilities["healthy"] >= class_probabilities["low_health"]
            else "low_health"
        )
        confidence = class_probabilities[predicted_class] / 100
        image_health_score = class_probabilities["healthy"]
        low_health_image_count = sum(
            image["prediction"] == "low_health" for image in image_results
        )
        health_reason = build_health_reason(
            predicted_class,
            low_health_image_count,
            image_count,
        )


        # ====================================================
        # 7. GET OPEN-METEO CLIMATE DATA
        #
        # IMPORTANT:
        # Automatically searches previous dates when the
        # requested date is unavailable.
        # ====================================================

        climate_result = (
            get_latest_available_climate(

                latitude=latitude,

                longitude=longitude,

                requested_date=date
            )
        )


        climate = climate_result[
            "climate"
        ]


        # ====================================================
        # 8. EXTRACT CLIMATE VALUES
        # ====================================================

        temperature = climate[
            "temperature_c"
        ]


        rainfall = climate[
            "rainfall_mm"
        ]


        humidity = climate[
            "humidity_percent"
        ]


        wind_speed = climate[
            "wind_speed_m_s"
        ]


        solar_radiation = climate[
            "solar_radiation_kwh_m2_day"
        ]


        # ====================================================
        # 9. TEA-FOCUSED MULTI-DAY STRESS ASSESSMENT
        # ====================================================

        try:
            data_date = datetime.strptime(
                climate_result["data_date"], "%Y-%m-%d"
            ).date()
            climate_history = fetch_open_meteo_climate_window(
                latitude=latitude,
                longitude=longitude,
                end_date=data_date,
            )
        except requests.RequestException:
            # The one-day result remains usable; the response will mark the
            # assessment as lower confidence through its shorter window.
            climate_history = []

        stress_assessment = build_stress_assessment(climate, climate_history)
        heat_stress = stress_assessment["heat_stress"]
        water_stress = stress_assessment["water_stress"]
        rainfall_stress = stress_assessment["rainfall_stress"]
        humidity_stress = stress_assessment["humidity_stress"]
        wind_condition = stress_assessment["wind_condition"]
        solar_condition = stress_assessment["solar_condition"]
        climate_risk_score = stress_assessment["climate_risk_score"]
        overall_climate_risk = stress_assessment["overall_climate_risk"]
        early_warning = stress_assessment["early_warning"]

        # ====================================================
        # 18. RECOMMENDATIONS
        # ====================================================

        recommendations = []


        # ----------------------------------------------------
        # Heat recommendations
        # ----------------------------------------------------

        if heat_stress == "High":

            recommendations.append(

                "High heat stress detected. "
                "Increase shade cover or mulching, "
                "irrigate during cooler morning or "
                "evening hours, and monitor temperature "
                "conditions."
            )


        elif heat_stress == "Medium":

            recommendations.append(

                "Moderate heat stress detected. "
                "Monitor temperature conditions and "
                "maintain adequate shade and soil moisture."
            )


        # ----------------------------------------------------
        # Water recommendations
        # ----------------------------------------------------

        if water_stress == "High":

            recommendations.append(

                "High water stress detected. "
                "Activate supplementary irrigation "
                "and use mulch to reduce soil moisture loss."
            )


        elif water_stress == "Medium":

            recommendations.append(

                "Moderate water stress detected. "
                "Monitor soil moisture and schedule "
                "irrigation if rainfall remains low."
            )


        # ----------------------------------------------------
        # Rainfall recommendations
        # ----------------------------------------------------

        if rainfall_stress == "High":

            recommendations.append(

                "High rainfall stress detected. "
                "Improve field drainage and monitor "
                "for fungal disease risk."
            )


        elif rainfall_stress == "Medium":

            recommendations.append(

                "Moderate rainfall stress detected. "
                "Monitor drainage and avoid excessive "
                "soil moisture."
            )


        # ----------------------------------------------------
        # Humidity recommendations
        # ----------------------------------------------------

        if humidity_stress == "High":

            recommendations.append(

                "High humidity detected. Increase "
                "monitoring for fungal diseases and "
                "improve plantation airflow."
            )


        elif humidity_stress == "Medium":

            recommendations.append(

                "Moderate humidity detected. Monitor "
                "foliage for fungal disease symptoms "
                "and maintain good field ventilation."
            )


        # ----------------------------------------------------
        # Wind recommendations
        # ----------------------------------------------------

        if (
            wind_speed is not None
            and wind_speed >= 5
        ):

            recommendations.append(

                "High wind conditions detected. "
                "Monitor exposed plants and assess "
                "physical damage risk."
            )


        # ----------------------------------------------------
        # Solar recommendation
        # ----------------------------------------------------

        if solar_radiation is None:

            recommendations.append(

                "Solar radiation data is unavailable "
                "for this observation. Continue assessment "
                "using the available climate variables."
            )


        # ----------------------------------------------------
        # No recommendation
        # ----------------------------------------------------

        if not recommendations:

            recommendations.append(

                "Current conditions are generally "
                "suitable. Continue regular plantation "
                "monitoring."
            )


        # ====================================================
        # 19. FINAL RESPONSE
        # ====================================================

        return {

            "success":
                True,


            "component":
                "Component 02",


            "service":
                "AI-Powered Plantation Health "
                "& Climate Stress Assessment",


            # ------------------------------------------------
            # IMAGE ANALYSIS
            # ------------------------------------------------

            "image_analysis": {

                "model":
                    "YOLO11",

                "image_count":
                    image_count,

                "images":
                    image_results,

                "prediction":
                    predicted_class,

                "confidence":
                    round(
                        confidence * 100,
                        2
                    ),

                "class_probabilities":
                    class_probabilities,

                "image_health_score":
                    image_health_score,

                "health_reason":
                    health_reason
            },


            # ------------------------------------------------
            # LOCATION
            # ------------------------------------------------

            "location": {

                "latitude":
                    latitude,

                "longitude":
                    longitude
            },


            # ------------------------------------------------
            # REQUESTED ANALYSIS DATE
            # ------------------------------------------------

            "date":
                date,


            # ------------------------------------------------
            # CLIMATE
            # ------------------------------------------------

            "climate": {

                "source":
                    "Open-Meteo",

                "requested_date":
                    date,

                "data_date":
                    climate_result[
                        "data_date"
                    ],

                "data_delay_days":
                    climate_result[
                        "data_delay_days"
                    ],

                "data_status":
                    climate_result[
                        "data_status"
                    ],

                "temperature_c":
                    temperature,

                "temperature_max_c":
                    climate.get("temperature_max_c"),

                "temperature_min_c":
                    climate.get("temperature_min_c"),

                "rainfall_mm":
                    rainfall,

                "humidity_percent":
                    humidity,

                "wind_speed_m_s":
                    wind_speed,

                "solar_radiation_kwh_m2_day":
                    solar_radiation,

                "et0_mm":
                    climate.get("et0_mm"),

                "history_days_available":
                    stress_assessment["data_quality"]["available_days"],

                "history_window_days":
                    CLIMATE_HISTORY_DAYS
            },


            # ------------------------------------------------
            # STRESS ASSESSMENT
            # ------------------------------------------------

            "stress_assessment": {

                "heat_stress":
                    heat_stress,

                "water_stress":
                    water_stress,

                "rainfall_stress":
                    rainfall_stress,

                "humidity_stress":
                    humidity_stress,

                "wind_condition":
                    wind_condition,

                "solar_condition":
                    solar_condition,

                "climate_risk_score":
                    climate_risk_score,

                "overall_climate_risk":
                    overall_climate_risk,

                "early_warning":
                    early_warning,

                "details":
                    stress_assessment["details"],

                "data_quality":
                    stress_assessment["data_quality"]
            },


            # ------------------------------------------------
            # RECOMMENDATIONS
            # ------------------------------------------------

            "recommendations":
                recommendations
        }


    # ========================================================
    # HTTP EXCEPTION
    # ========================================================

    except HTTPException:

        raise


    # ========================================================
    # OPEN-METEO REQUEST ERROR
    # ========================================================

    except requests.RequestException as e:

        raise HTTPException(

            status_code=502,

            detail=(
                "Open-Meteo API request failed: "
                f"{str(e)}"
            )
        )


    # ========================================================
    # GENERAL ERROR
    # ========================================================

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=(
                "Assessment failed: "
                f"{str(e)}"
            )
        )


    # ========================================================
    # DELETE TEMP IMAGE
    # ========================================================

    finally:

        for temp_path in temp_paths:
            if temp_path.exists():
                temp_path.unlink()
            
