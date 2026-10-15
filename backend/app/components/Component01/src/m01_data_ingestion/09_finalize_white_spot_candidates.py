
from pathlib import Path
from hashlib import sha256
from collections import Counter
import csv

# ====================================================
# STEP 09 - FINALIZE WHITE SPOT SCREENED CANDIDATES
# ====================================================

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "outputs" / "reports"
PROCESSED_DIR = ROOT / "data" / "processed"

SOURCE_CSV = (
    REPORT_DIR / "external_white_spot_yolo_crops.csv"
)

SIMILARITY_CSV = (
    REPORT_DIR / "white_spot_near_duplicate_candidates.csv"
)

DECISIONS_CSV = (
    REPORT_DIR / "white_spot_visual_review_decisions.csv"
)

CANDIDATES_CSV = (
    PROCESSED_DIR / "white_spot_screened_candidates.csv"
)

EXCLUSIONS_CSV = (
    REPORT_DIR / "white_spot_excluded_crops.csv"
)

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def hash_file(path):
    digest = sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def save_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


# ----------------------------------------------------
# 01. LOAD AUDIT RESULTS
# ----------------------------------------------------

crop_rows = read_csv(SOURCE_CSV)
similarity_rows = read_csv(SIMILARITY_CSV)

cross_split_pairs = [
    row for row in similarity_rows
    if row["comparison"] == "cross_yolo_split"
]

# The user visually confirmed exactly these 3 pairs.
# Stop if the source report has changed.
if len(cross_split_pairs) != 3:
    raise ValueError(
        "Expected exactly 3 reviewed pairs. "
        "Review the updated similarity report first."
    )

# ----------------------------------------------------
# 02. RECORD VISUAL REVIEW DECISIONS
# ----------------------------------------------------

decisions = []
excluded_hashes = set()

for index, pair in enumerate(cross_split_pairs, start=1):

    first_path = ROOT / pair["first_path"]
    second_path = ROOT / pair["second_path"]

    if not first_path.is_file():
        raise FileNotFoundError(first_path)

    if not second_path.is_file():
        raise FileNotFoundError(second_path)

    excluded_hashes.add(hash_file(first_path))
    excluded_hashes.add(hash_file(second_path))

    decisions.append({
        "pair_id": index,
        "first_path": pair["first_path"],
        "second_path": pair["second_path"],
        "first_split": pair["first_split"],
        "second_split": pair["second_split"],
        "review_decision": "confirmed_same_leaf",
        "action": "exclude_both_from_candidates"
    })

save_csv(
    DECISIONS_CSV,
    decisions,
    list(decisions[0].keys())
)

# ----------------------------------------------------
# 03. REMOVE EXACT DUPLICATE COPIES
#    AND REVIEW-CONFIRMED LEAKAGE GROUPS
# ----------------------------------------------------

seen_hashes = set()
candidates = []
exclusions = []
counts = Counter()

for row in crop_rows:

    crop_path = ROOT / row["crop_path"]

    if not crop_path.is_file():
        raise FileNotFoundError(crop_path)

    digest = hash_file(crop_path)

    if digest in excluded_hashes:
        reason = "confirmed_cross_split_same_leaf"

    elif digest in seen_hashes:
        reason = "exact_duplicate_copy"

    else:
        reason = None

    if reason is not None:
        exclusions.append({
            "crop_path": row["crop_path"],
            "crop_sha256": digest,
            "reason": reason
        })
        counts[reason] += 1
        continue

    seen_hashes.add(digest)

    candidates.append({
        "crop_path": row["crop_path"],
        "class_name": "white spot",
        "dataset_source": "external_yolo",
        "original_split": row["original_split"],
        "source_image": row["source_image"],
        "source_image_sha256": row["source_image_sha256"],
        "crop_sha256": digest,
        "review_status": "pending_visual_quality_review"
    })

    counts[f"{row['original_split']}_candidates"] += 1

# ----------------------------------------------------
# 04. SAVE RESULTS
# ----------------------------------------------------

candidate_columns = [
    "crop_path",
    "class_name",
    "dataset_source",
    "original_split",
    "source_image",
    "source_image_sha256",
    "crop_sha256",
    "review_status"
]

save_csv(
    CANDIDATES_CSV,
    candidates,
    candidate_columns
)

save_csv(
    EXCLUSIONS_CSV,
    exclusions,
    ["crop_path", "crop_sha256", "reason"]
)

# ----------------------------------------------------
# 05. SUMMARY
# ----------------------------------------------------

print("=" * 65)
print("STEP 09 - WHITE SPOT CANDIDATE FINALIZATION")
print("=" * 65)

print(f"Total source crop records : {len(crop_rows)}")
print(f"Visually confirmed pairs  : {len(decisions)}")
print(f"Excluded unique hashes    : {len(excluded_hashes)}")
print(f"Screened unique candidates: {len(candidates)}")

print("\nCandidates by original split:")

for split in ["train", "valid", "test"]:
    print(
        f"{split:<10}: "
        f"{counts[f'{split}_candidates']}"
    )

print("\nExcluded records by reason:")

for reason, count in sorted(counts.items()):
    if reason in {
        "confirmed_cross_split_same_leaf",
        "exact_duplicate_copy"
    }:
        print(f"{reason}: {count}")

print("\nSaved reports:")
print(DECISIONS_CSV)
print(CANDIDATES_CSV)
print(EXCLUSIONS_CSV)

print("\nNo source files deleted.")
print("Remaining candidates require quality review.")
print("STEP 09 COMPLETED")
