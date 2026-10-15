"""Step 17: five-class CNN model DEVELOPMENT training (never final evaluation).

Run from repository root (Windows):
    python backend/app/components/Component01/src/m02_disease_detection/17_train_cnn_dev.py --mode smoke

After the smoke test, use --mode full for developmental training. Even full
training here is DEVELOPMENT_ONLY, because Step 16 holdouts have unresolved
source independence / White Spot imbalance. The final research evaluation must
use a separately approved independent evaluation set in a later step.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import time

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
import torch
from torch import nn
from torch.optim import AdamW
from torchvision import models

from cnn_dev_data import build_dev_loaders

DEV_STATUS = "DEVELOPMENT_ONLY_NOT_FOR_FINAL_EVALUATION"
ARCHITECTURES = (
    "mobilenet_v3_small", "efficientnet_b0", "resnet18", "densenet121"
)


def component_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--mode", choices=("smoke", "full"), default="smoke")
    p.add_argument("--architectures", nargs="+", choices=ARCHITECTURES, default=None,
                   help="Architectures to train; smoke defaults to MobileNetV3 Small, full defaults to all four")
    p.add_argument("--epochs", type=int, default=None, help="Smoke defaults 1; full defaults 20")
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--num-workers", type=int, default=0, help="0 is safer on Windows")
    p.add_argument("--cpu-threads", type=int, default=4)
    p.add_argument("--learning-rate", type=float, default=None)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--patience", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--weights", choices=("auto", "imagenet", "random"), default="auto",
                   help="auto: random for smoke; ImageNet pretrained for full")
    p.add_argument("--max-train-batches", type=int, default=None,
                   help="Intended for smoke/dev debugging only")
    p.add_argument("--max-val-batches", type=int, default=None,
                   help="Intended for smoke/dev debugging only")
    p.add_argument("--run-id", default=None, help="Optional unique alphanumeric run ID")
    p.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return p.parse_args()


def make_model(architecture: str, num_classes: int, pretrained: bool) -> nn.Module:
    """Instantiate torchvision models using an explicit output class count."""
    if architecture == "mobilenet_v3_small":
        w = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        model = models.mobilenet_v3_small(weights=w)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
    elif architecture == "efficientnet_b0":
        w = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
        model = models.efficientnet_b0(weights=w)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
    elif architecture == "resnet18":
        w = models.ResNet18_Weights.DEFAULT if pretrained else None
        model = models.resnet18(weights=w)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
    elif architecture == "densenet121":
        w = models.DenseNet121_Weights.DEFAULT if pretrained else None
        model = models.densenet121(weights=w)
        model.classifier = nn.Linear(model.classifier.in_features, num_classes)
    else:
        raise ValueError(f"Unsupported model architecture: {architecture}")
    return model


def evaluate(model: nn.Module, loader, device: torch.device, max_batches: int | None,
             classes: list[str]) -> dict:
    model.eval()
    true, pred = [], []
    total_loss, total_n = 0.0, 0
    criterion = nn.CrossEntropyLoss()
    with torch.inference_mode():
        for index, (images, targets) in enumerate(loader):
            if max_batches is not None and index >= max_batches:
                break
            images = images.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True)
            logits = model(images)
            loss = criterion(logits, targets)
            n = targets.size(0)
            total_loss += float(loss.item()) * n
            total_n += n
            true.extend(targets.cpu().tolist())
            pred.extend(logits.argmax(dim=1).cpu().tolist())
    if not total_n:
        raise RuntimeError("No validation batches were evaluated")
    labels = list(range(len(classes)))
    precision, recall, f1, supports = precision_recall_fscore_support(
        true, pred, labels=labels, average=None, zero_division=0
    )
    return {
        "loss": total_loss / total_n,
        "accuracy": float(accuracy_score(true, pred)),
        "macro_f1": float(f1_score(true, pred, labels=labels, average="macro", zero_division=0)),
        "num_images": total_n,
        "per_class": {
            cls: {
                "precision": float(precision[i]), "recall": float(recall[i]),
                "f1": float(f1[i]), "support": int(supports[i]),
            }
            for i, cls in enumerate(classes)
        },
    }


def train_epoch(model: nn.Module, loader, optimizer, device: torch.device,
                max_batches: int | None) -> dict:
    model.train()
    loss_fn = nn.CrossEntropyLoss()  # Step 16 already balances via WeightedRandomSampler.
    total_loss, total_correct, total_n = 0.0, 0, 0
    for index, (images, targets) in enumerate(loader):
        if max_batches is not None and index >= max_batches:
            break
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        logits = model(images)
        loss = loss_fn(logits, targets)
        if not torch.isfinite(loss):
            raise RuntimeError("Non-finite training loss: inspect data and learning rate")
        loss.backward()
        optimizer.step()
        n = targets.size(0)
        total_n += n
        total_loss += float(loss.item()) * n
        total_correct += int((logits.argmax(dim=1) == targets).sum().item())
    if not total_n:
        raise RuntimeError("No training batches were processed")
    return {"loss": total_loss / total_n, "accuracy": total_correct / total_n,
            "num_images": total_n}


def save_csv(file: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("Expected at least one history row")
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_step16(root: Path) -> tuple[dict, dict, str]:
    summary_path = root / "outputs/reports/image_step16_development_summary.json"
    mapping_path = root / "data/processed/cnn_class_mapping.json"
    manifest_path = root / "data/processed/image_split_manifest_DEV_ONLY.csv"
    for path in (summary_path, mapping_path, manifest_path):
        if not path.is_file():
            raise FileNotFoundError(f"Run Step 16 before training; missing {path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if summary.get("status") != DEV_STATUS:
        raise ValueError("Unexpected development-only dataset status")
    if summary.get("final_research_evaluation_permitted") is not False:
        raise ValueError("Step 16 report does not prohibit scientific final evaluation")
    if summary.get("training_handover_approved") is not False:
        raise ValueError("Unexpected training handover approval state")
    if summary.get("prototype_num_classes") != 5 or summary.get("white_spot_deferred") is not True:
        raise ValueError("Run Step 19 five-class transition before training")
    if mapping.get("status") != DEV_STATUS or mapping.get("num_classes") != 5:
        raise ValueError("Unexpected class mapping status or class count")
    expected = [mapping["idx_to_class"][str(i)] for i in range(5)]
    if [mapping["class_to_idx"].get(c) for c in expected] != list(range(5)):
        raise ValueError("Class mapping indices do not match")
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return summary, mapping, manifest_sha


def main() -> None:
    args = parse_args()
    if args.batch_size < 2:
        raise ValueError("--batch-size must be >=2 for MobileNet/EfficientNet BatchNorm")
    if args.num_workers < 0 or args.cpu_threads < 1 or args.patience < 1:
        raise ValueError("Workers, CPU threads, patience must be non-negative/positive")
    root = component_root()
    summary, mapping, manifest_sha = read_step16(root)
    architectures = args.architectures or (
        ["mobilenet_v3_small"] if args.mode == "smoke" else list(ARCHITECTURES)
    )
    epochs = args.epochs if args.epochs is not None else (1 if args.mode == "smoke" else 20)
    if epochs < 1:
        raise ValueError("--epochs must be >=1")
    pretrained = ((args.mode == "full") if args.weights == "auto" else args.weights == "imagenet")
    lr = args.learning_rate if args.learning_rate is not None else (1e-4 if pretrained else 3e-4)
    if not math.isfinite(lr) or lr <= 0:
        raise ValueError("--learning-rate must be finite and positive")
    max_train = args.max_train_batches if args.max_train_batches is not None else (2 if args.mode == "smoke" else None)
    max_val = args.max_val_batches if args.max_val_batches is not None else (2 if args.mode == "smoke" else None)
    if any(n is not None and n < 1 for n in (max_train, max_val)):
        raise ValueError("Maximum batch counts must be >=1")
    # Truncated validation is only meaningful as a smoke check, never an actual model-selection run.
    if args.mode == "full" and (max_train is not None or max_val is not None):
        raise ValueError("Full mode does not allow --max-*-batches; use smoke mode")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but no CUDA GPU / CUDA PyTorch available")
    device = torch.device("cuda" if (args.device == "cuda" or args.device == "auto" and torch.cuda.is_available()) else "cpu")
    torch.set_num_threads(args.cpu_threads)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = False

    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", run_id):
        raise ValueError("--run-id must be 1-64 characters: letters, digits, _ or -")
    model_dir = root / "models/image/development_only" / f"step17_{run_id}"
    report_dir = root / "outputs/reports/cnn_dev_training" / f"step17_{run_id}"
    if model_dir.exists() or report_dir.exists():
        raise FileExistsError(f"Step 17 run already exists: {run_id}; select another --run-id")
    model_dir.mkdir(parents=True, exist_ok=False)
    report_dir.mkdir(parents=True, exist_ok=False)
    loaders, datasets = build_dev_loaders(root, batch_size=args.batch_size, num_workers=args.num_workers, seed=args.seed)
    classes = [mapping["idx_to_class"][str(i)] for i in range(5)]
    counts = {split: len(dataset) for split, dataset in datasets.items()}
    info = {
        "status": DEV_STATUS,
        "final_research_evaluation_permitted": False,
        "mode": args.mode,
        "run_id": run_id,
        "device": str(device),
        "epochs_requested": epochs,
        "batch_size": args.batch_size,
        "seed": args.seed,
        "weights_source": "imagenet" if pretrained else "random_initialization",
        "architectures": architectures,
        "class_names": classes,
        "manifest_sha256": manifest_sha,
        "dataset_sizes": counts,
        "prototype_scope": "five classes; white spot deferred",
        "source_independent_evaluation_verified": False,
        "train_sampling": "WeightedRandomSampler with replacement, unweighted cross-entropy; class repeats are NOT new images",
        "train_only_augmentation": True,
        "dev_test_used_for_selection": False,
        "torch_version": torch.__version__,
        "results": {},
    }
    (report_dir / "config.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print("=" * 76)
    print("STEP 17 - CNN DEVELOPMENT TRAINING - NOT FINAL RESEARCH EVALUATION")
    print("=" * 76)
    print(f"Mode: {args.mode}; device: {device}; weights: {info['weights_source']}")
    print(f"Dataset train={counts['dev_train']} val={counts['dev_val']} (dev_test never evaluated here)")
    print(f"Architectures: {', '.join(architectures)}")
    print(f"Run report dir: {report_dir}", flush=True)
    if pretrained:
        print("NOTE: torchvision may download ImageNet weights on first use (internet required).", flush=True)

    for architecture in architectures:
        torch.manual_seed(args.seed)  # match reproducible initial RNG by model
        print(f"\n[{architecture}] creating model...", flush=True)
        try:
            model = make_model(architecture, num_classes=len(classes), pretrained=pretrained)
        except Exception as exc:
            if pretrained:
                raise RuntimeError(
                    f"Could not load ImageNet weights for {architecture}. "
                    "Connect to the internet once, or explicitly use --weights random "
                    "for a non-pretrained experiment. No silent fallback."
                ) from exc
            raise
        model = model.to(device)
        optimizer = AdamW(model.parameters(), lr=lr, weight_decay=args.weight_decay)
        best_score, best_epoch, stale = -1.0, None, 0
        history: list[dict] = []
        best_path = model_dir / f"{architecture}_best_dev_only.pt"
        for epoch in range(1, epochs + 1):
            tick = time.perf_counter()
            train = train_epoch(model, loaders["dev_train"], optimizer, device, max_train)
            valid = evaluate(model, loaders["dev_val"], device, max_val, classes)
            row = {
                "epoch": epoch, "train_loss": round(train["loss"], 6),
                "train_accuracy": round(train["accuracy"], 6),
                "dev_val_loss": round(valid["loss"], 6),
                "dev_val_accuracy": round(valid["accuracy"], 6),
                "dev_val_macro_f1": round(valid["macro_f1"], 6),
                "dev_val_images": valid["num_images"],
                "seconds": round(time.perf_counter() - tick, 2),
            }
            history.append(row)
            print(f"  epoch {epoch:02}/{epochs:02} | train loss={row['train_loss']:.4f} "
                  f"| dev val macro F1={row['dev_val_macro_f1']:.4f} "
                  f"| {row['seconds']:.1f}s", flush=True)
            score = valid["macro_f1"]
            if score > best_score + 1e-10:
                best_score, best_epoch, stale = score, epoch, 0
                checkpoint = {
                    "model_architecture": architecture,
                    "model_state_dict": {name: tensor.detach().cpu() for name, tensor in model.state_dict().items()},
                    "num_classes": len(classes),
                    "class_names": classes,
                    "class_to_idx": mapping["class_to_idx"],
                    "image_size": int(mapping.get("image_size", 224)),
                    "normalization": {
                        "mean": [0.485, 0.456, 0.406],
                        "std": [0.229, 0.224, 0.225],
                    },
                    "epoch": epoch,
                    "dev_val_macro_f1": score,
                    "training_mode": args.mode,
                    "training_weights": info["weights_source"],
                    "manifest_sha256": manifest_sha,
                    "dataset_status": DEV_STATUS,
                    "final_research_evaluation_permitted": False,
                }
                torch.save(checkpoint, best_path)
            else:
                stale += 1
            if args.mode == "full" and stale >= args.patience:
                print(f"  Early stopping: dev_val macro F1 not improved for {args.patience} epochs", flush=True)
                break
        save_csv(report_dir / f"{architecture}_history.csv", history)
        # 'last validation' is not necessarily the selected epoch; best score is tracked separately.
        result = {
            "best_epoch": best_epoch,
            "best_dev_val_macro_f1": best_score,
            "dev_val_metrics_last_epoch": valid,
            "epochs_completed": len(history),
            "checkpoint": best_path.relative_to(root).as_posix(),
            "scientific_validity": "DEV_ONLY_DIAGNOSTIC_NOT_FOR_RESEARCH_PERFORMANCE_CLAIMS",
        }
        info["results"][architecture] = result
        (report_dir / f"{architecture}_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[{architecture}] checkpoint saved: {best_path}", flush=True)
        (report_dir / "config.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (report_dir / "run_summary.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print("\nCompleted Step 17 DEVELOPMENT run.")
    print(f"Model folder: {model_dir}")
    print(f"Reports: {report_dir}")
    print("IMPORTANT: DEV VAL scores and checkpoints are NOT final scientific evaluation.")


if __name__ == "__main__":
    main()
