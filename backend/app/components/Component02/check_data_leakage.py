from pathlib import Path
import hashlib


# ============================================================
# COMPONENT 02 - DATA LEAKAGE CHECK
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATASET_DIR = (
    BASE_DIR
    / "plantation_health"
    / "data"
)

SPLITS = ["train", "val", "test"]

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}


# ============================================================
# HASH FUNCTION
# ============================================================

def calculate_hash(file_path):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


# ============================================================
# COLLECT IMAGES
# ============================================================

split_hashes = {}

total_images = 0


print()
print("=" * 75)
print("COMPONENT 02 - DATA LEAKAGE CHECK")
print("=" * 75)


for split in SPLITS:

    split_dir = DATASET_DIR / split

    if not split_dir.exists():

        raise FileNotFoundError(
            f"Split not found:\n{split_dir}"
        )

    split_hashes[split] = {}

    print()
    print(f"Scanning {split}...")

    for class_dir in split_dir.iterdir():

        if not class_dir.is_dir():
            continue

        for image_path in class_dir.iterdir():

            if (
                not image_path.is_file()
                or image_path.suffix.lower()
                not in IMAGE_EXTENSIONS
            ):
                continue

            file_hash = calculate_hash(
                image_path
            )

            split_hashes[split][file_hash] = (
                image_path
            )

            total_images += 1

    print(
        f"{split}: "
        f"{len(split_hashes[split])} images"
    )


# ============================================================
# CHECK CROSS-SPLIT DUPLICATES
# ============================================================

print()
print("=" * 75)
print("CHECKING CROSS-SPLIT DUPLICATES")
print("=" * 75)


duplicates_found = []


for split_a_index in range(len(SPLITS)):

    split_a = SPLITS[split_a_index]

    for split_b_index in range(
        split_a_index + 1,
        len(SPLITS)
    ):

        split_b = SPLITS[split_b_index]

        hashes_a = set(
            split_hashes[split_a].keys()
        )

        hashes_b = set(
            split_hashes[split_b].keys()
        )

        common_hashes = (
            hashes_a.intersection(hashes_b)
        )

        print()
        print(
            f"{split_a} vs {split_b}"
        )

        print(
            f"Duplicate images: "
            f"{len(common_hashes)}"
        )

        for file_hash in common_hashes:

            duplicates_found.append(
                {
                    "split_a": split_a,
                    "image_a": str(
                        split_hashes[
                            split_a
                        ][file_hash]
                    ),
                    "split_b": split_b,
                    "image_b": str(
                        split_hashes[
                            split_b
                        ][file_hash]
                    )
                }
            )


# ============================================================
# FINAL RESULT
# ============================================================

print()
print("=" * 75)
print("FINAL DATA LEAKAGE RESULT")
print("=" * 75)

print()
print(
    f"Total images checked: "
    f"{total_images}"
)

print(
    f"Cross-split duplicates: "
    f"{len(duplicates_found)}"
)


if len(duplicates_found) == 0:

    print()
    print(
        "✅ NO EXACT DUPLICATE IMAGES "
        "FOUND BETWEEN TRAIN / VAL / TEST"
    )

else:

    print()
    print(
        "⚠️ DATA LEAKAGE DETECTED!"
    )

    print()

    for item in duplicates_found:

        print(
            f"{item['split_a']}:"
        )

        print(
            f"  {item['image_a']}"
        )

        print(
            f"{item['split_b']}:"
        )

        print(
            f"  {item['image_b']}"
        )

        print()


# ============================================================
# COMPLETED
# ============================================================

print()
print("=" * 75)
print("DATA LEAKAGE CHECK COMPLETED")
print("=" * 75)