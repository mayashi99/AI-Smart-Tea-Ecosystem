from pathlib import Path
import hashlib


# ============================================================
# HARVEST READINESS - EXACT DUPLICATE CHECK
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data" / "original"

READY_DIR = DATA_DIR / "Harvest_Ready"
NOT_READY_DIR = DATA_DIR / "Harvest_Not_Ready"


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}


# ============================================================
# HASH FUNCTION
# ============================================================

def get_file_hash(file_path):
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

def collect_images(folder):

    return [
        file
        for file in sorted(folder.iterdir())
        if (
            file.is_file()
            and file.suffix.lower() in IMAGE_EXTENSIONS
        )
    ]


# ============================================================
# MAIN
# ============================================================

print()
print("=" * 70)
print("HARVEST READINESS - DUPLICATE CHECK")
print("=" * 70)

print()

print(f"Ready folder     : {READY_DIR}")
print(f"Not Ready folder : {NOT_READY_DIR}")


# Check folders

if not READY_DIR.exists():
    raise FileNotFoundError(
        f"Folder not found: {READY_DIR}"
    )

if not NOT_READY_DIR.exists():
    raise FileNotFoundError(
        f"Folder not found: {NOT_READY_DIR}"
    )


# Collect images

ready_images = collect_images(READY_DIR)

not_ready_images = collect_images(NOT_READY_DIR)


print()
print("IMAGE COUNTS")
print("-" * 70)

print(
    f"Harvest_Ready     : {len(ready_images)}"
)

print(
    f"Harvest_Not_Ready : {len(not_ready_images)}"
)

print(
    f"Total             : "
    f"{len(ready_images) + len(not_ready_images)}"
)


# ============================================================
# CALCULATE HASHES
# ============================================================

print()
print("Calculating SHA-256 hashes...")
print()


ready_hashes = {}

for image in ready_images:

    file_hash = get_file_hash(image)

    ready_hashes[file_hash] = image


not_ready_hashes = {}

for image in not_ready_images:

    file_hash = get_file_hash(image)

    not_ready_hashes[file_hash] = image


# ============================================================
# FIND DUPLICATES WITHIN READY
# ============================================================

ready_duplicate_hashes = {}

for image in ready_images:

    file_hash = get_file_hash(image)

    if file_hash in ready_duplicate_hashes:

        ready_duplicate_hashes[file_hash].append(image)

    else:

        ready_duplicate_hashes[file_hash] = [image]


ready_duplicates = {
    file_hash: files
    for file_hash, files
    in ready_duplicate_hashes.items()
    if len(files) > 1
}


# ============================================================
# FIND DUPLICATES WITHIN NOT READY
# ============================================================

not_ready_duplicate_hashes = {}

for image in not_ready_images:

    file_hash = get_file_hash(image)

    if file_hash in not_ready_duplicate_hashes:

        not_ready_duplicate_hashes[file_hash].append(image)

    else:

        not_ready_duplicate_hashes[file_hash] = [image]


not_ready_duplicates = {
    file_hash: files
    for file_hash, files
    in not_ready_duplicate_hashes.items()
    if len(files) > 1
}


# ============================================================
# CROSS-CLASS DUPLICATES
# ============================================================

cross_class_hashes = (
    set(ready_hashes.keys())
    &
    set(not_ready_hashes.keys())
)


# ============================================================
# RESULTS
# ============================================================

print("=" * 70)
print("DUPLICATE CHECK RESULTS")
print("=" * 70)

print()

print(
    f"Duplicate images inside Harvest_Ready     : "
    f"{len(ready_duplicates)}"
)

print(
    f"Duplicate images inside Harvest_Not_Ready : "
    f"{len(not_ready_duplicates)}"
)

print(
    f"Cross-class duplicate images              : "
    f"{len(cross_class_hashes)}"
)


# ============================================================
# DISPLAY CROSS-CLASS DUPLICATES
# ============================================================

if cross_class_hashes:

    print()
    print("⚠️ CROSS-CLASS DUPLICATES FOUND")
    print("-" * 70)

    for file_hash in cross_class_hashes:

        print()

        print(
            f"Harvest_Ready     : "
            f"{ready_hashes[file_hash]}"
        )

        print(
            f"Harvest_Not_Ready : "
            f"{not_ready_hashes[file_hash]}"
        )


# ============================================================
# FINAL STATUS
# ============================================================

print()
print("=" * 70)

if (
    not ready_duplicates
    and not not_ready_duplicates
    and not cross_class_hashes
):

    print(
        "✅ NO EXACT DUPLICATE IMAGES FOUND"
    )

    print(
        "✅ ORIGINAL HARVEST DATASET PASSED DUPLICATE CHECK"
    )

else:

    print(
        "⚠️ DUPLICATE IMAGES FOUND"
    )

print("=" * 70)
print()