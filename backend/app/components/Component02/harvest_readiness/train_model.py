from pathlib import Path
import torch
from ultralytics import YOLO

# ============================================================
# HARVEST READINESS - YOLO11 CLASSIFICATION TRAINING
# FULL 50 EPOCHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

TRAIN_DIR = DATA_DIR / "train"
VAL_DIR = DATA_DIR / "val"

RUNS_DIR = BASE_DIR / "runs"

# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "yolo11n-cls.pt"

IMAGE_SIZE = 224
EPOCHS = 50
BATCH_SIZE = 32

RANDOM_SEED = 42

# ============================================================
# DEVICE
# ============================================================

if torch.backends.mps.is_available():
    DEVICE = "mps"

elif torch.cuda.is_available():
    DEVICE = 0

else:
    DEVICE = "cpu"

# ============================================================
# CHECK DATASET
# ============================================================

if not TRAIN_DIR.exists():
    raise FileNotFoundError(
        f"Training directory not found:\n{TRAIN_DIR}"
    )

if not VAL_DIR.exists():
    raise FileNotFoundError(
        f"Validation directory not found:\n{VAL_DIR}"
    )

# ============================================================
# DISPLAY CONFIGURATION
# ============================================================

print()

print("=" * 70)
print("HARVEST READINESS - YOLO11 CLASSIFICATION")
print("FULL 50 EPOCH TRAINING")
print("=" * 70)

print()

print("Dataset")
print("-" * 70)

print(f"Train      : {TRAIN_DIR}")
print(f"Validation : {VAL_DIR}")

print()

print("Model Configuration")
print("-" * 70)

print(f"Model      : {MODEL_NAME}")
print(f"Image size : {IMAGE_SIZE}")
print(f"Epochs     : {EPOCHS}")
print(f"Batch size : {BATCH_SIZE}")
print(f"Seed       : {RANDOM_SEED}")
print(f"Device     : {DEVICE}")

print()

print("Classes")
print("-" * 70)

print("0 : Harvest_Not_Ready")
print("1 : Harvest_Ready")

print()

print("Early Stopping")
print("-" * 70)

print("Disabled")
print("Training will run for all 50 epochs.")

print()

# ============================================================
# LOAD MODEL
# ============================================================

print("=" * 70)
print("LOADING MODEL")
print("=" * 70)

print()

model = YOLO(MODEL_NAME)

print("✅ Model loaded")

print()

# ============================================================
# TRAIN
# ============================================================

print("=" * 70)
print("STARTING TRAINING")
print("=" * 70)

print()

results = model.train(

    # --------------------------------------------------------
    # DATASET
    # --------------------------------------------------------

    data=str(DATA_DIR),

    # --------------------------------------------------------
    # TRAINING
    # --------------------------------------------------------

    epochs=EPOCHS,

    imgsz=IMAGE_SIZE,

    batch=BATCH_SIZE,

    device=DEVICE,

    seed=RANDOM_SEED,

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    project=str(RUNS_DIR),

    name="harvest_readiness_yolo11n_50epochs",

    # --------------------------------------------------------
    # PERFORMANCE
    # --------------------------------------------------------

    workers=4,

    # --------------------------------------------------------
    # EARLY STOPPING DISABLED
    # --------------------------------------------------------

    patience=0,

    # --------------------------------------------------------
    # VERBOSE OUTPUT
    # --------------------------------------------------------

    verbose=True
)

# ============================================================
# COMPLETED
# ============================================================

print()

print("=" * 70)
print("✅ TRAINING COMPLETED")
print("=" * 70)

print()

RESULTS_DIR = (
    RUNS_DIR
    / "harvest_readiness_yolo11n_50epochs"
)

print(
    "Training results saved to:"
)

print(
    RESULTS_DIR
)

print()

# ============================================================
# MODEL PATHS
# ============================================================

BEST_MODEL = (
    RESULTS_DIR
    / "weights"
    / "best.pt"
)

LAST_MODEL = (
    RESULTS_DIR
    / "weights"
    / "last.pt"
)

print("Best model:")
print(BEST_MODEL)

print()

print("Last epoch model:")
print(LAST_MODEL)

print()

print("=" * 70)
print("50 EPOCH TRAINING FINISHED")
print("=" * 70)

print()