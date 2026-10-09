from pathlib import Path
import hashlib

# ============================================================
# HARVEST READINESS - SPLIT DATA LEAKAGE CHECK
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

SPLITS = {
    "train": DATA_DIR / "train",
    "val": DATA_DIR / "val",
    "test": DATA_DIR / "test",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}


def calculate_hash(file_path):
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha256.update(chunk)

    return sha256.hexdigest()


def collect_images(split_dir):

    images = []

    for class_dir in split_dir.iterdir():

        if not class_dir.is_dir():
            continue

        for file in class_dir.iterdir():

            if (
                file.is_file()
                and file.suffix.lower() in IMAGE_EXTENSIONS
            ):
                images.append(file)

    return images


print()
print("=" * 70)
print("HARVEST READINESS - DATA LEAKAGE CHECK")
print("=" * 70)
print()

hashes = {}

# ============================================================
# COLLECT HASHES
# ============================================================

for split_name, split_dir in SPLITS.items():

    images = collect_images(split_dir)

    print(f"{split_name.upper()} images : {len(images)}")

    split_hashes = {}

    for image in images:

        image_hash = calculate_hash(image)

        split_hashes[image_hash] = str(image)

    hashes[split_name] = split_hashes

print()

# ============================================================
# CHECK OVERLAP
# ============================================================

train_hashes = set(hashes["train"])
val_hashes = set(hashes["val"])
test_hashes = set(hashes["test"])

train_val = train_hashes & val_hashes
train_test = train_hashes & test_hashes
val_test = val_hashes & test_hashes

print("=" * 70)
print("CROSS-SPLIT DUPLICATE CHECK")
print("=" * 70)
print()

print(
    f"Train ↔ Validation duplicates : {len(train_val)}"
)

print(
    f"Train ↔ Test duplicates        : {len(train_test)}"
)

print(
    f"Validation ↔ Test duplicates   : {len(val_test)}"
)

print()

# ============================================================
# RESULT
# ============================================================

if (
    len(train_val) == 0
    and len(train_test) == 0
    and len(val_test) == 0
):

    print("=" * 70)
    print("✅ NO CROSS-SPLIT DATA LEAKAGE FOUND")
    print("=" * 70)

else:

    print("=" * 70)
    print("❌ DATA LEAKAGE DETECTED")
    print("=" * 70)

    if train_val:
        print()
        print("Train ↔ Validation duplicates:")

        for image_hash in train_val:
            print(hashes["train"][image_hash])
            print(hashes["val"][image_hash])

    if train_test:
        print()
        print("Train ↔ Test duplicates:")

        for image_hash in train_test:
            print(hashes["train"][image_hash])
            print(hashes["test"][image_hash])

    if val_test:
        print()
        print("Validation ↔ Test duplicates:")

        for image_hash in val_test:
            print(hashes["val"][image_hash])
            print(hashes["test"][image_hash])

print()