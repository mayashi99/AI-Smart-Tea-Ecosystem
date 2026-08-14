from pathlib import Path
from ultralytics import YOLO


# ============================================================
# COMPONENT 02 - PLANTATION HEALTH PREDICTION
# YOLO11 CLASSIFICATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# Trained best model
MODEL_PATH = (
    BASE_DIR
    / "runs"
    / "plantation_health_yolo11n_50epochs"
    / "weights"
    / "best.pt"
)


# ============================================================
# LOAD MODEL
# ============================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Trained model not found:\n{MODEL_PATH}"
    )

model = YOLO(str(MODEL_PATH))

print("=" * 60)
print("COMPONENT 02 - PLANTATION HEALTH PREDICTION")
print("=" * 60)

print("Model loaded successfully")
print(f"Model: {MODEL_PATH}")
print(f"Classes: {model.names}")


# ============================================================
# PREDICTION FUNCTION
# ============================================================

def predict_image(image_path):

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found:\n{image_path}"
        )

    results = model.predict(
        source=str(image_path),
        imgsz=224,
        device="mps",
        verbose=False
    )

    result = results[0]

    # Classification probabilities
    probabilities = result.probs

    predicted_class_id = probabilities.top1
    confidence = float(probabilities.top1conf)

    predicted_class = model.names[predicted_class_id]

    print()
    print("=" * 60)
    print("PREDICTION RESULT")
    print("=" * 60)

    print(f"Image      : {image_path.name}")
    print(f"Prediction : {predicted_class}")
    print(f"Confidence : {confidence * 100:.2f}%")

    print()
    print("Class probabilities:")

    for class_id, probability in enumerate(probabilities.data):
        class_name = model.names[class_id]
        probability_value = float(probability)

        print(
            f"  {class_name:<12} : "
            f"{probability_value * 100:.2f}%"
        )

    print("=" * 60)

    return {
        "image": image_path.name,
        "prediction": predicted_class,
        "confidence": confidence,
    }


# ============================================================
# TEST IMAGE
# ============================================================

if __name__ == "__main__":

    # CHANGE THIS PATH TO YOUR TEST IMAGE
    IMAGE_PATH = Path('/Users/gayan/Desktop/SLIIT SE/RESEARCH/dataset/plantation_health_dataset/Low_helth/IMG_20230612_165244_jpg.rf.2d7a5962ac11643e6b7a587b65e1db3f.jpg')

    predict_image(IMAGE_PATH)
