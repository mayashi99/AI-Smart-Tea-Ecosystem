"""
Component 03: Tea Leaf Sample Validator & Out-Of-Distribution (OOD) Detector.
Verifies whether an uploaded image is a genuine dry tea leaf sample
before executing classification inference or purity analysis.
Rejects non-tea images such as human portraits, faces, animals, vehicles,
indoor rooms, landscapes, and blank/text documents.
"""

import logging
from typing import Tuple, Optional, Any
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def validate_tea_sample_image(
    image: Image.Image,
    probs: Optional[Any] = None,
    min_confidence_threshold: float = 0.60,
    min_margin_threshold: float = 0.10,
) -> Tuple[bool, Optional[str]]:
    """
    Validates whether the given image contains genuine dry tea leaf particles.

    Performs multi-criteria checks:
    1. Human skin tone detection (YCbCr skin loci for portraits/faces/people).
    2. Unnatural non-tea color detection (sky/clothing blue, bright foliage green).
    3. Hasler-Süsstrunk overall colorfulness limit (black tea is predominantly achromatic/dark).
    4. Dark tea particle presence (sufficient dark granular foreground pixels).
    5. Model out-of-distribution (OOD) confidence & entropy checks (when probs provided).

    Args:
        image: PIL Image in RGB format.
        probs: Optional YOLO probs object from classification inference.
        min_confidence_threshold: Minimum top-1 confidence required (default 0.60).
        min_margin_threshold: Minimum difference between top-1 and top-2 confidence (default 0.10).

    Returns:
        (is_valid: bool, error_message: Optional[str])
    """
    try:
        rgb_img = image.convert("RGB")
    except Exception as e:
        return False, f"Invalid or unreadable image format: {str(e)}"

    # Resize to standard analysis resolution (224x224)
    sample_img = rgb_img.resize((224, 224))
    arr = np.array(sample_img, dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    total_pixels = 224 * 224

    # -------------------------------------------------------------
    # Check 1: Human skin tone detection (YCbCr color space)
    # -------------------------------------------------------------
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    skin_mask = (y > 70) & (cb >= 77) & (cb <= 127) & (cr >= 133) & (cr <= 173)
    skin_ratio = float(np.sum(skin_mask)) / total_pixels

    if skin_ratio > 0.075:
        logger.warning(f"[Validator] Rejected image: Human skin/portrait detected ({skin_ratio*100:.1f}%)")
        return (
            False,
            "Invalid image: Human portrait, face, or person detected. Please upload a genuine tea leaf sample image.",
        )

    # -------------------------------------------------------------
    # Check 2: Unnatural non-tea colors (Bright blue & bright green foliage)
    # -------------------------------------------------------------
    # Black tea never contains bright sky/clothing blue
    bright_blue = (b > 105) & (b > r + 20) & (b > g + 15)
    blue_ratio = float(np.sum(bright_blue)) / total_pixels
    if blue_ratio > 0.05:
        logger.warning(f"[Validator] Rejected image: Vivid blue detected ({blue_ratio*100:.1f}%)")
        return (
            False,
            "Invalid image: Unnatural colors (e.g. blue sky, clothing, or synthetic background) detected. Please upload an image of dry tea leaves.",
        )

    # Black tea is dried and processed; bright grass/garden greenery is not black tea
    bright_green = (g > 105) & (g > r + 25) & (g > b + 15)
    green_ratio = float(np.sum(bright_green)) / total_pixels
    if green_ratio > 0.08:
        logger.warning(f"[Validator] Rejected image: Outdoor greenery detected ({green_ratio*100:.1f}%)")
        return (
            False,
            "Invalid image: Fresh outdoor greenery or foliage detected. Please upload an image of dry processed tea leaves.",
        )

    # -------------------------------------------------------------
    # Check 3: Hasler & Süsstrunk Colorfulness Metric
    # -------------------------------------------------------------
    rg = np.abs(r - g)
    yb = np.abs(0.5 * (r + g) - b)
    std_rg = float(np.std(rg))
    mean_rg = float(np.mean(rg))
    std_yb = float(np.std(yb))
    mean_yb = float(np.mean(yb))
    colorfulness = float(np.sqrt(std_rg**2 + std_yb**2) + 0.3 * np.sqrt(mean_rg**2 + mean_yb**2))

    if colorfulness > 26.0:
        logger.warning(f"[Validator] Rejected image: High colorfulness ({colorfulness:.1f})")
        return (
            False,
            "Invalid image: Color variation is too high for dry tea leaves. Please upload a clear photo of a tea sample on a neutral surface.",
        )

    # -------------------------------------------------------------
    # Check 4: Dark tea particle presence
    # -------------------------------------------------------------
    # Black tea particles are dark (typically R, G, B < 135)
    dark_particles = (r < 135) & (g < 135) & (b < 135)
    dark_ratio = float(np.sum(dark_particles)) / total_pixels

    if dark_ratio < 0.025:
        logger.warning(f"[Validator] Rejected image: Insufficient dark particles ({dark_ratio*100:.2f}%)")
        return (
            False,
            "Invalid image: No tea leaf particles detected in the sample. Please ensure dry tea leaves are clearly visible.",
        )

    # -------------------------------------------------------------
    # Check 5: Model Out-Of-Distribution (OOD) Confidence & Margin
    # -------------------------------------------------------------
    if probs is not None:
        top1_conf = float(probs.top1conf)
        if top1_conf < min_confidence_threshold:
            logger.warning(
                f"[Validator] Rejected image: Low model confidence ({top1_conf*100:.1f}% < {min_confidence_threshold*100:.1f}%)"
            )
            return (
                False,
                f"Invalid image: The uploaded sample does not match any recognized tea grade (Model confidence: {top1_conf*100:.1f}%). Please upload a valid tea grade image.",
            )

        if hasattr(probs, "top5") and len(probs.top5) >= 2:
            c1 = float(probs.top5conf[0])
            c2 = float(probs.top5conf[1])
            # If the margin between #1 and #2 is very small and confidence is modest
            if (c1 - c2 < min_margin_threshold) and (c1 < 0.75):
                logger.warning(
                    f"[Validator] Rejected image: Ambiguous classification margin ({c1*100:.1f}% vs {c2*100:.1f}%)"
                )
                return (
                    False,
                    f"Invalid image: Classification is highly uncertain ({c1*100:.1f}% vs {c2*100:.1f}%). The image does not appear to be a standard tea grade sample.",
                )

    return True, None
