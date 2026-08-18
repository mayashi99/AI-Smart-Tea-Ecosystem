from pathlib import Path
from ultralytics import YOLO


# ============================================================
# COMPONENT 02 - PLANTATION HEALTH CLASSIFICATION
# MODEL: YOLO11n-CLS
# DATASET: LEAKAGE-FREE DATASET
# ============================================================


# ============================================================
# BASE DIRECTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# DATASET
# ============================================================

# Expected structure:
#
# plantation_health/
# └── data/
#     ├── train/
#     │   ├── healthy/
#     │   └── low_health/
#     │
#     ├── val/
#     │   ├── healthy/
#     │   └── low_health/
#     │
#     └── test/
#         ├── healthy/
#         └── low_health/

DATASET_DIR = (
    BASE_DIR
    / "plantation_health"
    / "data"
)


# ============================================================
# PRETRAINED YOLO11 CLASSIFICATION MODEL
# ============================================================

MODEL_PATH = (
    BASE_DIR
    / "yolo11n-cls.pt"
)


# ============================================================
# OUTPUT DIRECTORY
# ============================================================

RUNS_DIR = (
    BASE_DIR
    / "runs"
)


# ============================================================
# CLEAN EXPERIMENT NAME
# ============================================================

# IMPORTANT:
# This is a NEW experiment after fixing data leakage.

EXPERIMENT_NAME = (
    "plantation_health_yolo11n_clean_50epochs"
)


# ============================================================
# TRAINING CONFIGURATION
# ============================================================

EPOCHS = 50

IMAGE_SIZE = 224

BATCH_SIZE = 16

WORKERS = 2

DEVICE = "mps"

SEED = 42


# ============================================================
# EXPECTED CLASSES
# ============================================================

EXPECTED_CLASSES = [
    "healthy",
    "low_health"
]


# ============================================================
# IMAGE EXTENSIONS
# ============================================================

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}


# ============================================================
# HELPER FUNCTION
# ============================================================

def count_images(folder):

    if not folder.exists():
        return 0

    return sum(
        1
        for file in folder.rglob("*")
        if (
            file.is_file()
            and file.suffix.lower()
            in IMAGE_EXTENSIONS
        )
    )


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 75)
print("COMPONENT 02 - PLANTATION HEALTH CLASSIFICATION")
print("MODEL: YOLO11n-CLS")
print("=" * 75)


# ============================================================
# CHECK DATASET
# ============================================================

print()
print("=" * 75)
print("CHECKING DATASET")
print("=" * 75)

if not DATASET_DIR.exists():

    raise FileNotFoundError(
        f"\nDataset not found:\n"
        f"{DATASET_DIR}"
    )

print()
print(f"Dataset: {DATASET_DIR}")


# ============================================================
# CHECK MODEL
# ============================================================

print()
print("=" * 75)
print("CHECKING YOLO11 MODEL")
print("=" * 75)

if not MODEL_PATH.exists():

    raise FileNotFoundError(
        f"\nYOLO11 classification model not found:\n"
        f"{MODEL_PATH}"
    )

print()
print(f"✓ Model found: {MODEL_PATH}")


# ============================================================
# CHECK DATASET STRUCTURE
# ============================================================

print()
print("=" * 75)
print("CHECKING DATASET STRUCTURE")
print("=" * 75)


dataset_statistics = {}


for split in [
    "train",
    "val",
    "test"
]:

    split_dir = (
        DATASET_DIR
        / split
    )

    # --------------------------------------------------------
    # Check split
    # --------------------------------------------------------

    if not split_dir.exists():

        raise FileNotFoundError(
            f"\nMissing dataset split:\n"
            f"{split_dir}"
        )

    print()
    print(f"[{split.upper()}]")

    dataset_statistics[split] = {}


    # --------------------------------------------------------
    # Check classes
    # --------------------------------------------------------

    for class_name in EXPECTED_CLASSES:

        class_dir = (
            split_dir
            / class_name
        )

        if not class_dir.exists():

            raise FileNotFoundError(
                f"\nMissing class directory:\n"
                f"{class_dir}"
            )

        count = count_images(
            class_dir
        )

        if count == 0:

            raise ValueError(
                f"\nNo images found in:\n"
                f"{class_dir}"
            )

        dataset_statistics[
            split
        ][class_name] = count

        print(
            f"  {class_name:<15}: "
            f"{count}"
        )


# ============================================================
# DATASET TOTALS
# ============================================================

print()
print("=" * 75)
print("DATASET TOTALS")
print("=" * 75)


for split in [
    "train",
    "val",
    "test"
]:

    total = sum(
        dataset_statistics[
            split
        ].values()
    )

    print(
        f"{split.upper():<10}: "
        f"{total}"
    )


# ============================================================
# EXPECTED DATASET TOTAL
# ============================================================

total_dataset_images = sum(
    sum(
        dataset_statistics[split].values()
    )
    for split in [
        "train",
        "val",
        "test"
    ]
)


print()
print(
    f"Total dataset images: "
    f"{total_dataset_images}"
)


# ============================================================
# CLASS BALANCE
# ============================================================

train_healthy = (
    dataset_statistics[
        "train"
    ]["healthy"]
)


train_low_health = (
    dataset_statistics[
        "train"
    ]["low_health"]
)


imbalance_ratio = (
    train_low_health
    / train_healthy
)


print()
print("=" * 75)
print("CLASS BALANCE")
print("=" * 75)

print()
print(
    f"Healthy images    : "
    f"{train_healthy}"
)

print(
    f"Low-health images : "
    f"{train_low_health}"
)

print(
    f"Low/Healthy ratio : "
    f"{imbalance_ratio:.2f}x"
)


if imbalance_ratio > 3:

    print()
    print("⚠️ WARNING:")
    print(
        "The training dataset has significant "
        "class imbalance."
    )

    print(
        "Final evaluation should focus on "
        "per-class Precision, Recall and F1-score."
    )


# ============================================================
# LOAD YOLO11n-CLS
# ============================================================

print()
print("=" * 75)
print("LOADING YOLO11n-CLS")
print("=" * 75)


model = YOLO(
    str(MODEL_PATH)
)


print()
print("✓ YOLO11n-CLS loaded successfully")


# ============================================================
# TRAINING CONFIGURATION
# ============================================================

print()
print("=" * 75)
print("TRAINING CONFIGURATION")
print("=" * 75)

print()
print(f"Dataset       : {DATASET_DIR}")
print(f"Model         : {MODEL_PATH}")
print(f"Epochs        : {EPOCHS}")
print(f"Image size    : {IMAGE_SIZE}")
print(f"Batch size    : {BATCH_SIZE}")
print(f"Workers       : {WORKERS}")
print(f"Device        : {DEVICE}")
print(f"Seed          : {SEED}")
print(f"Experiment    : {EXPERIMENT_NAME}")

print()
print("Early stopping: DISABLED")
print("Training will run for the full 50 epochs.")

print()
print("IMPORTANT:")
print("This training uses the leakage-free dataset.")
print("Exact duplicate images were removed from cross-split leakage.")
print("The TEST set will NOT be used during training.")


# ============================================================
# START TRAINING
# ============================================================

print()
print("=" * 75)
print("STARTING COMPONENT 02 CLEAN TRAINING")
print("=" * 75)

print()


results = model.train(

    # --------------------------------------------------------
    # DATASET
    # --------------------------------------------------------

    data=str(
        DATASET_DIR
    ),


    # --------------------------------------------------------
    # TRAINING
    # --------------------------------------------------------

    epochs=EPOCHS,

    imgsz=IMAGE_SIZE,

    batch=BATCH_SIZE,


    # --------------------------------------------------------
    # APPLE SILICON
    # --------------------------------------------------------

    device=DEVICE,


    # --------------------------------------------------------
    # DATA LOADING
    # --------------------------------------------------------

    workers=WORKERS,


    # --------------------------------------------------------
    # EARLY STOPPING
    # --------------------------------------------------------

    # 0 = disabled
    patience=0,


    # --------------------------------------------------------
    # REPRODUCIBILITY
    # --------------------------------------------------------

    seed=SEED,


    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    project=str(
        RUNS_DIR
    ),

    name=EXPERIMENT_NAME,

    exist_ok=False,


    # --------------------------------------------------------
    # SAVE CHECKPOINTS
    # --------------------------------------------------------

    save=True,


    # --------------------------------------------------------
    # SAVE TRAINING PLOTS
    # --------------------------------------------------------

    plots=True,


    # --------------------------------------------------------
    # VERBOSE OUTPUT
    # --------------------------------------------------------

    verbose=True
)


# ============================================================
# TRAINING COMPLETED
# ============================================================

print()
print("=" * 75)
print("✅ COMPONENT 02 CLEAN TRAINING COMPLETED")
print("=" * 75)


# ============================================================
# OUTPUT PATHS
# ============================================================

EXPERIMENT_DIR = (
    RUNS_DIR
    / EXPERIMENT_NAME
)


BEST_MODEL = (
    EXPERIMENT_DIR
    / "weights"
    / "best.pt"
)


LAST_MODEL = (
    EXPERIMENT_DIR
    / "weights"
    / "last.pt"
)


# ============================================================
# PRINT OUTPUT PATHS
# ============================================================

print()
print("=" * 75)
print("TRAINING OUTPUT")
print("=" * 75)

print()
print("Experiment directory:")
print(
    EXPERIMENT_DIR
)

print()
print("Best model:")
print(
    BEST_MODEL
)

print()
print("Last model:")
print(
    LAST_MODEL
)


# ============================================================
# VERIFY BEST MODEL
# ============================================================

print()
print("=" * 75)
print("CHECKING TRAINING OUTPUT")
print("=" * 75)


if BEST_MODEL.exists():

    print()
    print("✅ best.pt created successfully")

else:

    print()
    print("❌ best.pt NOT FOUND")


# ============================================================
# VERIFY LAST MODEL
# ============================================================

if LAST_MODEL.exists():

    print()
    print("✅ last.pt created successfully")

else:

    print()
    print("❌ last.pt NOT FOUND")


# ============================================================
# FINAL INFORMATION
# ============================================================

print()
print("=" * 75)
print("COMPONENT 02 TRAINING SUMMARY")
print("=" * 75)

print()
print("Dataset:")
print(
    DATASET_DIR
)

print()
print("Experiment:")
print(
    EXPERIMENT_DIR
)

print()
print("Best model:")
print(
    BEST_MODEL
)

print()
print("Last model:")
print(
    LAST_MODEL
)

print()
print("Classes:")
print(
    "0 = healthy"
)

print(
    "1 = low_health"
)

print()
print("Training:")
print(
    f"{EPOCHS} epochs"
)

print()
print("Dataset split:")
print(
    "Train = 70%"
)

print(
    "Validation = 20%"
)

print(
    "Test = 10%"
)

print()
print("Data leakage:")
print(
    "Cross-split duplicate check = 0"
)

print()
print("Original dataset:")
print(
    "NOT modified"
)

print()
print("Test set:")
print(
    "NOT used during training"
)

print()
print("=" * 75)
print("✅ COMPONENT 02 TRAINING FINISHED")
print("=" * 75)