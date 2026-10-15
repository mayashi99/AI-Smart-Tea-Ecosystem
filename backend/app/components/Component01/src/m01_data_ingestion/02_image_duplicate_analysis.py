
from pathlib import Path
from collections import Counter, defaultdict
import csv
import json

# ================================================
# STEP 02 - EXACT IMAGE DUPLICATE ANALYSIS
# ================================================

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "outputs" / "reports"

INPUT_FILE = REPORT_DIR / "image_audit.csv"
OUTPUT_FILE = REPORT_DIR / "image_duplicate_groups.csv"
SUMMARY_FILE = REPORT_DIR / "image_duplicate_summary.json"

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Run 01_image_data_audit.py first: {INPUT_FILE}"
    )

# Read previously generated audit results
with INPUT_FILE.open(
    "r", encoding="utf-8", newline=""
) as file:
    records = list(csv.DictReader(file))

# Group identical image files by SHA-256 hash
hash_groups = defaultdict(list)

for record in records:
    file_hash = record["sha256"]

    if file_hash:
        hash_groups[file_hash].append(record)

# Only groups with multiple identical files
duplicate_groups = {
    h: group
    for h, group in hash_groups.items()
    if len(group) > 1
}

class_duplicate_groups = Counter()
class_duplicate_extras = Counter()
duplicate_rows = []
cross_class_groups = 0

for file_hash, group in duplicate_groups.items():

    classes = {r["class_name"] for r in group}

    if len(classes) > 1:
        cross_class_groups += 1

    class_counts = Counter(
        r["class_name"] for r in group
    )

    for class_name, count in class_counts.items():
        class_duplicate_groups[class_name] += 1
        class_duplicate_extras[class_name] += count - 1

    for record in group:
        duplicate_rows.append({
            "sha256": file_hash,
            "class_name": record["class_name"],
            "relative_path": record["relative_path"],
            "group_size": len(group),
        })

# Save detailed duplicate report
with OUTPUT_FILE.open(
    "w", encoding="utf-8", newline=""
) as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "sha256",
            "class_name",
            "relative_path",
            "group_size",
        ],
    )
    writer.writeheader()
    writer.writerows(duplicate_rows)

total_images = len(records)

# Number of redundant copies (not duplicate groups)
extra_copies = sum(
    len(group) - 1
    for group in duplicate_groups.values()
)

summary = {
    "total_images": total_images,
    "exact_duplicate_groups": len(duplicate_groups),
    "extra_duplicate_copies": extra_copies,
    "unique_image_hashes": len(hash_groups),
    "cross_class_duplicate_groups": cross_class_groups,
    "duplicate_groups_by_class": dict(class_duplicate_groups),
    "extra_copies_by_class": dict(class_duplicate_extras),
}

with SUMMARY_FILE.open(
    "w", encoding="utf-8"
) as file:
    json.dump(summary, file, indent=4)

print("=" * 65)
print("STEP 02 - EXACT IMAGE DUPLICATE ANALYSIS")
print("=" * 65)

print(f"Total images               : {total_images}")
print(f"Exact duplicate groups     : {len(duplicate_groups)}")
print(f"Extra duplicate copies     : {extra_copies}")
print(f"Unique image hashes        : {len(hash_groups)}")
print(f"Cross-class duplicate groups: {cross_class_groups}")

print("\nCLASS-WISE DUPLICATE ANALYSIS")

for class_name in sorted(
    {r["class_name"] for r in records}
):
    print(
        f"{class_name:<20} "
        f"groups={class_duplicate_groups[class_name]:<5} "
        f"extra_copies={class_duplicate_extras[class_name]}"
    )

print("\nReports saved:")
print(OUTPUT_FILE)
print(SUMMARY_FILE)

print("\nSTEP 02 COMPLETED - NO IMAGES DELETED")
