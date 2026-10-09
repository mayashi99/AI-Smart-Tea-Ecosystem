
from pathlib import Path
import csv
import json

import torch
from ultralytics import YOLO
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix,
)

# ============================================================
# HARVEST READINESS - FINAL TEST EVALUATION
# MEMORY-EFFICIENT BATCH PREDICTION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

TEST_DIR = BASE_DIR / "data" / "test"

MODEL_PATH = (
    BASE_DIR
    / "runs"
    / "harvest_readiness_yolo11n_50epochs"
    / "weights"
    / "best.pt"
)

OUTPUT_DIR = BASE_DIR / "evaluation"

CLASS_NAMES = [
    "Harvest_Not_Ready",
    "Harvest_Ready",
]

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

IMAGE_SIZE = 224
BATCH_SIZE = 8

# MPS is attempted first; CPU is the fallback.
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"

# ============================================================
# CHECK PATHS
# ============================================================

if not MODEL_PATH.is_file():
    raise FileNotFoundError(
        f"Model not found:\n{MODEL_PATH}"
    )

if not TEST_DIR.is_dir():
    raise FileNotFoundError(
        f"Test directory not found:\n{TEST_DIR}"
    )

for class_name in CLASS_NAMES:
    class_dir = TEST_DIR / class_name

    if not class_dir.is_dir():
        raise FileNotFoundError(
            f"Test class directory not found:\n{class_dir}"
        )

# ============================================================
# COLLECT TEST IMAGES
# ============================================================

image_paths = []
true_labels = []

for class_index, class_name in enumerate(CLASS_NAMES):
    class_dir = TEST_DIR / class_name

    images = sorted(
        path
        for path in class_dir.iterdir()
        if (
            path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
        )
    )

    image_paths.extend(images)
    true_labels.extend([class_index] * len(images))

if not image_paths:
    raise RuntimeError("No test images found.")

# ============================================================
# PREPARE OUTPUT
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

print()
print("=" * 70)
print("HARVEST READINESS - FINAL TEST EVALUATION")
print("=" * 70)

print(f"Model       : {MODEL_PATH}")
print(f"Test folder : {TEST_DIR}")
print(f"Test images : {len(image_paths)}")
print(f"Image size  : {IMAGE_SIZE}")
print(f"Batch size  : {BATCH_SIZE}")
print(f"Device      : {DEVICE}")

print()
print("Test images per class:")

for class_name in CLASS_NAMES:
    count = sum(
        1
        for path in image_paths
        if path.parent.name == class_name
    )
    print(f"  {class_name}: {count}")

# ============================================================
# LOAD MODEL
# ============================================================

print()
print("Loading trained model...", flush=True)

model = YOLO(str(MODEL_PATH))

# ============================================================
# BATCHED PREDICTION
# ============================================================

predicted_labels = []

print()
print("Predicting test images...", flush=True)

try:
    for start in range(0, len(image_paths), BATCH_SIZE):
        batch_paths = image_paths[
            start:start + BATCH_SIZE
        ]

        print(
            f"Predicting images "
            f"{start + 1}-{start + len(batch_paths)} "
            f"of {len(image_paths)}",
            flush=True,
        )

        batch_results = model.predict(
            source=[str(path) for path in batch_paths],
            imgsz=IMAGE_SIZE,
            batch=BATCH_SIZE,
            device=DEVICE,
            verbose=False,
        )

        for result in batch_results:
            if result.probs is None:
                raise RuntimeError(
                    "Classification probabilities were not returned."
                )

            predicted_labels.append(
                int(result.probs.top1)
            )

except Exception as error:
    # Retry on CPU if the MPS inference fails.
    if DEVICE != "mps":
        raise

    print()
    print(f"MPS prediction failed: {error}")
    print("Retrying the complete evaluation on CPU...", flush=True)

    DEVICE = "cpu"
    predicted_labels = []

    for start in range(0, len(image_paths), BATCH_SIZE):
        batch_paths = image_paths[
            start:start + BATCH_SIZE
        ]

        print(
            f"CPU prediction: images "
            f"{start + 1}-{start + len(batch_paths)} "
            f"of {len(image_paths)}",
            flush=True,
        )

        batch_results = model.predict(
            source=[str(path) for path in batch_paths],
            imgsz=IMAGE_SIZE,
            batch=BATCH_SIZE,
            device="cpu",
            verbose=False,
        )

        for result in batch_results:
            if result.probs is None:
                raise RuntimeError(
                    "Classification probabilities were not returned."
                )

            predicted_labels.append(
                int(result.probs.top1)
            )

# ============================================================
# VERIFY PREDICTIONS
# ============================================================

if len(predicted_labels) != len(image_paths):
    raise RuntimeError(
        f"Expected {len(image_paths)} predictions, "
        f"received {len(predicted_labels)}."
    )

# Confirm model class order matches expected dataset class order.
model_names = model.names

if isinstance(model_names, dict):
    model_class_names = [
        model_names[index]
        for index in range(len(model_names))
    ]
else:
    model_class_names = list(model_names)

if model_class_names != CLASS_NAMES:
    raise RuntimeError(
        "Model class order does not match evaluation labels.\n"
        f"Model classes: {model_class_names}\n"
        f"Expected: {CLASS_NAMES}"
    )

# ============================================================
# CALCULATE METRICS
# ============================================================

accuracy = accuracy_score(
    true_labels,
    predicted_labels,
)

precision, recall, f1, support = (
    precision_recall_fscore_support(
        true_labels,
        predicted_labels,
        labels=[0, 1],
        zero_division=0,
    )
)

macro_precision, macro_recall, macro_f1, _ = (
    precision_recall_fscore_support(
        true_labels,
        predicted_labels,
        labels=[0, 1],
        average="macro",
        zero_division=0,
    )
)

matrix = confusion_matrix(
    true_labels,
    predicted_labels,
    labels=[0, 1],
)

report = classification_report(
    true_labels,
    predicted_labels,
    labels=[0, 1],
    target_names=CLASS_NAMES,
    zero_division=0,
    output_dict=True,
)

# ============================================================
# DISPLAY RESULTS
# ============================================================

print()
print("=" * 70)
print("FINAL TEST METRICS")
print("=" * 70)

print(
    f"Accuracy          : {accuracy:.4f} "
    f"({accuracy * 100:.2f}%)"
)
print(f"Macro Precision   : {macro_precision:.4f}")
print(f"Macro Recall      : {macro_recall:.4f}")
print(f"Macro F1-score    : {macro_f1:.4f}")

print()
print("PER-CLASS RESULTS")
print("-" * 70)

for index, class_name in enumerate(CLASS_NAMES):
    print(f"\n{class_name}")
    print(f"  Precision : {precision[index]:.4f}")
    print(f"  Recall    : {recall[index]:.4f}")
    print(f"  F1-score  : {f1[index]:.4f}")
    print(f"  Support   : {support[index]}")

print()
print("CONFUSION MATRIX")
print("-" * 70)
print("Rows = actual class; columns = predicted class")
print(f"Class order: {CLASS_NAMES}")
print(matrix)

print()
print("CLASSIFICATION REPORT")
print("-" * 70)

print(
    classification_report(
        true_labels,
        predicted_labels,
        labels=[0, 1],
        target_names=CLASS_NAMES,
        zero_division=0,
    )
)

# ============================================================
# SAVE METRICS
# ============================================================

metrics = {
    "model_path": str(MODEL_PATH),
    "test_directory": str(TEST_DIR),
    "test_image_count": len(image_paths),
    "class_names": CLASS_NAMES,
    "image_size": IMAGE_SIZE,
    "batch_size": BATCH_SIZE,
    "device_used": DEVICE,
    "accuracy": float(accuracy),
    "accuracy_percent": float(accuracy * 100),
    "macro_precision": float(macro_precision),
    "macro_recall": float(macro_recall),
    "macro_f1": float(macro_f1),
    "per_class": report,
    "confusion_matrix": matrix.tolist(),
}

metrics_path = OUTPUT_DIR / "test_metrics.json"

with open(
    metrics_path,
    "w",
    encoding="utf-8",
) as file:
    json.dump(metrics, file, indent=4)

# ============================================================
# SAVE INDIVIDUAL PREDICTIONS
# ============================================================

predictions_path = OUTPUT_DIR / "test_predictions.csv"

with open(
    predictions_path,
    "w",
    encoding="utf-8",
    newline="",
) as file:
    writer = csv.writer(file)

    writer.writerow([
        "image",
        "actual_class",
        "predicted_class",
        "correct",
    ])

    for path, actual, predicted in zip(
        image_paths,
        true_labels,
        predicted_labels,
    ):
        writer.writerow([
            path.name,
            CLASS_NAMES[actual],
            CLASS_NAMES[predicted],
            actual == predicted,
        ])

# ============================================================
# COMPLETED
# ============================================================

print()
print("=" * 70)
print("EVALUATION COMPLETED")
print("=" * 70)

print(f"Metrics saved     : {metrics_path}")
print(f"Predictions saved : {predictions_path}")
print()
