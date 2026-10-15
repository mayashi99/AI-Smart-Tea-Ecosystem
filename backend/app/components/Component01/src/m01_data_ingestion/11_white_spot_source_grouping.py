from pathlib import Path
from collections import defaultdict
from hashlib import sha256
from PIL import Image, ImageOps, ImageDraw
import csv
import math
import imagehash

# STEP 11 - WHITE SPOT SOURCE-LEVEL GROUPING (DRAFT)
ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "outputs" / "reports"
PROCESSED = ROOT / "data" / "processed"
PREVIEWS = ROOT / "outputs" / "figures" / "white_spot_source_groups"
ORIGINAL_CSV = REPORTS / "image_audit.csv"
CROPS_CSV = PROCESSED / "white_spot_screened_candidates.csv"
GROUPS_CSV = PROCESSED / "white_spot_source_groups_draft.csv"
PAIRS_CSV = REPORTS / "white_spot_grouping_review_pairs.csv"
SUMMARY_CSV = REPORTS / "white_spot_grouping_summary.csv"

# Thresholds are screening heuristics, NOT a final same-leaf verdict.
STRONG_PHASH = 6
STRONG_DHASH = 8
REVIEW_PHASH = 14
REVIEW_DHASH = 14


def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def hash_file(path):
    digest = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_record(items, path, source, split, source_hash):
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as opened:
        opened.verify()
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        p_hash = imagehash.phash(image)
        d_hash = imagehash.dhash(image)
    items.append({
        "path": path.relative_to(ROOT).as_posix(),
        "source": source,
        "source_split": split,
        "source_image_sha256": source_hash,
        "file_sha256": hash_file(path),
        "phash": p_hash,
        "dhash": d_hash,
    })


original_rows = read_csv(ORIGINAL_CSV)
crop_rows = read_csv(CROPS_CSV)
items = []
seen_original = set()
for row in original_rows:
    if row["class_name"] != "white spot" or row["status"] == "corrupted":
        continue
    path = ROOT / "data" / "raw" / "images" / row["relative_path"]
    # Collapse exact duplicates within the original dataset.
    digest = hash_file(path)
    if digest in seen_original:
        continue
    seen_original.add(digest)
    add_record(items, path, "original", "unassigned", digest)

for row in crop_rows:
    add_record(
        items,
        ROOT / row["crop_path"],
        "yolo_crop",
        row["original_split"],
        row["source_image_sha256"],
    )

items.sort(key=lambda x: (x["source"], x["path"]))
parent = list(range(len(items)))


def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def union(i, j):
    a, b = find(i), find(j)
    if a != b:
        parent[b] = a


pair_rows = []
for i, first in enumerate(items):
    for j in range(i + 1, len(items)):
        second = items[j]
        p_dist = first["phash"] - second["phash"]
        d_dist = first["dhash"] - second["dhash"]
        exact = first["file_sha256"] == second["file_sha256"]
        same_source = (
            first["source"] == second["source"] == "yolo_crop"
            and first["source_image_sha256"] == second["source_image_sha256"]
        )
        strong = exact or same_source or (p_dist <= STRONG_PHASH and d_dist <= STRONG_DHASH)
        possible = strong or p_dist <= REVIEW_PHASH or d_dist <= REVIEW_DHASH
        if not possible:
            continue
        if strong:
            union(i, j)
        cross_yolo_split = (
            first["source"] == second["source"] == "yolo_crop"
            and first["source_split"] != second["source_split"]
        )
        pair_rows.append({
            "first_path": first["path"],
            "second_path": second["path"],
            "first_split": first["source_split"],
            "second_split": second["source_split"],
            "phash_distance": p_dist,
            "dhash_distance": d_dist,
            "cross_yolo_split": "yes" if cross_yolo_split else "no",
            "screening_level": "group_candidate" if strong else "review_candidate",
            "review_status": "pending",
        })

members_by_root = defaultdict(list)
for i in range(len(items)):
    members_by_root[find(i)].append(i)

ordered_groups = sorted(
    members_by_root.values(),
    key=lambda ids: min(items[i]["path"] for i in ids),
)
PREVIEWS.mkdir(parents=True, exist_ok=True)
member_rows, summary_rows = [], []
for index, members in enumerate(ordered_groups, start=1):
    group_id = f"WSG_{index:03d}"
    splits = sorted(set(items[i]["source_split"] for i in members if items[i]["source_split"] != "unassigned"))
    sources = sorted(set(items[i]["source"] for i in members))
    summary_rows.append({
        "group_id": group_id,
        "images": len(members),
        "sources": ";".join(sources),
        "yolo_splits": ";".join(splits),
        "cross_yolo_split": "yes" if len(splits) > 1 else "no",
        "review_status": "pending",
    })
    for i in members:
        record = items[i]
        member_rows.append({
            "group_id": group_id,
            "image_path": record["path"],
            "dataset_source": record["source"],
            "original_yolo_split": record["source_split"],
            "image_sha256": record["file_sha256"],
            "source_image_sha256": record["source_image_sha256"],
            "review_status": "pending",
        })
    if len(members) < 2:
        continue
    # Contact sheets make the suggested groups easy to manually confirm.
    for page_idx in range(math.ceil(len(members) / 25)):
        subset = members[page_idx * 25:(page_idx + 1) * 25]
        sheet = Image.new("RGB", (5 * 180, 5 * 180), "white")
        draw = ImageDraw.Draw(sheet)
        for k, i in enumerate(subset):
            item = items[i]
            x, y = (k % 5) * 180, (k // 5) * 180
            with Image.open(ROOT / item["path"]) as opened:
                image = ImageOps.contain(
                    ImageOps.exif_transpose(opened).convert("RGB"), (165, 145)
                )
            sheet.paste(image, (x + 5, y + 5))
            draw.text((x + 5, y + 153), f"{item['source'][:4]}:{item['source_split'][:5]}", fill="black")
        sheet.save(PREVIEWS / f"{group_id}_page_{page_idx + 1:02d}.jpg", quality=90)

write_csv(GROUPS_CSV, member_rows,
    ["group_id", "image_path", "dataset_source", "original_yolo_split", "image_sha256", "source_image_sha256", "review_status"])
write_csv(PAIRS_CSV, sorted(pair_rows, key=lambda r: (r["screening_level"], int(r["phash_distance"]) + int(r["dhash_distance"]))),
    ["first_path", "second_path", "first_split", "second_split", "phash_distance", "dhash_distance", "cross_yolo_split", "screening_level", "review_status"])
write_csv(SUMMARY_CSV, summary_rows,
    ["group_id", "images", "sources", "yolo_splits", "cross_yolo_split", "review_status"])

print("=" * 65)
print("STEP 11 - WHITE SPOT SOURCE-LEVEL GROUP SCREENING")
print("=" * 65)
print(f"Total images screened     : {len(items)}")
print(f"Provisional groups        : {len(ordered_groups)}")
print(f"Multi-image groups        : {sum(len(g)>1 for g in ordered_groups)}")
print(f"Groups spanning YOLO splits: {sum(r['cross_yolo_split']=='yes' for r in summary_rows)}")
print(f"Similarity pairs to review: {len(pair_rows)}")
print(f"Group candidates saved: {GROUPS_CSV}")
print(f"Pair report saved     : {PAIRS_CSV}")
print(f"Group summary saved   : {SUMMARY_CSV}")
print(f"Visual sheets         : {PREVIEWS}")
print("IMPORTANT: Proposed groups are unverified. Do NOT use as final train/test split.")
print("NO ORIGINAL IMAGES MODIFIED")
