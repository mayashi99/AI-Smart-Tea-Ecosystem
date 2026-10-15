"""Step 13: record the 40 visual-screening suggestions in the editable queue.

This does NOT certify disease labels, finalize image groups, create train/test
splits, or resolve the remaining similarity pairs. Nothing is deleted.

Run from the J26-IT-415 repository root (or anywhere):
  python backend/app/components/Component01/src/m01_data_ingestion/13_apply_white_spot_review_decisions.py
"""
from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from pathlib import Path

COMPONENT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = COMPONENT_ROOT / "outputs" / "reports"
QUEUE = REPORT_DIR / "white_spot_priority_review_queue.csv"
BACKUP = REPORT_DIR / "white_spot_priority_review_queue_before_step13.csv"
SUMMARY = REPORT_DIR / "white_spot_step13_review_summary.json"

# Suggested after inspection of five contact sheets; human-reviewable.
DIFFERENT_LEAF = {12, 14, 30, 31, 34, 35}
UNCERTAIN = {21, 23, 26, 27, 28}
EXPECTED_IDS = {f"WS_PAIR_{i:03d}" for i in range(1, 41)}


def suggested_decision(pair_id: str) -> str:
    index = int(pair_id.rsplit("_", 1)[1])
    if index in DIFFERENT_LEAF:
        return "different_leaf"
    if index in UNCERTAIN:
        return "uncertain"
    return "same_leaf"


def apply(queue: Path = QUEUE, backup: Path = BACKUP, summary: Path = SUMMARY) -> Counter:
    if not queue.is_file():
        raise FileNotFoundError(f"Run Step 12 first; missing {queue}")

    with queue.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        required = {"pair_id", "review_decision", "review_notes", "first_path", "second_path"}
        if not required.issubset(fields):
            raise ValueError(f"Missing CSV fields: {sorted(required - set(fields))}")
        rows = list(reader)

    ids = [r["pair_id"] for r in rows]
    if len(ids) != 40 or set(ids) != EXPECTED_IDS or len(set(ids)) != 40:
        raise ValueError("The CSV is not the expected 40-pair Step 12 review queue. No changes made.")

    for row in rows:
        proposed = suggested_decision(row["pair_id"])
        current = row["review_decision"].strip().lower()
        if current not in {"", "pending", proposed}:
            raise ValueError(
                f"Manual decision for {row['pair_id']} is '{current}', different from "
                f"the suggested '{proposed}'. No changes made; preserve the manual decision."
            )
        row["review_decision"] = proposed
        if not row["review_notes"].strip():
            row["review_notes"] = "AI-assisted contact-sheet suggestion; verify before final grouping"

    # Preserve the initial editable file so suggestions can be reversed.
    if not backup.exists():
        shutil.copy2(queue, backup)

    temp_path = queue.with_suffix(".step13.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temp_path.replace(queue)

    counts = Counter(r["review_decision"] for r in rows)
    with summary.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "status": "provisional_human_review_suggestions",
                "pairs_reviewed": len(rows),
                "decisions": dict(counts),
                "unreviewed_other_pairs": 703,
                "training_approved": False,
                "note": "No final groups or splits. Review remaining risks conservatively.",
            },
            f,
            indent=2,
        )
    return counts


if __name__ == "__main__":
    result = apply()
    print("=" * 65)
    print("STEP 13 - RECORD WHITE SPOT VISUAL REVIEW SUGGESTIONS")
    print("=" * 65)
    print("Decision counts:", dict(result))
    print("Updated:", QUEUE)
    print("Backup:", BACKUP)
    print("Summary:", SUMMARY)
    print("Remaining similarity candidates require conservative handling.")
    print("NO images modified, NO final splits created.")
