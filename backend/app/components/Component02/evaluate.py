from pathlib import Path
from ultralytics import YOLO


# ============================================================
# COMPONENT 02 - FULL MODEL EVALUATION
# YOLO11 CLASSIFICATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

DATASET_DIR = BASE_DIR / "plantation_health" / "data"

MODEL_PATH = (
    BASE_DIR
    / "runs"
    / "plantation_health_yolo11n_50epochs"
    / "weights"
    / "best.pt"
)

TEST_DIR = DATASET_DIR / "test"


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
print("COMPONENT 02 - FULL MODEL EVALUATION")
print("=" * 70)

model = YOLO(str(MODEL_PATH))

print()
print("Model loaded successfully")
print(f"Model: {MODEL_PATH}")
print(f"Classes: {model.names}")


# ============================================================
# CLASS INFORMATION
# ============================================================

class_names = model.names

healthy_dir = TEST_DIR / "healthy"
low_health_dir = TEST_DIR / "low_health"

healthy_images = list(healthy_dir.glob("*"))
low_health_images = list(low_health_dir.glob("*"))

healthy_images = [
    p for p in healthy_images
    if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
]

low_health_images = [
    p for p in low_health_images
    if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
]


print()
print("TEST DATASET")
print("-" * 70)
print(f"Healthy images    : {len(healthy_images)}")
print(f"Low-health images : {len(low_health_images)}")
print(f"Total test images : {len(healthy_images) + len(low_health_images)}")


# ============================================================
# PREDICTION
# ============================================================

all_images = []

for image in healthy_images:
    all_images.append((image, 0))

for image in low_health_images:
    all_images.append((image, 1))


correct = 0
wrong = 0

# Confusion matrix
#              Predicted
#              healthy   low_health
#
# Actual
# healthy         TN          FP
# low_health      FN          TP

true_healthy_pred_healthy = 0
true_healthy_pred_low = 0

true_low_pred_healthy = 0
true_low_pred_low = 0

wrong_predictions = []


print()
print("Running predictions...")
print("-" * 70)


for index, (image_path, actual_class) in enumerate(all_images, start=1):

    results = model.predict(
        source=str(image_path),
        imgsz=224,
        device="mps",
        verbose=False
    )

    result = results[0]

    predicted_class = result.probs.top1
    confidence = float(result.probs.top1conf)

    if predicted_class == actual_class:

        correct += 1

    else:

        wrong += 1

        wrong_predictions.append({
            "image": image_path.name,
            "actual": class_names[actual_class],
            "predicted": class_names[predicted_class],
            "confidence": confidence
        })


    # --------------------------------------------------------
    # Confusion matrix values
    # --------------------------------------------------------

    if actual_class == 0 and predicted_class == 0:
        true_healthy_pred_healthy += 1

    elif actual_class == 0 and predicted_class == 1:
        true_healthy_pred_low += 1

    elif actual_class == 1 and predicted_class == 0:
        true_low_pred_healthy += 1

    elif actual_class == 1 and predicted_class == 1:
        true_low_pred_low += 1


    if index % 50 == 0 or index == len(all_images):
        print(
            f"Processed {index}/{len(all_images)}"
        )


# ============================================================
# ACCURACY
# ============================================================

total = len(all_images)

accuracy = correct / total if total > 0 else 0


# ============================================================
# METRICS - HEALTHY
# ============================================================

healthy_tp = true_healthy_pred_healthy
healthy_fp = true_low_pred_healthy
healthy_fn = true_healthy_pred_low

healthy_precision = (
    healthy_tp / (healthy_tp + healthy_fp)
    if (healthy_tp + healthy_fp) > 0 else 0
)

healthy_recall = (
    healthy_tp / (healthy_tp + healthy_fn)
    if (healthy_tp + healthy_fn) > 0 else 0
)

healthy_f1 = (
    2 * healthy_precision * healthy_recall /
    (healthy_precision + healthy_recall)
    if (healthy_precision + healthy_recall) > 0 else 0
)


# ============================================================
# METRICS - LOW HEALTH
# ============================================================

low_tp = true_low_pred_low
low_fp = true_healthy_pred_low
low_fn = true_low_pred_healthy

low_precision = (
    low_tp / (low_tp + low_fp)
    if (low_tp + low_fp) > 0 else 0
)

low_recall = (
    low_tp / (low_tp + low_fn)
    if (low_tp + low_fn) > 0 else 0
)

low_f1 = (
    2 * low_precision * low_recall /
    (low_precision + low_recall)
    if (low_precision + low_recall) > 0 else 0
)


# ============================================================
# MACRO AVERAGE
# ============================================================

macro_precision = (
    healthy_precision + low_precision
) / 2

macro_recall = (
    healthy_recall + low_recall
) / 2

macro_f1 = (
    healthy_f1 + low_f1
) / 2


# ============================================================
# FINAL REPORT
# ============================================================

print()
print("=" * 70)
print("FINAL EVALUATION RESULTS")
print("=" * 70)

print()
print(f"Total Test Images : {total}")
print(f"Correct           : {correct}")
print(f"Wrong             : {wrong}")
print(f"Accuracy          : {accuracy * 100:.2f}%")

print()
print("=" * 70)
print("CLASSIFICATION METRICS")
print("=" * 70)

print()
print("Healthy")
print(f"  Precision : {healthy_precision * 100:.2f}%")
print(f"  Recall    : {healthy_recall * 100:.2f}%")
print(f"  F1-Score  : {healthy_f1 * 100:.2f}%")

print()
print("Low Health")
print(f"  Precision : {low_precision * 100:.2f}%")
print(f"  Recall    : {low_recall * 100:.2f}%")
print(f"  F1-Score  : {low_f1 * 100:.2f}%")

print()
print("Macro Average")
print(f"  Precision : {macro_precision * 100:.2f}%")
print(f"  Recall    : {macro_recall * 100:.2f}%")
print(f"  F1-Score  : {macro_f1 * 100:.2f}%")


# ============================================================
# CONFUSION MATRIX
# ============================================================

print()
print("=" * 70)
print("CONFUSION MATRIX")
print("=" * 70)

print()
print("                    Predicted")
print("                 Healthy   Low Health")
print(
    f"Actual Healthy     "
    f"{true_healthy_pred_healthy:^8}   "
    f"{true_healthy_pred_low:^10}"
)

print(
    f"Actual Low Health  "
    f"{true_low_pred_healthy:^8}   "
    f"{true_low_pred_low:^10}"
)


# ============================================================
# WRONG PREDICTIONS
# ============================================================

print()
print("=" * 70)
print("WRONG PREDICTIONS")
print("=" * 70)

if len(wrong_predictions) == 0:

    print("No wrong predictions found.")

else:

    for item in wrong_predictions:

        print()
        print(f"Image      : {item['image']}")
        print(f"Actual     : {item['actual']}")
        print(f"Predicted  : {item['predicted']}")
        print(
            f"Confidence : "
            f"{item['confidence'] * 100:.2f}%"
        )


# ============================================================
# COMPLETED
# ============================================================

print()
print("=" * 70)
print("✅ COMPONENT 02 FULL EVALUATION COMPLETED")
print("=" * 70)