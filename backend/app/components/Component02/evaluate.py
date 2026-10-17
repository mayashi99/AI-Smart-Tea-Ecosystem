from pathlib import Path
import csv
import json

from ultralytics import YOLO


# ============================================================
# COMPONENT 02 - PLANTATION HEALTH
# FULL MODEL EVALUATION
# MODEL: YOLO11n-CLS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# DATASET
# ============================================================

DATASET_DIR = (
    BASE_DIR
    / "plantation_health"
    / "data"
)

TEST_DIR = DATASET_DIR / "test"


# ============================================================
# NEW UPDATED TRAINED MODEL
# ============================================================

# IMPORTANT:
# This is the NEW model trained after adding the
# additional Low Health images and re-training the dataset.
#
# Experiment:
# plantation_health_yolo11n_updated_50epochs_v2

EXPERIMENT_NAME = "plantation_health_yolo11n_updated_50epochs_v2"

MODEL_PATH = (
    BASE_DIR
    / "runs"
    / EXPERIMENT_NAME
    / "weights"
    / "best.pt"
)


# ============================================================
# EVALUATION OUTPUT DIRECTORY
# ============================================================

EVALUATION_DIR = (
    BASE_DIR
    / "runs"
    / EXPERIMENT_NAME
    / "evaluation"
)

EVALUATION_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# SETTINGS
# ============================================================

IMAGE_SIZE = 224

# Apple Silicon MacBook
DEVICE = "mps"

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 75)
print("COMPONENT 02 - PLANTATION HEALTH MODEL EVALUATION")
print("=" * 75)

print()
print("Evaluation configuration:")
print("-" * 75)
print("Model       : YOLO11n-CLS")
print(f"Experiment  : {EXPERIMENT_NAME}")
print("Dataset     : Plantation Health")
print("Test split  : 10%")
print(f"Image size  : {IMAGE_SIZE}")
print(f"Device      : {DEVICE}")
print("-" * 75)


# ============================================================
# CHECK MODEL
# ============================================================

print()
print("Checking trained model...")

if not MODEL_PATH.exists():

    raise FileNotFoundError(
        f"""
Trained model not found:

{MODEL_PATH}

Please make sure the NEW 50-epoch training
was completed successfully and best.pt exists.
"""
    )

print("✓ NEW best.pt found")
print(f"Model: {MODEL_PATH}")


# ============================================================
# CHECK DATASET
# ============================================================

print()
print("Checking test dataset...")

if not TEST_DIR.exists():

    raise FileNotFoundError(
        f"""
Test dataset not found:

{TEST_DIR}
"""
    )


# ============================================================
# CHECK CLASS FOLDERS
# ============================================================

healthy_dir = TEST_DIR / "healthy"
low_health_dir = TEST_DIR / "low_health"


if not healthy_dir.exists():

    raise FileNotFoundError(
        f"""
Healthy test folder not found:

{healthy_dir}
"""
    )


if not low_health_dir.exists():

    raise FileNotFoundError(
        f"""
Low-health test folder not found:

{low_health_dir}
"""
    )


# ============================================================
# GET TEST IMAGES
# ============================================================

healthy_images = sorted(
    [
        p
        for p in healthy_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
)


low_health_images = sorted(
    [
        p
        for p in low_health_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
)


# ============================================================
# TEST DATASET INFORMATION
# ============================================================

print()
print("=" * 75)
print("TEST DATASET")
print("=" * 75)

print()
print(f"Healthy images    : {len(healthy_images)}")
print(f"Low-health images : {len(low_health_images)}")

total_images = (
    len(healthy_images)
    + len(low_health_images)
)

print(f"Total test images : {total_images}")


# ============================================================
# LOAD MODEL
# ============================================================

print()
print("=" * 75)
print("LOADING NEW MODEL")
print("=" * 75)

model = YOLO(str(MODEL_PATH))

print()
print("✓ YOLO11 classification model loaded")
print(f"Model classes: {model.names}")


# ============================================================
# CLASS DEFINITIONS
# ============================================================

CLASS_NAMES = {
    0: "healthy",
    1: "low_health"
}


# ============================================================
# PREPARE IMAGE LIST
# ============================================================

all_images = []


# ------------------------------------------------------------
# Healthy = class 0
# ------------------------------------------------------------

for image_path in healthy_images:

    all_images.append(
        {
            "path": image_path,
            "actual": 0
        }
    )


# ------------------------------------------------------------
# Low Health = class 1
# ------------------------------------------------------------

for image_path in low_health_images:

    all_images.append(
        {
            "path": image_path,
            "actual": 1
        }
    )


# ============================================================
# CONFUSION MATRIX VARIABLES
# ============================================================

#                    Predicted
#
#                 Healthy   Low Health
#
# Actual Healthy      0          0
# Actual Low          0          0


true_healthy_pred_healthy = 0
true_healthy_pred_low = 0

true_low_pred_healthy = 0
true_low_pred_low = 0


# ============================================================
# BASIC COUNTERS
# ============================================================

correct = 0
wrong = 0

wrong_predictions = []


# ============================================================
# START EVALUATION
# ============================================================

print()
print("=" * 75)
print("RUNNING TEST DATASET EVALUATION")
print("=" * 75)

print()
print(f"Model being evaluated:")
print(MODEL_PATH)

print()
print(f"Total images to evaluate: {total_images}")
print()


# ============================================================
# PREDICTION
# ============================================================

for index, item in enumerate(
    all_images,
    start=1
):

    image_path = item["path"]
    actual_class = item["actual"]


    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    results = model.predict(
        source=str(image_path),
        imgsz=IMAGE_SIZE,
        device=DEVICE,
        verbose=False
    )

    result = results[0]


    # --------------------------------------------------------
    # Get predicted class
    # --------------------------------------------------------

    predicted_class = int(
        result.probs.top1
    )


    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    confidence = float(
        result.probs.top1conf
    )


    # --------------------------------------------------------
    # Correct / Wrong
    # --------------------------------------------------------

    if predicted_class == actual_class:

        correct += 1

    else:

        wrong += 1

        wrong_predictions.append(
            {
                "image": image_path.name,
                "image_path": str(image_path),
                "actual_class": CLASS_NAMES[actual_class],
                "predicted_class": CLASS_NAMES[predicted_class],
                "confidence": round(
                    confidence,
                    6
                )
            }
        )


    # --------------------------------------------------------
    # Confusion Matrix
    # --------------------------------------------------------

    if actual_class == 0:

        if predicted_class == 0:

            true_healthy_pred_healthy += 1

        else:

            true_healthy_pred_low += 1


    elif actual_class == 1:

        if predicted_class == 0:

            true_low_pred_healthy += 1

        else:

            true_low_pred_low += 1


    # --------------------------------------------------------
    # Progress
    # --------------------------------------------------------

    if (
        index % 25 == 0
        or index == total_images
    ):

        print(
            f"Processed "
            f"{index}/{total_images}"
        )


# ============================================================
# BASIC METRICS
# ============================================================

accuracy = (
    correct / total_images
    if total_images > 0
    else 0
)


# ============================================================
# HEALTHY METRICS
# ============================================================

healthy_tp = (
    true_healthy_pred_healthy
)

healthy_fp = (
    true_low_pred_healthy
)

healthy_fn = (
    true_healthy_pred_low
)


healthy_precision = (

    healthy_tp
    /
    (healthy_tp + healthy_fp)

    if (healthy_tp + healthy_fp) > 0
    else 0
)


healthy_recall = (

    healthy_tp
    /
    (healthy_tp + healthy_fn)

    if (healthy_tp + healthy_fn) > 0
    else 0
)


healthy_f1 = (

    2
    * healthy_precision
    * healthy_recall
    /
    (healthy_precision + healthy_recall)

    if (healthy_precision + healthy_recall) > 0
    else 0
)


# ============================================================
# LOW HEALTH METRICS
# ============================================================

low_tp = (
    true_low_pred_low
)

low_fp = (
    true_healthy_pred_low
)

low_fn = (
    true_low_pred_healthy
)


low_precision = (

    low_tp
    /
    (low_tp + low_fp)

    if (low_tp + low_fp) > 0
    else 0
)


low_recall = (

    low_tp
    /
    (low_tp + low_fn)

    if (low_tp + low_fn) > 0
    else 0
)


low_f1 = (

    2
    * low_precision
    * low_recall
    /
    (low_precision + low_recall)

    if (low_precision + low_recall) > 0
    else 0
)


# ============================================================
# MACRO AVERAGE
# ============================================================

macro_precision = (
    healthy_precision
    + low_precision
) / 2


macro_recall = (
    healthy_recall
    + low_recall
) / 2


macro_f1 = (
    healthy_f1
    + low_f1
) / 2


# ============================================================
# WEIGHTED AVERAGE
# ============================================================

healthy_support = len(
    healthy_images
)

low_support = len(
    low_health_images
)


if total_images > 0:

    weighted_precision = (

        (
            healthy_precision
            * healthy_support
        )

        +

        (
            low_precision
            * low_support
        )

    ) / total_images


    weighted_recall = (

        (
            healthy_recall
            * healthy_support
        )

        +

        (
            low_recall
            * low_support
        )

    ) / total_images


    weighted_f1 = (

        (
            healthy_f1
            * healthy_support
        )

        +

        (
            low_f1
            * low_support
        )

    ) / total_images

else:

    weighted_precision = 0
    weighted_recall = 0
    weighted_f1 = 0


# ============================================================
# FINAL TEST RESULTS
# ============================================================

print()
print("=" * 75)
print("FINAL TEST SET RESULTS")
print("=" * 75)

print()

print(
    f"Total Test Images : {total_images}"
)

print(
    f"Correct           : {correct}"
)

print(
    f"Wrong             : {wrong}"
)

print(
    f"Accuracy          : "
    f"{accuracy * 100:.2f}%"
)


# ============================================================
# CLASSIFICATION METRICS
# ============================================================

print()
print("=" * 75)
print("CLASSIFICATION METRICS")
print("=" * 75)


# ------------------------------------------------------------
# Healthy
# ------------------------------------------------------------

print()
print("Healthy")
print("-" * 40)

print(
    f"Precision : "
    f"{healthy_precision * 100:.2f}%"
)

print(
    f"Recall    : "
    f"{healthy_recall * 100:.2f}%"
)

print(
    f"F1-Score  : "
    f"{healthy_f1 * 100:.2f}%"
)

print(
    f"Support   : "
    f"{healthy_support}"
)


# ------------------------------------------------------------
# Low Health
# ------------------------------------------------------------

print()
print("Low Health")
print("-" * 40)

print(
    f"Precision : "
    f"{low_precision * 100:.2f}%"
)

print(
    f"Recall    : "
    f"{low_recall * 100:.2f}%"
)

print(
    f"F1-Score  : "
    f"{low_f1 * 100:.2f}%"
)

print(
    f"Support   : "
    f"{low_support}"
)


# ------------------------------------------------------------
# Macro Average
# ------------------------------------------------------------

print()
print("Macro Average")
print("-" * 40)

print(
    f"Precision : "
    f"{macro_precision * 100:.2f}%"
)

print(
    f"Recall    : "
    f"{macro_recall * 100:.2f}%"
)

print(
    f"F1-Score  : "
    f"{macro_f1 * 100:.2f}%"
)


# ------------------------------------------------------------
# Weighted Average
# ------------------------------------------------------------

print()
print("Weighted Average")
print("-" * 40)

print(
    f"Precision : "
    f"{weighted_precision * 100:.2f}%"
)

print(
    f"Recall    : "
    f"{weighted_recall * 100:.2f}%"
)

print(
    f"F1-Score  : "
    f"{weighted_f1 * 100:.2f}%"
)


# ============================================================
# CONFUSION MATRIX
# ============================================================

print()
print("=" * 75)
print("CONFUSION MATRIX")
print("=" * 75)

print()

print(
    "                    Predicted"
)

print(
    "                 Healthy   Low Health"
)

print(
    f"Actual Healthy   "
    f"{true_healthy_pred_healthy:^8}   "
    f"{true_healthy_pred_low:^10}"
)

print(
    f"Actual Low Health"
    f" {true_low_pred_healthy:^8}   "
    f"{true_low_pred_low:^10}"
)


# ============================================================
# WRONG PREDICTIONS
# ============================================================

print()
print("=" * 75)
print("WRONG PREDICTIONS")
print("=" * 75)


if len(wrong_predictions) == 0:

    print()
    print("✓ No wrong predictions found.")

else:

    print()
    print(
        f"Total wrong predictions: "
        f"{len(wrong_predictions)}"
    )

    for item in wrong_predictions:

        print()

        print(
            f"Image      : "
            f"{item['image']}"
        )

        print(
            f"Actual     : "
            f"{item['actual_class']}"
        )

        print(
            f"Predicted  : "
            f"{item['predicted_class']}"
        )

        print(
            f"Confidence : "
            f"{item['confidence'] * 100:.2f}%"
        )


# ============================================================
# SAVE METRICS JSON
# ============================================================

metrics = {

    "component": "Component 02",

    "model_name": "YOLO11n-CLS",

    "experiment": EXPERIMENT_NAME,

    "model": str(MODEL_PATH),

    "dataset": str(TEST_DIR),

    "image_size": IMAGE_SIZE,

    "device": DEVICE,

    "total_test_images": total_images,

    "correct": correct,

    "wrong": wrong,

    "accuracy": accuracy,

    "classes": {

        "healthy": {

            "precision": healthy_precision,

            "recall": healthy_recall,

            "f1_score": healthy_f1,

            "support": healthy_support

        },

        "low_health": {

            "precision": low_precision,

            "recall": low_recall,

            "f1_score": low_f1,

            "support": low_support

        }

    },

    "macro_average": {

        "precision": macro_precision,

        "recall": macro_recall,

        "f1_score": macro_f1

    },

    "weighted_average": {

        "precision": weighted_precision,

        "recall": weighted_recall,

        "f1_score": weighted_f1

    },

    "confusion_matrix": [

        [
            true_healthy_pred_healthy,
            true_healthy_pred_low
        ],

        [
            true_low_pred_healthy,
            true_low_pred_low
        ]

    ]

}


# ============================================================
# SAVE METRICS JSON
# ============================================================

METRICS_FILE = (
    EVALUATION_DIR
    / "evaluation_metrics.json"
)


with open(
    METRICS_FILE,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        metrics,
        file,
        indent=4
    )


# ============================================================
# SAVE WRONG PREDICTIONS CSV
# ============================================================

WRONG_CSV = (
    EVALUATION_DIR
    / "wrong_predictions.csv"
)


with open(
    WRONG_CSV,
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.DictWriter(

        file,

        fieldnames=[
            "image",
            "image_path",
            "actual_class",
            "predicted_class",
            "confidence"
        ]
    )

    writer.writeheader()

    writer.writerows(
        wrong_predictions
    )


# ============================================================
# SAVE TEXT REPORT
# ============================================================

REPORT_FILE = (
    EVALUATION_DIR
    / "evaluation_report.txt"
)


with open(
    REPORT_FILE,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        "COMPONENT 02 - PLANTATION HEALTH\n"
    )

    file.write(
        "YOLO11n-CLS MODEL EVALUATION\n"
    )

    file.write(
        "=" * 70
        + "\n\n"
    )

    file.write(
        f"Experiment: "
        f"{EXPERIMENT_NAME}\n"
    )

    file.write(
        f"Model: {MODEL_PATH}\n"
    )

    file.write(
        f"Test Dataset: {TEST_DIR}\n"
    )

    file.write(
        f"Image Size: {IMAGE_SIZE}\n"
    )

    file.write(
        f"Device: {DEVICE}\n\n"
    )

    file.write(
        f"Total Test Images: {total_images}\n"
    )

    file.write(
        f"Correct: {correct}\n"
    )

    file.write(
        f"Wrong: {wrong}\n"
    )

    file.write(
        f"Accuracy: "
        f"{accuracy * 100:.2f}%\n\n"
    )


    file.write(
        "Healthy\n"
    )

    file.write(
        f"Precision: "
        f"{healthy_precision * 100:.2f}%\n"
    )

    file.write(
        f"Recall: "
        f"{healthy_recall * 100:.2f}%\n"
    )

    file.write(
        f"F1-Score: "
        f"{healthy_f1 * 100:.2f}%\n"
    )

    file.write(
        f"Support: "
        f"{healthy_support}\n\n"
    )


    file.write(
        "Low Health\n"
    )

    file.write(
        f"Precision: "
        f"{low_precision * 100:.2f}%\n"
    )

    file.write(
        f"Recall: "
        f"{low_recall * 100:.2f}%\n"
    )

    file.write(
        f"F1-Score: "
        f"{low_f1 * 100:.2f}%\n"
    )

    file.write(
        f"Support: "
        f"{low_support}\n\n"
    )


    file.write(
        "Macro Average\n"
    )

    file.write(
        f"Precision: "
        f"{macro_precision * 100:.2f}%\n"
    )

    file.write(
        f"Recall: "
        f"{macro_recall * 100:.2f}%\n"
    )

    file.write(
        f"F1-Score: "
        f"{macro_f1 * 100:.2f}%\n\n"
    )


    file.write(
        "Weighted Average\n"
    )

    file.write(
        f"Precision: "
        f"{weighted_precision * 100:.2f}%\n"
    )

    file.write(
        f"Recall: "
        f"{weighted_recall * 100:.2f}%\n"
    )

    file.write(
        f"F1-Score: "
        f"{weighted_f1 * 100:.2f}%\n\n"
    )


    file.write(
        "Confusion Matrix\n"
    )

    file.write(
        f"Healthy -> Healthy: "
        f"{true_healthy_pred_healthy}\n"
    )

    file.write(
        f"Healthy -> Low Health: "
        f"{true_healthy_pred_low}\n"
    )

    file.write(
        f"Low Health -> Healthy: "
        f"{true_low_pred_healthy}\n"
    )

    file.write(
        f"Low Health -> Low Health: "
        f"{true_low_pred_low}\n"
    )


# ============================================================
# FINAL OUTPUT
# ============================================================

print()
print("=" * 75)
print("EVALUATION FILES SAVED")
print("=" * 75)

print()

print(
    f"Evaluation folder:\n"
    f"{EVALUATION_DIR}"
)

print()

print(
    f"Metrics JSON:\n"
    f"{METRICS_FILE}"
)

print()

print(
    f"Wrong predictions CSV:\n"
    f"{WRONG_CSV}"
)

print()

print(
    f"Text report:\n"
    f"{REPORT_FILE}"
)


# ============================================================
# COMPLETED
# ============================================================

print()
print("=" * 75)
print("✅ COMPONENT 02 NEW MODEL EVALUATION COMPLETED")
print("=" * 75)

print()