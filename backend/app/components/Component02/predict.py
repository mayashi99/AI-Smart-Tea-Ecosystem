from pathlib import Path
from ultralytics import YOLO


# ============================================================
# COMPONENT 02 - PLANTATION HEALTH PREDICTION
# YOLO11 CLASSIFICATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# PATHS
# ============================================================

# IMPORTANT:
# This is the CLEAN model trained on the leakage-free dataset.
MODEL_PATH = (
    BASE_DIR
    / "runs"
    / "plantation_health_yolo11n_clean_50epochs"
    / "weights"
    / "best.pt"
)


# ============================================================
# LOAD MODEL
# ============================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"""
Trained model not found.

Expected model:
{MODEL_PATH}

Please make sure:
runs/plantation_health_yolo11n_clean_50epochs/weights/best.pt
exists.
"""
    )


model = YOLO(str(MODEL_PATH))


# ============================================================
# MODEL INFORMATION
# ============================================================

print("=" * 70)
print("COMPONENT 02 - PLANTATION HEALTH PREDICTION")
print("=" * 70)

print()
print("Model loaded successfully")
print(f"Model : {MODEL_PATH}")
print(f"Classes : {model.names}")

print()
print("Using CLEAN trained model")
print("Training experiment : plantation_health_yolo11n_clean_50epochs")
print("=" * 70)


# ============================================================
# PREDICTION FUNCTION
# ============================================================

def predict_image(image_path):

    image_path = Path(image_path)

    # --------------------------------------------------------
    # Check image
    # --------------------------------------------------------

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found:\n{image_path}"
        )

    # --------------------------------------------------------
    # Run prediction
    # --------------------------------------------------------

    results = model.predict(
        source=str(image_path),
        imgsz=224,
        device="mps",
        verbose=False
    )

    result = results[0]

    # --------------------------------------------------------
    # Classification probabilities
    # --------------------------------------------------------

    probabilities = result.probs

    predicted_class_id = int(probabilities.top1)

    confidence = float(
        probabilities.top1conf
    )

    predicted_class = model.names[
        predicted_class_id
    ]


    # ========================================================
    # PRINT RESULT
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

    # --------------------------------------------------------
    # Class probabilities
    # --------------------------------------------------------

    print()
    print("CLASS PROBABILITIES")
    print("-" * 70)

    probability_dict = {}

    for class_id, probability in enumerate(
        probabilities.data
    ):

        class_name = model.names[class_id]

        probability_value = float(
            probability
        )

        probability_percentage = (
            probability_value * 100
        )

        probability_dict[class_name] = (
            probability_value
        )

        print(
            f"{class_name:<15} : "
            f"{probability_percentage:.2f}%"
        )


    print("=" * 70)


    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {
        "image": image_path.name,
        "prediction": predicted_class,
        "confidence": confidence,
        "probabilities": probability_dict,
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
    # Run prediction
    # --------------------------------------------------------

    result = predict_image(IMAGE_PATH)

    print()
    print("Returned result:")
    print(result)