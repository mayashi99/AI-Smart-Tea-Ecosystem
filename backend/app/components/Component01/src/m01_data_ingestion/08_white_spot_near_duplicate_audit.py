
from pathlib import Path
from collections import Counter
from hashlib import sha256
from PIL import Image, ImageOps
import csv
import json

# ==========================================================
# STEP 08 - WHITE SPOT NEAR-DUPLICATE LEAKAGE AUDIT
# ==========================================================

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "outputs" / "reports"

CROP_REPORT = REPORT_DIR / "external_white_spot_yolo_crops.csv"
ORIGINAL_REPORT = REPORT_DIR / "image_audit.csv"

OUTPUT_CSV = REPORT_DIR / "white_spot_near_duplicate_candidates.csv"
OUTPUT_JSON = REPORT_DIR / "white_spot_near_duplicate_summary.json"

THRESHOLD = 4  # Candidate review threshold, not automatic removal


def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sha256_file(path):
    digest = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dhash(path):
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened)
        image = image.convert("L").resize((9, 8))
        pixels = image.tobytes()

    value = 0
    for y in range(8):
        for x in range(8):
            a = pixels[y * 9 + x]
            b = pixels[y * 9 + x + 1]
            value = (value << 1) | int(a > b)

    return value


def distance(a, b):
    return (a ^ b).bit_count()


crop_rows = read_csv(CROP_REPORT)
original_rows = read_csv(ORIGINAL_REPORT)

# ----------------------------------------------------------
# 01. KEEP ONE REPRESENTATIVE PER EXACT CROP HASH
# ----------------------------------------------------------

unique_crops = {}
split_unique_hashes = {
    "train": set(),
    "valid": set(),
    "test": set()
}

for row in crop_rows:
    path = ROOT / row["crop_path"]

    if not path.is_file():
        raise FileNotFoundError(path)

    digest = sha256_file(path)

    split_unique_hashes[row["original_split"]].add(digest)

    if digest not in unique_crops:
        unique_crops[digest] = {
            "path": row["crop_path"],
            "split": row["original_split"],
            "dhash": dhash(path)
        }

crops = list(unique_crops.values())

# ----------------------------------------------------------
# 02. LOAD ORIGINAL WHITE SPOT REFERENCE IMAGES
# ----------------------------------------------------------

original_unique = {}

for row in original_rows:
    if row["class_name"] != "white spot":
        continue

    if row["status"] == "corrupted":
        continue

    digest = row["sha256"]

    if not digest or digest in original_unique:
        continue

    path = ROOT / "data/raw/images" / row["relative_path"]

    if not path.is_file():
        raise FileNotFoundError(path)

    original_unique[digest] = {
        "path": str(path.relative_to(ROOT)),
        "split": "not_yet_assigned",
        "dhash": dhash(path)
    }

originals = list(original_unique.values())

# ----------------------------------------------------------
# 03. FIND SIMILAR CROPS ACROSS YOLO SPLITS
# ----------------------------------------------------------

candidates = []
counts = Counter()

for i in range(len(crops)):
    for j in range(i + 1, len(crops)):
        a = crops[i]
        b = crops[j]

        if a["split"] == b["split"]:
            continue

        d = distance(a["dhash"], b["dhash"])

        if d <= THRESHOLD:
            candidates.append({
                "comparison": "cross_yolo_split",
                "first_path": a["path"],
                "first_split": a["split"],
                "second_path": b["path"],
                "second_split": b["split"],
                "dhash_distance": d
            })
            counts["cross_split_flags"] += 1

# ----------------------------------------------------------
# 04. COMPARE NEW CROPS WITH ORIGINAL WHITE SPOT
# ----------------------------------------------------------

for crop in crops:
    for original in originals:
        d = distance(crop["dhash"], original["dhash"])

        if d <= THRESHOLD:
            candidates.append({
                "comparison": "new_vs_original",
                "first_path": crop["path"],
                "first_split": crop["split"],
                "second_path": original["path"],
                "second_split": "not_yet_assigned",
                "dhash_distance": d
            })
            counts["original_overlap_flags"] += 1

# ----------------------------------------------------------
# 05. SAVE RESULTS
# ----------------------------------------------------------

candidates.sort(key=lambda row: (
    row["dhash_distance"],
    row["comparison"]
))

fields = [
    "comparison",
    "first_path",
    "first_split",
    "second_path",
    "second_split",
    "dhash_distance"
]

with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(candidates)

summary = {
    "total_crops": len(crop_rows),
    "unique_exact_crops": len(crops),
    "original_unique_white_spot": len(originals),
    "unique_crops_by_split": {
        split: len(hashes)
        for split, hashes in split_unique_hashes.items()
    },
    "cross_split_near_duplicate_flags": counts["cross_split_flags"],
    "new_vs_original_near_duplicate_flags": counts["original_overlap_flags"],
    "threshold": THRESHOLD
}

with OUTPUT_JSON.open("w", encoding="utf-8") as f:
    json.dump(summary, f, indent=4)

# ----------------------------------------------------------
# 06. TERMINAL OUTPUT
# ----------------------------------------------------------

print("=" * 65)
print("STEP 08 - WHITE SPOT NEAR-DUPLICATE AUDIT")
print("=" * 65)

print(f"Total YOLO crops         : {len(crop_rows)}")
print(f"Unique exact crops       : {len(crops)}")
print(f"Original White Spot refs : {len(originals)}")

print("\nExact unique crops by original YOLO split:")
for split in ["train", "valid", "test"]:
    print(f"{split:<10}: {len(split_unique_hashes[split])}")

print("\nSimilarity review flags:")
print(f"Cross-split flags        : {counts['cross_split_flags']}")
print(f"New vs original flags    : {counts['original_overlap_flags']}")

print("\nReports:")
print(OUTPUT_CSV)
print(OUTPUT_JSON)

print("\nIMPORTANT:")
print("Similarity flags are NOT confirmed duplicates.")
print("Review flagged pairs before making dataset decisions.")
print("No images modified or deleted.")
print("\nSTEP 08 COMPLETED")
