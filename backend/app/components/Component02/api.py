from pathlib import Path
import tempfile
import requests
from datetime import datetime, timedelta

from fastapi import APIRouter, UploadFile, File, HTTPException
from ultralytics import YOLO


# ============================================================
# COMPONENT 02
# AI-POWERED PLANTATION HEALTH & CLIMATE STRESS ASSESSMENT
#
# YOLO11 + NASA POWER
#
# Features:
#   1. YOLO11 Plantation Health Classification
#   2. Image Health Score
#   3. NASA POWER Climate Data
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
    / "plantation_health_yolo11n_50epochs"
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
# NASA POWER
# ============================================================

NASA_POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
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


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/component02",
    tags=["Component 02 - Plantation Health"]
)


# ============================================================
# HELPER
# CHECK VALID NASA VALUE
# ============================================================

def is_valid_nasa_value(value):
    """
    NASA POWER may return:
        None
        -999
        -999.0

    These values mean the data is unavailable.
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
# CLEAN NASA VALUE
# ============================================================

def clean_nasa_value(value):
    """
    Convert NASA POWER value into float.

    Invalid values become None.
    """

    if not is_valid_nasa_value(value):

        return None

    return round(
        float(value),
        2
    )


# ============================================================
# HELPER
# GET ONE DAY FROM NASA POWER
# ============================================================

def fetch_nasa_climate_for_date(
    latitude: float,
    longitude: float,
    date_obj
):
    """
    Fetch NASA POWER climate data for one date.

    Returns:

    {
        "temperature_c": ...,
        "rainfall_mm": ...,
        "humidity_percent": ...,
        "wind_speed_m_s": ...,
        "solar_radiation_kwh_m2_day": ...
    }

    """

    requested_date = date_obj.strftime(
        "%Y%m%d"
    )


    # --------------------------------------------------------
    # NASA POWER parameters
    # --------------------------------------------------------

    params = {

        "parameters": (
            "T2M,"
            "PRECTOTCORR,"
            "RH2M,"
            "WS10M,"
            "ALLSKY_SFC_SW_DWN"
        ),

        "community": "AG",

        "longitude": longitude,

        "latitude": latitude,

        "start": requested_date,

        "end": requested_date,

        "format": "JSON"
    }


    # --------------------------------------------------------
    # Request NASA POWER
    # --------------------------------------------------------

    response = requests.get(
        NASA_POWER_URL,
        params=params,
        timeout=30
    )


    response.raise_for_status()


    nasa_data = response.json()


    # --------------------------------------------------------
    # Extract parameter data
    # --------------------------------------------------------

    parameter_data = (
        nasa_data
        .get("properties", {})
        .get("parameter", {})
    )


    # --------------------------------------------------------
    # Extract values
    # --------------------------------------------------------

    temperature = (
        parameter_data
        .get("T2M", {})
        .get(requested_date)
    )


    rainfall = (
        parameter_data
        .get("PRECTOTCORR", {})
        .get(requested_date)
    )


    humidity = (
        parameter_data
        .get("RH2M", {})
        .get(requested_date)
    )


    wind_speed = (
        parameter_data
        .get("WS10M", {})
        .get(requested_date)
    )


    solar_radiation = (
        parameter_data
        .get("ALLSKY_SFC_SW_DWN", {})
        .get(requested_date)
    )


    # --------------------------------------------------------
    # Clean values
    # --------------------------------------------------------

    climate = {

        "temperature_c":
            clean_nasa_value(
                temperature
            ),

        "rainfall_mm":
            clean_nasa_value(
                rainfall
            ),

        "humidity_percent":
            clean_nasa_value(
                humidity
            ),

        "wind_speed_m_s":
            clean_nasa_value(
                wind_speed
            ),

        "solar_radiation_kwh_m2_day":
            clean_nasa_value(
                solar_radiation
            )
    }


    return climate


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
            f"NASA POWER: checking "
            f"{candidate_date}"
        )


        try:

            climate = fetch_nasa_climate_for_date(
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

        if has_meteorological_data(
            climate
        ):

            data_delay_days = (
                requested_date_obj
                - candidate_date
            ).days


            if data_delay_days == 0:

                data_status = "Current"

            else:

                data_status = (
                    "Latest Available"
                )


            print(
                f"NASA POWER: data found for "
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
            "NASA POWER climate data is not available "
            f"for {requested_date} or the previous "
            f"{MAX_CLIMATE_LOOKBACK_DAYS} days."
        )
    )


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

        predicted_class_id = int(
            probabilities.top1
        )


        confidence = float(
            probabilities.top1conf
        )


        predicted_class = model.names[
            predicted_class_id
        ]


        # ----------------------------------------------------
        # All class probabilities
        # ----------------------------------------------------

        class_probabilities = {}


        for class_id, probability in enumerate(
            probabilities.data
        ):

            class_name = model.names[
                class_id
            ]


            class_probabilities[
                class_name
            ] = round(

                float(probability) * 100,

                2
            )


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
                "NASA POWER",

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
                "NASA POWER API request failed: "
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

    file: UploadFile = File(...),

    latitude: float = 6.9497,

    longitude: float = 80.7891,

    date: str = "2026-08-10"

):

    # ========================================================
    # 1. VALIDATE IMAGE
    # ========================================================

    allowed_extensions = {

        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }


    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file name provided."
        )


    file_extension = Path(
        file.filename
    ).suffix.lower()


    if file_extension not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG, PNG and WEBP "
                "images are allowed."
            )
        )


    image_bytes = await file.read()


    if not image_bytes:

        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty."
        )


    temp_path = None


    try:

        # ====================================================
        # 2. SAVE TEMPORARY IMAGE
        # ====================================================

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


        # ====================================================
        # 3. YOLO11 IMAGE ANALYSIS
        # ====================================================

        results = model.predict(

            source=str(temp_path),

            imgsz=224,

            device="mps",

            verbose=False
        )


        result = results[0]


        if result.probs is None:

            raise RuntimeError(
                "YOLO model did not return "
                "classification probabilities."
            )


        probabilities = result.probs


        # ====================================================
        # 4. TOP PREDICTION
        # ====================================================

        predicted_class_id = int(
            probabilities.top1
        )


        confidence = float(
            probabilities.top1conf
        )


        predicted_class = model.names[
            predicted_class_id
        ]


        # ====================================================
        # 5. CLASS PROBABILITIES
        # ====================================================

        class_probabilities = {}


        for class_id, probability in enumerate(
            probabilities.data
        ):

            class_name = model.names[
                class_id
            ]


            class_probabilities[
                class_name
            ] = round(

                float(probability) * 100,

                2
            )


        # ====================================================
        # 6. IMAGE HEALTH SCORE
        # ====================================================

        healthy_probability = None


        for class_id, probability in enumerate(
            probabilities.data
        ):

            class_name = model.names[
                class_id
            ].lower()


            if class_name in {

                "healthy",

                "high_health",

                "good_health"

            }:

                healthy_probability = float(
                    probability
                )

                break


        if healthy_probability is not None:

            image_health_score = round(

                healthy_probability * 100,

                2
            )

        else:

            image_health_score = round(

                confidence * 100,

                2
            )


        # ====================================================
        # 7. GET NASA POWER CLIMATE DATA
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
        # 9. HEAT STRESS
        # ====================================================

        if temperature is None:

            heat_stress = "Unknown"

        elif temperature >= 30:

            heat_stress = "High"

        elif temperature >= 27:

            heat_stress = "Medium"

        else:

            heat_stress = "Low"


        # ====================================================
        # 10. WATER STRESS
        # ====================================================

        if rainfall is None:

            water_stress = "Unknown"

        elif rainfall < 2:

            water_stress = "High"

        elif rainfall < 10:

            water_stress = "Medium"

        else:

            water_stress = "Low"


        # ====================================================
        # 11. RAINFALL STRESS
        # ====================================================

        if rainfall is None:

            rainfall_stress = "Unknown"

        elif rainfall > 50:

            rainfall_stress = "High"

        elif rainfall > 25:

            rainfall_stress = "Medium"

        else:

            rainfall_stress = "Low"


        # ====================================================
        # 12. HUMIDITY STRESS
        # ====================================================

        if humidity is None:

            humidity_stress = "Unknown"

        elif humidity >= 90:

            humidity_stress = "High"

        elif humidity >= 80:

            humidity_stress = "Medium"

        else:

            humidity_stress = "Low"


        # ====================================================
        # 13. WIND CONDITION
        # ====================================================

        if wind_speed is None:

            wind_condition = "Unknown"

        elif wind_speed >= 5:

            wind_condition = "High"

        elif wind_speed >= 2:

            wind_condition = "Moderate"

        else:

            wind_condition = "Low"


        # ====================================================
        # 14. SOLAR RADIATION CONDITION
        # ====================================================

        if solar_radiation is None:

            solar_condition = "Unknown"

        elif solar_radiation < 3:

            solar_condition = "Low"

        elif solar_radiation < 6:

            solar_condition = "Moderate"

        else:

            solar_condition = "High"


        # ====================================================
        # 15. CLIMATE RISK SCORE
        # ====================================================

        stress_score_map = {

            "Low": 0,

            "Medium": 50,

            "High": 100,

            "Unknown": 25
        }


        stress_scores = [

            stress_score_map.get(
                heat_stress,
                25
            ),

            stress_score_map.get(
                water_stress,
                25
            ),

            stress_score_map.get(
                rainfall_stress,
                25
            ),

            stress_score_map.get(
                humidity_stress,
                25
            )
        ]


        climate_risk_score = round(

            sum(stress_scores)
            / len(stress_scores),

            2
        )


        # ====================================================
        # 16. OVERALL CLIMATE RISK
        # ====================================================

        if climate_risk_score >= 70:

            overall_climate_risk = "High"

        elif climate_risk_score >= 40:

            overall_climate_risk = "Medium"

        else:

            overall_climate_risk = "Low"


        # ====================================================
        # 17. EARLY WARNING
        # ====================================================

        stress_levels = [

            heat_stress,

            water_stress,

            rainfall_stress,

            humidity_stress
        ]


        if "High" in stress_levels:

            early_warning = (
                "Immediate Risk"
            )

        elif "Medium" in stress_levels:

            early_warning = (
                "Monitor Conditions"
            )

        else:

            early_warning = (
                "No Immediate Risk"
            )


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
                    image_health_score
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
                    "NASA POWER",

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

                "rainfall_mm":
                    rainfall,

                "humidity_percent":
                    humidity,

                "wind_speed_m_s":
                    wind_speed,

                "solar_radiation_kwh_m2_day":
                    solar_radiation
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
                    early_warning
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
    # NASA POWER REQUEST ERROR
    # ========================================================

    except requests.RequestException as e:

        raise HTTPException(

            status_code=502,

            detail=(
                "NASA POWER API request failed: "
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

        if (
            temp_path is not None
            and temp_path.exists()
        ):

            temp_path.unlink()