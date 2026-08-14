from pathlib import Path
from ultralytics import YOLO


# ============================================================
# COMPONENT 02 - PLANTATION HEALTH CLASSIFICATION
# MODEL: YOLO11n-CLS
# ============================================================

# Current Component02 directory
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

DATASET_DIR = BASE_DIR / "plantation_health" / "data"


# ============================================================
# PRETRAINED YOLO11 CLASSIFICATION MODEL
# ============================================================

MODEL_PATH = BASE_DIR / "yolo11n-cls.pt"


# ============================================================
# COMPONENT 02 ONLY OUTPUT DIRECTORY
# ============================================================

RUNS_DIR = BASE_DIR / "runs"


# ============================================================
# EXPERIMENT NAME
# ============================================================

# Keep this separate from the previous 20-epoch experiment.
EXPERIMENT_NAME = "plantation_health_yolo11n_50epochs"


# ============================================================
# TRAINING CONFIGURATION
# ============================================================

EPOCHS = 50
IMAGE_SIZE = 224
BATCH_SIZE = 16
WORKERS = 2

# Apple Silicon MacBook
DEVICE = "mps"


# ============================================================
# CHECK REQUIRED PATHS
# ============================================================

print("=" * 70)
print("COMPONENT 02 - PLANTATION HEALTH CLASSIFICATION")
print("=" * 70)

print()
print("Checking dataset...")

if not DATASET_DIR.exists():
    raise FileNotFoundError(
        f"\nDataset not found:\n{DATASET_DIR}"
    )

print(f"Dataset: {DATASET_DIR}")


print()
print("Checking YOLO11 model...")

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"\nYOLO11 classification model not found:\n{MODEL_PATH}"
    )

print(f"Model: {MODEL_PATH}")


# ============================================================
# CHECK DATASET SPLITS
# ============================================================

for split in ["train", "val", "test"]:

    split_dir = DATASET_DIR / split

    if not split_dir.exists():
        raise FileNotFoundError(
            f"\nMissing dataset split:\n{split_dir}"
        )

    print(f"✓ {split} folder found")


# ============================================================
# LOAD PRETRAINED YOLO11 CLASSIFICATION MODEL
# ============================================================

print()
print("=" * 70)
print("Loading YOLO11 Classification Model")
print("=" * 70)

model = YOLO(str(MODEL_PATH))

print("✓ YOLO11 model loaded successfully")


# ============================================================
# TRAINING INFORMATION
# ============================================================

print()
print("=" * 70)
print("TRAINING CONFIGURATION")
print("=" * 70)

print(f"Dataset       : {DATASET_DIR}")
print(f"Model         : {MODEL_PATH}")
print(f"Epochs        : {EPOCHS}")
print(f"Image size    : {IMAGE_SIZE}")
print(f"Batch size    : {BATCH_SIZE}")
print(f"Device        : {DEVICE}")
print(f"Workers       : {WORKERS}")
print(f"Experiment    : {EXPERIMENT_NAME}")

print()
print("Early stopping: DISABLED")
print("Training will run for the full 50 epochs.")


# ============================================================
# START TRAINING
# ============================================================

print()
print("=" * 70)
print("STARTING COMPONENT 02 TRAINING")
print("=" * 70)


results = model.train(

    # Dataset
    data=str(DATASET_DIR),

    # Training
    epochs=EPOCHS,
    imgsz=IMAGE_SIZE,
    batch=BATCH_SIZE,

    # Apple Silicon GPU
    device=DEVICE,

    # Data loading
    workers=WORKERS,

    # --------------------------------------------------------
    # IMPORTANT
    # patience=0 disables EarlyStopping.
    # Therefore all 50 epochs will run.
    # --------------------------------------------------------
    patience=0,

    # --------------------------------------------------------
    # Reproducibility
    # --------------------------------------------------------
    seed=42,

    # --------------------------------------------------------
    # Save results inside Component02 only
    # --------------------------------------------------------
    project=str(RUNS_DIR),
    name=EXPERIMENT_NAME,

    # Save checkpoints
    save=True,

    # Do not overwrite existing experiment
    exist_ok=False,

    # Show detailed training information
    verbose=True,
)


# ============================================================
# TRAINING COMPLETED
# ============================================================

print()
print("=" * 70)
print("✅ COMPONENT 02 TRAINING COMPLETED")
print("=" * 70)


# ============================================================
# OUTPUT PATHS
# ============================================================

EXPERIMENT_DIR = RUNS_DIR / EXPERIMENT_NAME
BEST_MODEL = EXPERIMENT_DIR / "weights" / "best.pt"
LAST_MODEL = EXPERIMENT_DIR / "weights" / "last.pt"


print()
print("Training output:")
print(EXPERIMENT_DIR)


print()
print("Best model:")
print(BEST_MODEL)


print()
print("Last model:")
print(LAST_MODEL)


# ============================================================
# VERIFY OUTPUT
# ============================================================

print()

if BEST_MODEL.exists():
    print("✅ best.pt created successfully")
else:
    print("⚠️ best.pt was not found")


if LAST_MODEL.exists():
    print("✅ last.pt created successfully")
else:
    print("⚠️ last.pt was not found")


print()
print("=" * 70)
print("COMPONENT 02 TRAINING FINISHED")
print("=" * 70)