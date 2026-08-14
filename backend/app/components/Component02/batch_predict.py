from pathlib import Path
from ultralytics import YOLO


# ============================================================
# COMPONENT 02 - BATCH TEST PREDICTION
# YOLO11 CLASSIFICATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# MODEL
# ============================================================

MODEL_PATH = (
    BASE_DIR
    / "runs"
    / "plantation_health_yolo11n_50epochs"
    / "weights"
    / "best.pt"
)


# ============================================================
# TEST DATASET
# ============================================================

TEST_DIR = (
    BASE_DIR
    / "plantation_health"
    / "data"
    / "test"
)


# ============================================================
# CHECK PATHS
# ============================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Model not found:\n{MODEL_PATH}"
    )

if not TEST_DIR.exists():
    raise FileNotFoundError(
        f"Test dataset not found:\n{TEST_DIR}"
    )


# ============================================================
# LOAD MODEL
# ============================================================

print("=" * 70)
print("COMPONENT 02 - BATCH TEST PREDICTION")
print("=" * 70)

model = YOLO(str(MODEL_PATH))

print()
print("Model loaded successfully")
print(f"Model : {MODEL_PATH}")
print(f"Classes : {model.names}")


# ============================================================
# FIND TEST IMAGES
# ============================================================

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}

images = []

for class_name in model.names.values():

    class_dir = TEST_DIR / class_name

    if not class_dir.exists():
        print(
            f"WARNING: Folder not found: {class_dir}"
        )
        continue

    for image_path in class_dir.iterdir():

        if (
            image_path.is_file()
            and image_path.suffix.lower()
            in IMAGE_EXTENSIONS
        ):
            images.append(
                (image_path, class_name)
            )


# ============================================================
# DATASET INFORMATION
# ============================================================

print()
print("=" * 70)
print("TEST DATASET")
print("=" * 70)

print(
    f"Total test images : {len(images)}"
)

for class_name in model.names.values():

    count = sum(
        1
        for _, actual_class in images
        if actual_class == class_name
    )

    print(
        f"{class_name:<15}: {count}"
    )


# ============================================================
# PREDICTION
# ============================================================

correct = 0
incorrect = 0

wrong_predictions = []


print()
print("=" * 70)
print("STARTING BATCH PREDICTION")
print("=" * 70)


for index, (image_path, actual_class) in enumerate(
    images,
    start=1
):

    results = model.predict(
        source=str(image_path),
        imgsz=224,
        device="mps",
        verbose=False,
    )

    result = results[0]

    probabilities = result.probs

    predicted_class_id = probabilities.top1

    confidence = float(
        probabilities.top1conf
    )

    predicted_class = model.names[
        predicted_class_id
    ]


    # --------------------------------------------------------
    # Compare actual vs predicted
    # --------------------------------------------------------

    if predicted_class == actual_class:

        correct += 1

    else:

        incorrect += 1

        wrong_predictions.append({
            "image": image_path.name,
            "actual": actual_class,
            "predicted": predicted_class,
            "confidence": confidence,
        })


    # --------------------------------------------------------
    # Progress
    # --------------------------------------------------------

    print(
        f"[{index}/{len(images)}] "
        f"{predicted_class:<12} "
        f"{confidence * 100:6.2f}% "
        f"| Actual: {actual_class:<12} "
        f"| {image_path.name}"
    )


# ============================================================
# FINAL RESULTS
# ============================================================

total = len(images)

accuracy = (
    correct / total
    if total > 0
    else 0
)


print()
print("=" * 70)
print("FINAL BATCH PREDICTION RESULTS")
print("=" * 70)

print()
print(f"Total Images        : {total}")
print(f"Correct Predictions : {correct}")
print(f"Wrong Predictions   : {incorrect}")

print()
print(
    f"Accuracy            : "
    f"{accuracy * 100:.2f}%"
)


# ============================================================
# MISCLASSIFIED IMAGES
# ============================================================

print()
print("=" * 70)
print("MISCLASSIFIED IMAGES")
print("=" * 70)


if wrong_predictions:

    for item in wrong_predictions:

        print()
        print(f"Image      : {item['image']}")
        print(f"Actual     : {item['actual']}")
        print(f"Predicted  : {item['predicted']}")
        print(
            f"Confidence : "
            f"{item['confidence'] * 100:.2f}%"
        )

else:

    print()
    print("No misclassified images found.")


print()
print("=" * 70)
print("BATCH PREDICTION COMPLETED")
print("=" * 70)