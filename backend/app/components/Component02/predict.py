from pathlib import Path
from ultralytics import YOLO


# ============================================================
# COMPONENT 02 - PLANTATION HEALTH PREDICTION
# YOLO11 CLASSIFICATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# MODEL PATH
# ============================================================

# IMPORTANT:
# This is the NEW model trained after adding the new
# Low Health images to the dataset.
MODEL_PATH = (
    BASE_DIR
    / "runs"
    / "plantation_health_yolo11n_updated_50epochs_v2"
    / "weights"
    / "best.pt"
)


# ============================================================
# LOAD MODEL
# ============================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"""
============================================================
TRAINED MODEL NOT FOUND
============================================================

Expected model:
{MODEL_PATH}

Please make sure this file exists:

runs/
└── plantation_health_yolo11n_updated_50epochs_v2/
    └── weights/
        └── best.pt

============================================================
"""
    )


model = YOLO(str(MODEL_PATH))


# ============================================================
# MODEL INFORMATION
# ============================================================

print()
print("=" * 70)
print("COMPONENT 02 - PLANTATION HEALTH PREDICTION")
print("=" * 70)

print()
print("Model loaded successfully")
print(f"Model   : {MODEL_PATH}")
print(f"Classes : {model.names}")

print()
print("Using NEW UPDATED trained model")
print(
    "Training experiment : "
    "plantation_health_yolo11n_updated_50epochs_v2"
)

print("=" * 70)


# ============================================================
# DEVICE
# ============================================================

# Apple Silicon Mac:
# MPS = Metal Performance Shaders
#
# If MPS is not available, automatically use CPU.

try:
    import torch

    if torch.backends.mps.is_available():
        DEVICE = "mps"
    else:
        DEVICE = "cpu"

except Exception:
    DEVICE = "cpu"


print()
print(f"Prediction device : {DEVICE}")
print("=" * 70)


# ============================================================
# PREDICTION FUNCTION
# ============================================================

def predict_image(image_path):
    """
    Predict plantation health from a single image.

    Classes:
        0 = healthy
        1 = low_health
    """

    image_path = Path(image_path)


    # ========================================================
    # CHECK IMAGE EXISTS
    # ========================================================

    if not image_path.exists():
        raise FileNotFoundError(
            f"""
Image not found:

{image_path}
"""
        )


    # ========================================================
    # CHECK FILE TYPE
    # ========================================================

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }

    if image_path.suffix.lower() not in allowed_extensions:
        raise ValueError(
            f"""
Unsupported image format:

{image_path.suffix}

Supported formats:
.jpg
.jpeg
.png
.webp
"""
        )


    # ========================================================
    # RUN MODEL PREDICTION
    # ========================================================

    results = model.predict(
        source=str(image_path),
        imgsz=224,
        device=DEVICE,
        verbose=False
    )


    # ========================================================
    # GET RESULT
    # ========================================================

    result = results[0]


    # ========================================================
    # CHECK CLASSIFICATION RESULT
    # ========================================================

    if result.probs is None:
        raise RuntimeError(
            "Model did not return classification probabilities."
        )


    probabilities = result.probs


    # ========================================================
    # TOP PREDICTION
    # ========================================================

    predicted_class_id = int(
        probabilities.top1
    )

    confidence = float(
        probabilities.top1conf
    )

    predicted_class = model.names[
        predicted_class_id
    ]


    # ========================================================
    # CLASS PROBABILITIES
    # ========================================================

    probability_dict = {}

    for class_id, probability in enumerate(
        probabilities.data
    ):

        class_name = model.names[class_id]

        probability_value = float(
            probability
        )

        probability_dict[class_name] = (
            probability_value
        )


    # ========================================================
    # DISPLAY RESULT
    # ========================================================

    print()
    print("=" * 70)
    print("PREDICTION RESULT")
    print("=" * 70)

    print()
    print(f"Image      : {image_path.name}")
    print(f"Prediction : {predicted_class}")
    print(
        f"Confidence : "
        f"{confidence * 100:.2f}%"
    )


    # ========================================================
    # DISPLAY CLASS PROBABILITIES
    # ========================================================

    print()
    print("CLASS PROBABILITIES")
    print("-" * 70)

    for class_id, probability in enumerate(
        probabilities.data
    ):

        class_name = model.names[class_id]

        probability_value = float(
            probability
        )

        print(
            f"{class_name:<15} : "
            f"{probability_value * 100:.2f}%"
        )


    print("=" * 70)


    # ========================================================
    # HUMAN-READABLE HEALTH STATUS
    # ========================================================

    normalized_prediction = (
        str(predicted_class)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


    if normalized_prediction == "healthy":

        health_status = "Healthy"

        recommendation = (
            "The tea plantation appears healthy. "
            "Continue regular monitoring and "
            "normal plantation management."
        )

    elif normalized_prediction == "low_health":

        health_status = "Low Health"

        recommendation = (
            "The tea plantation shows signs of low health. "
            "Further inspection and appropriate "
            "plantation management are recommended."
        )

    else:

        health_status = predicted_class

        recommendation = (
            "Please perform further inspection."
        )


    # ========================================================
    # DISPLAY HEALTH STATUS
    # ========================================================

    print()
    print("HEALTH ASSESSMENT")
    print("-" * 70)

    print(
        f"Health Status : {health_status}"
    )

    print(
        f"Recommendation: {recommendation}"
    )

    print("=" * 70)


    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {
        "image": image_path.name,

        "prediction": predicted_class,

        "health_status": health_status,

        "confidence": confidence,

        "confidence_percentage": (
            confidence * 100
        ),

        "probabilities": probability_dict,

        "recommendation": recommendation,

        "model": (
            "plantation_health_yolo11n_"
            "updated_50epochs_v2"
        ),

        "model_path": str(MODEL_PATH),

        "device": DEVICE
    }


# ============================================================
# TEST IMAGE
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # CHANGE THIS PATH TO THE IMAGE YOU WANT TO TEST
    # --------------------------------------------------------

    IMAGE_PATH = Path(
        "/Users/gayan/Desktop/SLIIT SE/RESEARCH/"
        "dataset/plantation_health_dataset/"
        "Low_helth/"
        "IMG_20230612_165244_jpg.rf."
        "2d7a5962ac11643e6b7a587b65e1db3f.jpg"
    )


    # --------------------------------------------------------
    # RUN PREDICTION
    # --------------------------------------------------------

    result = predict_image(
        IMAGE_PATH
    )


    # --------------------------------------------------------
    # PRINT RETURNED RESULT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RETURNED RESULT")
    print("=" * 70)

    print(result)

    print("=" * 70)