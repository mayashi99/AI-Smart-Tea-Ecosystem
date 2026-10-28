"""Production model loading and health-class aggregation for plantation images."""

from ultralytics import YOLO

from DL.utils.component02.paths import PLANTATION_PRODUCTION_MODEL


def load_model():
    """Load the configured production plantation-health classifier."""
    if not PLANTATION_PRODUCTION_MODEL.is_file():
        raise FileNotFoundError(f"Trained model not found:\n{PLANTATION_PRODUCTION_MODEL}")
    return YOLO(str(PLANTATION_PRODUCTION_MODEL))


def canonical_health_class(class_name):
    """Map every trained class into the public healthy/low_health contract."""
    normalized_name = str(class_name).strip().lower()
    normalized_name = normalized_name.replace("-", "_").replace(" ", "_")
    return "healthy" if normalized_name == "healthy" else "low_health"


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


def extract_health_prediction(probabilities, model):
    """Aggregate a model probability vector into the two public categories."""
    predicted_class_id = int(probabilities.top1)
    raw_predicted_class = model.names[predicted_class_id]
    category_probabilities = {"healthy": 0.0, "low_health": 0.0}
    for class_id, probability in enumerate(probabilities.data):
        category = canonical_health_class(model.names[class_id])
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
