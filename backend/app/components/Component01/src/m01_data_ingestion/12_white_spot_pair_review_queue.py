"""
STEP 12 - Prioritized White Spot source-similarity review.

Reads the STEP 11 candidate-pair CSV; generates a small, editable human-review
queue and side-by-side contact sheets. Does NOT automatically certify sources,
merge provisional groups, change training splits, or delete image files.

Run (from anywhere):
    python path/to/12_white_spot_pair_review_queue.py
    python path/to/12_white_spot_pair_review_queue.py --max-pairs 40
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

COMPONENT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = COMPONENT_ROOT / "outputs" / "reports"
INPUT_CSV = REPORT_DIR / "white_spot_grouping_review_pairs.csv"
QUEUE_CSV = REPORT_DIR / "white_spot_priority_review_queue.csv"
SUMMARY_JSON = REPORT_DIR / "white_spot_priority_review_summary.json"
PREVIEW_DIR = COMPONENT_ROOT / "outputs" / "figures" / "white_spot_priority_review"

REQUIRED = {
    "first_path", "second_path", "first_split", "second_split",
    "phash_distance", "dhash_distance", "cross_yolo_split",
    "screening_level", "review_status",
}
VALID_DECISIONS = {"pending", "same_leaf", "different_leaf", "uncertain"}


def load_csv(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"First run Step 11: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing columns: {sorted(missing)}")
        return list(reader)


def local_image(relative_path: str) -> Path:
    p = (COMPONENT_ROOT / relative_path).resolve()
    # Prevent accidental reading outside Component01 if a CSV path is malformed.
    try:
        p.relative_to(COMPONENT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Image path outside Component01: {relative_path}") from exc
    if not p.is_file():
        raise FileNotFoundError(f"Review image missing: {p}")
    return p


def pair_key(row):
    return tuple(sorted((row["first_path"], row["second_path"])))


def risk_rank(row):
    a, b = row["first_split"].strip().lower(), row["second_split"].strip().lower()
    # Hold-out test leakage comes first. Original images are currently unassigned.
    if a != b and "test" in (a, b):
        return 0
    if a != b and "valid" in (a, b):
        return 1
    if a != b:
        return 2
    return 3


def score(row):
    return (
        risk_rank(row),
        0 if row["screening_level"] == "group_candidate" else 1,
        int(row["phash_distance"]) + int(row["dhash_distance"]),
        int(row["phash_distance"]),
        row["first_path"], row["second_path"],
    )


def choose_review_pairs(rows, max_pairs):
    # Avoid listing the same unordered pair twice.
    seen = set()
    unique = []
    for row in rows:
        key = pair_key(row)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    unique.sort(key=score)

    # Prefer variety; don't fill all pages with one repeated reference image.
    selected = []
    used = set()
    for row in unique:
        if len(selected) >= max_pairs:
            break
        if row["first_path"] in used or row["second_path"] in used:
            continue
        selected.append(row)
        used.update((row["first_path"], row["second_path"]))

    # Second pass includes overlapping pairs when necessary.
    taken = {pair_key(row) for row in selected}
    for row in unique:
        if len(selected) >= max_pairs:
            break
        if pair_key(row) not in taken:
            selected.append(row)
            taken.add(pair_key(row))
    return selected, len(unique)


def make_thumb(path, box=(270, 190)):
    with Image.open(path) as opened:
        im = ImageOps.exif_transpose(opened).convert("RGB")
        return ImageOps.contain(im, box)


def render_sheets(rows):
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    per_page = 8
    cell_w = 650
    cell_h = 245
    for page_num in range(math.ceil(len(rows) / per_page)):
        batch = rows[page_num * per_page : (page_num + 1) * per_page]
        sheet = Image.new("RGB", (cell_w, cell_h * len(batch)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, row in enumerate(batch):
            top = i * cell_h
            left_img = make_thumb(local_image(row["first_path"]))
            right_img = make_thumb(local_image(row["second_path"]))
            sheet.paste(left_img, (12, top + 26))
            sheet.paste(right_img, (338, top + 26))
            header = (f"{row['pair_id']}  {row['screening_level']}  "
                      f"pHash={row['phash_distance']} dHash={row['dhash_distance']}")
            draw.text((12, top + 5), header, fill="black")
            first = f"{row['first_split']}: {Path(row['first_path']).name[:38]}"
            second = f"{row['second_split']}: {Path(row['second_path']).name[:38]}"
            draw.text((12, top + 221), first, fill="black")
            draw.text((338, top + 221), second, fill="black")
            draw.line((0, top + cell_h - 1, cell_w, top + cell_h - 1), fill="gray")
        out = PREVIEW_DIR / f"priority_review_{page_num + 1:02d}.jpg"
        sheet.save(out, quality=91)
        print(f"Created: {out.name}")


def main():
    parser = argparse.ArgumentParser(description="Prepare prioritized White Spot human-review queue")
    parser.add_argument("--max-pairs", type=int, default=40,
                        help="Number of priority pairs to show first (default: 40)")
    args = parser.parse_args()
    if not 1 <= args.max_pairs <= 743:
        raise ValueError("--max-pairs must be between 1 and 743")

    source_rows = load_csv(INPUT_CSV)
    for row in source_rows:
        # Fail clearly on invalid numeric fields, rather than silently misranking.
        int(row["phash_distance"])
        int(row["dhash_distance"])
    selected, unique_count = choose_review_pairs(source_rows, args.max_pairs)
    if not selected:
        raise ValueError("Step 11 report contains no candidate pairs")

    new_rows = []
    for i, row in enumerate(selected, 1):
        local_image(row["first_path"])
        local_image(row["second_path"])
        new_rows.append({
            "pair_id": f"WS_PAIR_{i:03d}",
            "first_path": row["first_path"],
            "second_path": row["second_path"],
            "first_split": row["first_split"],
            "second_split": row["second_split"],
            "phash_distance": row["phash_distance"],
            "dhash_distance": row["dhash_distance"],
            "screening_level": row["screening_level"],
            "cross_yolo_split": row["cross_yolo_split"],
            "review_decision": "pending",
            "review_notes": "",
        })

    columns = list(new_rows[0])
    if QUEUE_CSV.exists():
        with QUEUE_CSV.open("r", newline="", encoding="utf-8-sig") as f:
            old_rows = list(csv.DictReader(f))
        # Preserve manual decisions; changing queue size requires an explicit backup.
        if [pair_key(r) for r in old_rows] != [pair_key(r) for r in new_rows]:
            raise RuntimeError(
                f"Existing review queue differs: {QUEUE_CSV}\n"
                "Preserving any manual work. Rename/back up that CSV before "
                "rerunning with a different --max-pairs."
            )
        for new, old in zip(new_rows, old_rows):
            decision = old.get("review_decision", "pending").strip().lower()
            if decision not in VALID_DECISIONS:
                raise ValueError(f"Invalid decision in {old.get('pair_id')}: {decision}")
            new["review_decision"] = decision
            new["review_notes"] = old.get("review_notes", "")
    else:
        QUEUE_CSV.parent.mkdir(parents=True, exist_ok=True)

    with QUEUE_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(new_rows)

    render_sheets(new_rows)
    statuses = Counter(row["review_decision"] for row in new_rows)
    summary = {
        "source_pairs": len(source_rows),
        "unique_unordered_pairs": unique_count,
        "priority_pairs_selected": len(new_rows),
        "priority_pairs_with_different_split_labels": sum(
            row["first_split"] != row["second_split"] for row in new_rows
        ),
        "decisions": dict(statuses),
        "important": "This is a review queue, NOT a final source-group or training split.",
    }
    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=" * 65)
    print("STEP 12 - WHITE SPOT PRIORITY PAIR REVIEW")
    print("=" * 65)
    print("Candidate pairs in source report:", len(source_rows))
    print("Unique unordered candidate pairs:", unique_count)
    print("Priority pairs on review sheets:", len(new_rows))
    print("Review decisions:", dict(statuses))
    print("Editable decision CSV:", QUEUE_CSV)
    print("Review contact sheets:", PREVIEW_DIR)
    print("Decisions: same_leaf / different_leaf / uncertain / pending")
    print("NO images changed, NO final splits created.")


if __name__ == "__main__":
    main()
