"""Shared expected-yield feature and target definitions."""

TARGET = "kg_per_Acre"
FEATURES = [
    "Year",
    "Month_Number",
    "Week_Number",
    "Temperature",
    "Rainfall_mm",
    "Humidity",
    "Wind_Speed",
    "Solar_Radiation",
    "Location",
    "Grown_Type",
]
NUMERIC_FEATURES = FEATURES[:8]
CATEGORICAL_FEATURES = FEATURES[8:]
CLIMATE_FEATURES = [
    "Temperature",
    "Rainfall_mm",
    "Humidity",
    "Wind_Speed",
    "Solar_Radiation",
]
GROWN_TYPES = ("HIGH grown", "MID grown", "LOW grown")
