"""Step 15 - Conservative, reproducible image split after Step 14.

Purpose:
* Keep exact-duplicate images and Step 14 source-groups in the same split.
* Protect against known, still-unresolved White Spot candidate similarity links
  by placing *both members and their transitive group* in one split.
* Use all Step 11 candidate edges (not only the 276 that crossed Step 14),
  because a new split may expose different cross-split edges.
* Fail closed if conservative grouping leaves too little validation/test data.

This is a SCREENED PROVISIONAL dataset. Image-source IDs and expert label
verification are unavailable. A lack of cross-split candidate edges is NOT
proof that source leakage is impossible. No image is modified/deleted.

Run from any working directory (PowerShell):
  python backend/app/components/Component01/src/m01_data_ingestion/15_build_conservative_grouped_split.py

Optional for tests:
  python 15_build_conservative_grouped_split.py --root C:/path/to/Component01
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import random

CLASSES = (
    "brown blight", "grey leaf", "healthy", "red rust",
    "red spider mite", "white spot",
)
SEED = 42
MIN_EVAL_PER_CLASS = 10


class DSU:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        a, b = self.find(a), self.find(b)
        if a != b:
            if self.size[a] < self.size[b]:
                a, b = b, a
            self.parent[b] = a
            self.size[a] += self.size[b]


def read_csv(path: Path, required: set[str]) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Prerequisite CSV is missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        actual = set(reader.fieldnames or [])
        if missing := required - actual:
            raise ValueError(f"Missing columns in {path.name}: {sorted(missing)}")
        return list(reader)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normal_path(value: str) -> str:
    p = value.strip().replace("\\", "/")
    if not p or p.startswith("/") or ":" in p or ".." in p.split("/"):
        raise ValueError(f"Invalid component-relative path: {value!r}")
    return "/".join(part for part in p.split("/") if part not in ("", "."))


def allocate(cls: str, grouped: list[list[int]], image_total: int) -> tuple[dict[int, str], dict]:
    """Greedily reserve modest independent groups for eval; rest go to train.

    Largest connected components normally remain in training. Evaluation only
    proceeds when both held-out subsets contain >=10 candidate images.
    """
    rng = random.Random(SEED + CLASSES.index(cls) * 17)
    ordered = sorted(grouped, key=lambda g: min(g))
    rng.shuffle(ordered)
    ordered.sort(key=len)
    targets = {"val": round(image_total * .15), "test": round(image_total * .15)}
    counts = Counter()
    assigned: dict[int, str] = {}
    min_train = (image_total * 65 + 99) // 100  # ceil 65%, integers only
    nontrain_limit = image_total - min_train

    for group in ordered:
        n = len(group)
        options = []
        for split in ("val", "test"):
            current = counts[split]
            new = current + n
            if counts["val"] + counts["test"] + n > nontrain_limit:
                continue
            # Only use groups which move the target closer, to avoid a huge
            # group being placed into val/test just to fill a few spaces.
            if abs(targets[split] - new) < abs(targets[split] - current):
                options.append(split)
        if options:
            split = max(options, key=lambda s: (targets[s] - counts[s], s))
        else:
            split = "train"
        counts[split] += n
        for i in group:
            assigned[i] = split

    stats = {
        "images": image_total,
        "groups": len(grouped),
        "largest_conservative_group": max(map(len, grouped)),
        "train": counts["train"], "val": counts["val"], "test": counts["test"],
        "minimum_eval_required_each": MIN_EVAL_PER_CLASS,
        "eval_sufficient": counts["val"] >= MIN_EVAL_PER_CLASS
                            and counts["test"] >= MIN_EVAL_PER_CLASS,
        "train_at_least_65_percent": counts["train"] >= min_train,
    }
    return assigned, stats


def main(component_root: Path):
    root = component_root.resolve()
    processed = root / "data" / "processed"
    reports = root / "outputs" / "reports"
    draft_file = processed / "image_split_manifest_DRAFT.csv"
    source_pairs = reports / "white_spot_grouping_review_pairs.csv"
    orig_audit = reports / "image_audit.csv"
    output_file = processed / "image_split_manifest_SCREENED.csv"
    blocked_file = processed / "image_split_manifest_BLOCKED_DIAGNOSTIC.csv"
    summary_file = reports / "image_split_step15_summary.json"

    image_rows = read_csv(draft_file, {
        "class_name", "dataset_source", "relative_path", "sha256", "group_id", "split"
    })
    pair_rows = read_csv(source_pairs, {"first_path", "second_path", "screening_level"})
    audit_rows = read_csv(orig_audit, {"class_name", "relative_path", "sha256"})
    if not image_rows:
        raise ValueError("Empty Step 14 manifest")

    row_by_path: dict[str, int] = {}
    sha_to_i: dict[str, int] = {}
    group_to_i: dict[tuple[str, str], int] = {}
    dsu = DSU(len(image_rows))
    for i, row in enumerate(image_rows):
        cls = row["class_name"].strip().lower()
        if cls not in CLASSES:
            raise ValueError(f"Unexpected class: {cls}")
        row["class_name"] = cls
        path = normal_path(row["relative_path"])
        if path in row_by_path:
            raise ValueError(f"Duplicate relative path in draft: {path}")
        if row["split"] not in {"train", "val", "test"}:
            raise ValueError(f"Bad draft split: {row['split']}")
        row["relative_path"] = path
        row_by_path[path] = i
        digest = row["sha256"].strip().lower()
        if digest in sha_to_i and image_rows[sha_to_i[digest]]["class_name"] != cls:
            raise ValueError("Same SHA256 appears in different classes. Stop and verify labels.")
        if digest in sha_to_i:
            dsu.union(i, sha_to_i[digest])
        else:
            sha_to_i[digest] = i
        grp = (cls, row["group_id"])
        if grp in group_to_i:
            dsu.union(i, group_to_i[grp])
        else:
            group_to_i[grp] = i

    # Step 11 may refer to a different exact copy from Step 14's chosen copy.
    # Add SHA aliases from the original audit so we never miss those links.
    mapped_audit_aliases = 0
    for r in audit_rows:
        cls = r["class_name"].strip().lower()
        digest = r["sha256"].strip().lower()
        i = sha_to_i.get(digest)
        if i is None or image_rows[i]["class_name"] != cls:
            continue
        alias = normal_path("data/raw/images/" + r["relative_path"])
        if alias not in row_by_path:
            row_by_path[alias] = i
            mapped_audit_aliases += 1

    # Step 11 reported 743 candidate links across original and YOLO images.
    # Only those between included Step 14 files may influence the split.
    included_edges: set[tuple[int, int]] = set()
    excluded_yolo_or_unmatched = 0
    for r in pair_rows:
        first = row_by_path.get(normal_path(r["first_path"]))
        second = row_by_path.get(normal_path(r["second_path"]))
        if first is None or second is None:
            excluded_yolo_or_unmatched += 1
            continue
        if first == second:
            continue
        if image_rows[first]["class_name"] != image_rows[second]["class_name"]:
            raise ValueError("Similarity pair unexpectedly crosses disease classes")
        a, b = sorted((first, second))
        included_edges.add((a, b))

    # Verify the 276 Step 14 risk rows were not lost through path aliases.
    step14_risk_file = reports / "image_split_unresolved_similarity.csv"
    old_risks = read_csv(step14_risk_file, {"first_path", "second_path"})
    mapped_risk_pairs = set()
    for r in old_risks:
        a = row_by_path.get(normal_path(r["first_path"]))
        b = row_by_path.get(normal_path(r["second_path"]))
        if a is None or b is None:
            raise ValueError("Step 14 risk-pair image not found in manifest / alias map")
        if a == b:
            continue
        mapped_risk_pairs.add(tuple(sorted((a, b))))
    if not mapped_risk_pairs.issubset(included_edges):
        raise ValueError("Step 11 candidate list does not cover all Step 14 flagged pairs")

    old_crossing_edges = sum(
        image_rows[a]["split"] != image_rows[b]["split"]
        for a, b in included_edges
    )
    for a, b in sorted(included_edges):
        dsu.union(a, b)

    groups_by_cls: dict[str, list[list[int]]] = defaultdict(list)
    components: dict[tuple[str, int], list[int]] = defaultdict(list)
    for i, row in enumerate(image_rows):
        components[(row["class_name"], dsu.find(i))].append(i)
    for (cls, _), group in components.items():
        groups_by_cls[cls].append(group)

    assignment: dict[int, str] = {}
    results: dict[str, dict] = {}
    for cls in CLASSES:
        these = groups_by_cls.get(cls, [])
        if not these:
            raise ValueError(f"Class has no candidates: {cls}")
        mapping, stats = allocate(cls, these, sum(map(len, these)))
        assignment.update(mapping)
        results[cls] = stats

    post_crossing = sum(assignment[a] != assignment[b] for a, b in included_edges)
    hash_splits = defaultdict(set)
    for i, row in enumerate(image_rows):
        hash_splits[row["sha256"].strip().lower()].add(assignment[i])
    cross_sha = sum(len(splits) > 1 for splits in hash_splits.values())
    bad_groups = sum(len({assignment[i] for i in g}) != 1 for g in components.values())
    if post_crossing or cross_sha or bad_groups:
        raise RuntimeError("Internal split-integrity check failed. Do not use output.")

    valid_eval = all(v["eval_sufficient"] and v["train_at_least_65_percent"]
                     for v in results.values())
    status = ("SCREENED_PROVISIONAL_NOT_SOURCE_VERIFIED" if valid_eval
              else "BLOCKED_INSUFFICIENT_INDEPENDENT_EVALUATION_CANDIDATES")

    gid_for_root: dict[tuple[str, int], str] = {}
    for cls in CLASSES:
        class_groups = sorted(groups_by_cls[cls], key=lambda g: min(image_rows[i]["relative_path"] for i in g))
        for ix, group in enumerate(class_groups, 1):
            gid_for_root[(cls, dsu.find(group[0]))] = f"{cls.replace(' ', '_')}_safe_{ix:05d}"

    output = []
    for i, row in enumerate(image_rows):
        output.append({
            "class_name": row["class_name"],
            "dataset_source": row["dataset_source"],
            "relative_path": row["relative_path"],
            "sha256": row["sha256"],
            "group_id": gid_for_root[(row["class_name"], dsu.find(i))],
            "split": assignment[i],
            "review_status": status,
        })

    write_csv(output_file if valid_eval else blocked_file, output,
              ["class_name", "dataset_source", "relative_path", "sha256",
               "group_id", "split", "review_status"])
    # Remove stale SCREENED manifest if a re-run is now blocked; fail safely.
    if not valid_eval and output_file.exists():
        output_file.unlink()
    if valid_eval and blocked_file.exists():
        blocked_file.unlink()

    summary = {
        "status": status,
        "seed": SEED,
        "files_from_step14": len(image_rows),
        "step11_candidate_pairs_total": len(pair_rows),
        "candidate_pairs_between_included_images": len(included_edges),
        "candidate_pairs_excluded_yolo_or_unmatched": excluded_yolo_or_unmatched,
        "step14_candidate_edges_crossing_splits": old_crossing_edges,
        "step14_risk_rows_checked": len(old_risks),
        "step15_candidate_edges_crossing_splits": post_crossing,
        "step14_original_sha_aliases_mapped": mapped_audit_aliases,
        "class_results": results,
        "white_spot_yolo_crops_included": False,
        "source_verified": False,
        "labels_expert_verified": False,
        "other_classes_medium_similarity_pairs_audited": False,
        "limitations": [
            "Grouping all Step 11 similarity candidates is deliberately conservative; perceptual similarity does not prove identical leaves.",
            "Zero crossing pairs covers only the Step 11 screening list for included White Spot candidates, not every possible source duplicate.",
            "Other disease classes have only Step 14 strong-heuristic grouping; additional independent-source audit may be needed.",
            "Image source/plant IDs and expert diagnosis labels are unavailable; do not claim fully leakage-free independent testing.",
            "All original image files are unchanged; unapproved YOLO White Spot crops are excluded.",
        ],
        "training_handover_approved": False,
        "manifest_for_next_step": str(output_file if valid_eval else blocked_file),
    }
    reports.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("=" * 70)
    print("STEP 15 - CONSERVATIVE SIX-CLASS SPLIT SCREENING")
    print("=" * 70)
    print(f"Rows: {len(image_rows)} | Step 11 candidate edges relevant: {len(included_edges)}")
    print(f"Candidate edges crossing old splits: {old_crossing_edges}")
    print(f"Candidate edges crossing new splits: {post_crossing}")
    for cls in CLASSES:
        s = results[cls]
        label = "OK" if s["eval_sufficient"] else "INSUFFICIENT EVAL"
        print(f"{cls:<20}: train={s['train']:>4}, val={s['val']:>4}, "
              f"test={s['test']:>4}, groups={s['groups']:>4}, "
              f"largest={s['largest_conservative_group']:>4} [{label}]")
    print("Status:", status)
    print("Report:", summary_file)
    print("Manifest:", output_file if valid_eval else blocked_file)
    if not valid_eval:
        print("WARNING: Insufficient independent eval candidates under this conservative policy.")
        print("Do NOT treat BLOCKED_DIAGNOSTIC as an approved train/val/test dataset.")
        print("Original images preserved. More verified independent sources/review are needed.")
    else:
        print("SCREENED ONLY: not certified source independent or expert label validated.")
    print("No images changed/deleted. YOLO crops remain excluded.")
    return 0 if valid_eval else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Component01 directory, optional")
    opts = parser.parse_args()
    raise SystemExit(main(opts.root))
