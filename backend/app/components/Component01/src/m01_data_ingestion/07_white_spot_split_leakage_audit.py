
from pathlib import Path
from collections import defaultdict, Counter
from hashlib import sha256
import csv

# =====================================================
# STEP 07 - WHITE SPOT CROSS-SPLIT LEAKAGE AUDIT
# =====================================================

ROOT = Path(__file__).resolve().parents[2]

REPORT_DIR = ROOT / "outputs" / "reports"

INPUT_FILE = (
    REPORT_DIR / "external_white_spot_yolo_crops.csv"
)

OUTPUT_FILE = (
    REPORT_DIR / "white_spot_split_leakage_audit.csv"
)

if not INPUT_FILE.is_file():
    raise FileNotFoundError(
        f"Missing extraction report: {INPUT_FILE}"
    )


def calculate_hash(path):
    digest = sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024), b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


with INPUT_FILE.open(
    "r", newline="", encoding="utf-8"
) as file:
    records = list(csv.DictReader(file))


# Group crops with identical image content.
groups = defaultdict(list)
source_groups = defaultdict(set)
split_counts = Counter()

for record in records:

    image_path = ROOT / record["crop_path"]

    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    crop_hash = calculate_hash(image_path)

    record["crop_sha256"] = crop_hash

    groups[crop_hash].append(record)

    source_hash = record["source_image_sha256"]

    source_groups[source_hash].add(
        record["original_split"]
    )

    split_counts[record["original_split"]] += 1


# Detect exact-identical crops present in more than
# one of the original YOLO dataset splits.
cross_split_groups = {}

for crop_hash, group in groups.items():

    splits = {
        record["original_split"]
        for record in group
    }

    if len(splits) > 1:
        cross_split_groups[crop_hash] = group


# Save audit report for every crop.
output_rows = []

for crop_hash, group in groups.items():

    splits = sorted({
        r["original_split"]
        for r in group
    })

    for record in group:

        output_rows.append({
            "crop_path": record["crop_path"],
            "source_image": record["source_image"],
            "original_split": record["original_split"],
            "crop_sha256": crop_hash,
            "duplicate_group_size": len(group),
            "group_splits": ",".join(splits),
            "cross_split_duplicate": (
                "yes" if len(splits) > 1 else "no"
            ),
        })


fieldnames = [
    "crop_path",
    "source_image",
    "original_split",
    "crop_sha256",
    "duplicate_group_size",
    "group_splits",
    "cross_split_duplicate",
]

with OUTPUT_FILE.open(
    "w", newline="", encoding="utf-8"
) as file:

    writer = csv.DictWriter(
        file, fieldnames=fieldnames
    )

    writer.writeheader()
    writer.writerows(output_rows)


total_crops = len(records)
unique_crops = len(groups)
extra_copies = total_crops - unique_crops

cross_split_source_groups = sum(
    len(splits) > 1
    for splits in source_groups.values()
)

print("=" * 65)
print("STEP 07 - WHITE SPOT SPLIT LEAKAGE AUDIT")
print("=" * 65)

print(f"Total crops                 : {total_crops}")
print(f"Unique exact crop hashes    : {unique_crops}")
print(f"Extra exact duplicate copies: {extra_copies}")

print("\nOriginal split counts:")

for split in ["train", "valid", "test"]:
    print(f"{split:<10}: {split_counts[split]}")

print("\nLeakage screening results:")

print(
    "Cross-split exact crop groups:",
    len(cross_split_groups)
)

print(
    "Cross-split source hash groups:",
    cross_split_source_groups
)

print("\nAudit report:")
print(OUTPUT_FILE)

if cross_split_groups:
    print(
        "\nWARNING: Exact crops are shared "
        "between different splits."
    )
    print(
        "Resolve these groups before model training."
    )
else:
    print(
        "\nPASS: No cross-split exact crop "
        "duplicates detected."
    )

print(
    "\nNOTE: Perceptual near-duplicate and "
    "source provenance checks are still required."
)

print("\nNO IMAGES MODIFIED")
print("STEP 07 COMPLETED")
