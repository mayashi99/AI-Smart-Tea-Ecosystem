import io
import logging
from pathlib import Path
from typing import Dict, Optional, Any
import numpy as np
from PIL import Image

from app.config import ALLOWED_EXTENSIONS
from app.components.component3.validator import validate_tea_sample_image

logger = logging.getLogger(__name__)


def analyze_tea_purity(image_bytes: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Experimental Computer Vision Baseline for Tea Purity & Foreign-Material Homogeneity Analysis.

    IMPORTANT ARCHITECTURAL CONSTRAINTS:
    1. Ground-truth purity labels and foreign-material annotations do NOT exist in the current dataset.
    2. Therefore, a validated commercial purity percentage CANNOT be generated.
    3. We DO NOT fabricate or hardcode purity percentages.
    4. We DO NOT use YOLO grade-classification confidence as a purity measure.
    5. This module computes objective, reproducible visual homogeneity metrics (color consistency,
       chromatic anomaly ratio, and foreground distribution) labeled strictly as EXPERIMENTAL.
    """
    # 1. Validate image extension
    if filename:
        ext = Path(filename).suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

    # 2. Decode image
    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Invalid or corrupted image file: {str(e)}")

    # 3. Validate that image is a genuine tea sample
    is_valid, validation_error = validate_tea_sample_image(pil_image)
    if not is_valid:
        raise ValueError(validation_error)

    # Resize image for consistent, efficient visual analysis
    analysis_img = pil_image.resize((448, 448))
    img_array = np.array(analysis_img, dtype=np.float32)

    # 3. Separate sample particles (foreground) from presentation background
    # Standard tea sample images are photographed on light/white trays or paper backgrounds
    r, g, b = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]
    grayscale = 0.299 * r + 0.587 * g + 0.114 * b

    # Estimate background threshold dynamically
    bg_threshold = min(220.0, max(140.0, float(np.percentile(grayscale, 85))))
    foreground_mask = grayscale < bg_threshold

    total_pixels = analysis_img.width * analysis_img.height
    foreground_pixels = int(np.sum(foreground_mask))

    if foreground_pixels < 100:
        return {
            "success": True,
            "component": "Component 03: Purity Analysis Module",
            "status": "insufficient_sample",
            "validated_purity_percentage": None,
            "is_validated": False,
            "message": "Insufficient tea leaf particles detected in sample. Please ensure tea leaves are clearly visible.",
            "metrics": None,
        }

    # 4. Compute objective color uniformity metrics across tea particles
    fg_r = r[foreground_mask]
    fg_g = g[foreground_mask]
    fg_b = b[foreground_mask]
    fg_gray = grayscale[foreground_mask]

    # Standard deviation of brightness and RGB channels (lower std = more uniform particle appearance)
    std_brightness = float(np.std(fg_gray))
    std_r = float(np.std(fg_r))
    std_g = float(np.std(fg_g))
    std_b = float(np.std(fg_b))
    mean_brightness = float(np.mean(fg_gray))

    # Standard black tea particle ranges (typically dark, low brightness < 100)
    # Off-color anomaly detection: particles with unusually high brightness or green/yellow tint
    # (e.g. stalks, coarse fibers, yellow flakes, extraneous non-leaf particles)
    anomaly_bright_mask = (fg_gray > (mean_brightness + 1.8 * std_brightness)) & (fg_gray > 90.0)
    # Check green/yellow shift: (G > R and G > 70) or significant red tint
    anomaly_tint_mask = ((fg_g > fg_r * 1.05) & (fg_g > 60.0)) | ((fg_r > fg_b * 1.5) & (fg_r > 120.0))
    anomaly_combined = anomaly_bright_mask | anomaly_tint_mask

    anomaly_count = int(np.sum(anomaly_combined))
    anomaly_ratio = float(anomaly_count / foreground_pixels)
    anomaly_percentage = round(anomaly_ratio * 100.0, 2)

    # Normalized color uniformity index (0 to 100, purely a descriptive visual statistic)
    # Ideal homogeneous black tea has lower standard deviation across foreground particles
    raw_uniformity = max(0.0, min(100.0, 100.0 - (std_brightness * 1.4)))
    color_uniformity_index = round(float(raw_uniformity), 1)

    foreground_coverage_pct = round((foreground_pixels / total_pixels) * 100.0, 1)

    return {
        "success": True,
        "component": "Component 03: AI-Powered Tea Grade, Purity, Mixed Composition & Defect Analysis",
        "module": "Purity Analysis (Experimental Baseline)",
        "ground_truth_purity_available": False,
        "validated_purity_percentage": None,  # NEVER fabricated
        "is_validated": False,
        "status": "experimental_baseline",
        "transparency_notice": (
            "A validated commercial purity percentage cannot be generated because ground-truth purity labels, "
            "foreign-material annotations, and certified laboratory chemical purity measurements are absent "
            "from the current dataset. The metrics below represent experimental computer-vision color and "
            "texture homogeneity measurements only."
        ),
        "experimental_metrics": {
            "color_uniformity_index": color_uniformity_index,  # 0 to 100
            "chromatic_anomaly_ratio": anomaly_ratio,
            "chromatic_anomaly_percentage": anomaly_percentage,  # estimated off-color / stalk-like particles %
            "particle_coverage_percentage": foreground_coverage_pct,
            "mean_particle_brightness": round(mean_brightness, 1),
            "particle_brightness_std": round(std_brightness, 1),
        },
        "audit_findings": {
            "dataset_purity_labels": "Missing (Dataset only contains 8 discrete grade category folders)",
            "foreign_material_annotations": "Missing (No bounding boxes or masks for stalks, fiber, or stone)",
            "classification_confidence_reused": False,  # Strict compliance: confidence is NOT purity
            "model_architecture": "YOLO11 Classification only (requires dedicated purity regression model for commercial certification)",
        },
        "next_steps_for_certification": [
            "Collect dry-tea samples with certified laboratory purity indices.",
            "Annotate foreign materials (stalks, coarse fiber, extraneous matter) with bounding boxes or segmentation masks.",
            "Train a multi-spectral or specialized object-detection/segmentation model for physical purity validation.",
        ],
    }
