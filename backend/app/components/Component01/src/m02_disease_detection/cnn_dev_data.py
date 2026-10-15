"""CNN data-loading interface for Step 16's DEVELOPMENT-ONLY six-class dataset.

Intended for model-code smoke tests while source-independent research
holdouts are pending; NEVER use dev_val/dev_test metrics as final results.

The same transforms and loader interface can be reused in future training
code after a final independently validated manifest is prepared, but the
manifest must be explicitly passed and its status checked.
"""
from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path

from PIL import Image, ImageOps
import torch
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import transforms


class TeaDiseaseDevDataset(Dataset):
    """Images remain on disk. Always returns (RGB tensor, integer class)."""

    def __init__(self, component_root: Path, split: str, manifest: str = "data/processed/image_split_manifest_DEV_ONLY.csv", image_size: int = 224):
        self.root = Path(component_root).resolve()
        self.split = split
        if split not in {"dev_train", "dev_val", "dev_test"}:
            raise ValueError(f"Expected dev-only split, not {split!r}")
        manifest_path = self.root / manifest
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Run Step 16 first: {manifest_path}")
        status_path = self.root / "outputs/reports/image_step16_development_summary.json"
        report = json.loads(status_path.read_text(encoding="utf-8"))
        if report.get("status") != "DEVELOPMENT_ONLY_NOT_FOR_FINAL_EVALUATION":
            raise ValueError("Incorrect/unsupported development manifest status")
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            self.samples = [r for r in reader if r.get("split") == split]
        if not self.samples:
            raise ValueError(f"Empty development split: {split}")
        self.labels = [int(r["class_index"]) for r in self.samples]
        standard_normalize = transforms.Normalize(
            mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)
        )
        if split == "dev_train":
            self.transform = transforms.Compose([
                transforms.RandomResizedCrop(image_size, scale=(0.80, 1.00)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomVerticalFlip(p=0.25),
                transforms.RandomRotation(degrees=12),
                transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.10),
                transforms.ToTensor(),
                standard_normalize,
            ])
        else:
            self.transform = transforms.Compose([
                transforms.Resize((image_size, image_size)),
                transforms.ToTensor(),
                standard_normalize,
            ])

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        sample = self.samples[index]
        path = (self.root / sample["relative_path"]).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Unsafe image path: {path}")
        with Image.open(path) as image:
            rgb = ImageOps.exif_transpose(image).convert("RGB")
            pixels = self.transform(rgb)
        return pixels, self.labels[index]


def build_dev_loaders(component_root: Path, batch_size: int = 16, num_workers: int = 0, seed: int = 42):
    """Build stratified-ish training sampler, non-shuffled dev validation/test.

    Returning a WeightedRandomSampler does not fabricate new White Spot
    images: it repeats the small class more often within training, so avoid
    treating the additional draws as independent information.
    """
    root = Path(component_root)
    datasets = {s: TeaDiseaseDevDataset(root, s) for s in ("dev_train", "dev_val", "dev_test")}
    counts = Counter(datasets["dev_train"].labels)
    weights = [1.0 / counts[label] for label in datasets["dev_train"].labels]
    sampler = WeightedRandomSampler(
        weights=weights,
        num_samples=len(datasets["dev_train"]),
        replacement=True,
        generator=torch.Generator().manual_seed(seed),
    )
    loaders = {
        "dev_train": DataLoader(datasets["dev_train"], batch_size=batch_size,
                                sampler=sampler, num_workers=num_workers,
                                generator=torch.Generator().manual_seed(seed)),
        "dev_val": DataLoader(datasets["dev_val"], batch_size=batch_size,
                              shuffle=False, num_workers=num_workers),
        "dev_test": DataLoader(datasets["dev_test"], batch_size=batch_size,
                               shuffle=False, num_workers=num_workers),
    }
    return loaders, datasets
