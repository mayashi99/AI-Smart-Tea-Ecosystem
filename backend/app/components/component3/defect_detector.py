"""
Component 03: Unauthorized / Foreign Particle Material Detection Module.
Detects and pinpoints unauthorized foreign matter, stalks, coarse fibers,
discolored flakes, and extraneous particles in dry tea leaf samples.
Generates normalized and pixel bounding boxes along with an annotated preview image.
"""

import base64
import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import cv2
import numpy as np
from PIL import Image

from app.config import ALLOWED_EXTENSIONS
from app.components.component3.validator import validate_tea_sample_image

logger = logging.getLogger(__name__)

# Defect categories configuration
DEFECT_CONFIG = {
    "stalk": {
        "label": "Stalk / Stem",
        "description": "Woody elongated tea stem particle (fails clean leaf cut standard)",
        "color_bgr": (11, 158, 245),   # Amber/Orange in BGR (#f59e0b)
        "color_hex": "#f59e0b",
        "badge_bg": "#fef3c7",
        "badge_text": "#92400e",
    },
    "fiber": {
        "label": "Coarse Fiber",
        "description": "Loose coarse plant fiber strand",
        "color_bgr": (246, 92, 139),  # Purple/Violet in BGR (#8b5cf6)
        "color_hex": "#8b5cf6",
        "badge_bg": "#f3e8ff",
        "badge_text": "#6b21a8",
    },
    "pale_flake": {
        "label": "Discolored Pale Flake",
        "description": "Unfermented or chlorotic yellow/greenish leaf flake",
        "color_bgr": (8, 179, 234),   # Bright Gold/Yellow in BGR (#eab308)
        "color_hex": "#eab308",
        "badge_bg": "#fef9c3",
        "badge_text": "#854d0e",
    },
    "foreign_matter": {
        "label": "Foreign Non-Tea Matter",
        "description": "Extraneous inorganic matter, grit, stone, or non-tea debris",
        "color_bgr": (68, 68, 239),   # Red in BGR (#ef4444)
        "color_hex": "#ef4444",
        "badge_bg": "#fee2e2",
        "badge_text": "#991b1b",
    },
}


def classify_defect_particle(
    contour: np.ndarray,
    img_rgb: np.ndarray,
    img_gray: np.ndarray,
    mean_tea_brightness: float,
) -> Optional[Tuple[str, float]]:
    """
    Classifies a detected particle contour into a specific defect type.
    Uses cv2.minAreaRect to calculate true physical elongation / aspect ratio.
    Returns (defect_type, confidence) or None if normal tea particle.
    """
    area = cv2.contourArea(contour)
    if area < 14 or area > 18000:
        return None

    # True physical elongation regardless of particle rotation
    rect = cv2.minAreaRect(contour)
    (rx, ry), (rw, rh), angle = rect
    aspect_ratio = max(rw, rh) / max(1.0, min(rw, rh))

    # Mask for this particle
    mask = np.zeros(img_gray.shape, dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)

    particle_gray = img_gray[mask > 0]
    if len(particle_gray) == 0:
        return None

    particle_mean_b = float(np.mean(particle_gray))
    particle_rgb = img_rgb[mask > 0]
    r_mean = float(np.mean(particle_rgb[:, 0]))
    g_mean = float(np.mean(particle_rgb[:, 1]))
    b_mean = float(np.mean(particle_rgb[:, 2]))

    # 1. Coarse Fiber:
    # High perimeter-to-area ratio (thin curved strand) with moderate area
    perimeter = cv2.arcLength(contour, True)
    compactness = (perimeter * perimeter) / max(1.0, area)
    if (compactness > 24.0) and (aspect_ratio >= 1.9) and (area < 1200):
        conf = min(0.95, 0.76 + (compactness * 0.004))
        return "fiber", round(conf, 2)

    # 2. Stalk / Stem:
    # Elongated shape (true physical AR >= 2.0), significantly lighter than dark tea leaf,
    # and has a warm tan/yellowish-brown reflectance
    if (aspect_ratio >= 2.0) and (particle_mean_b > mean_tea_brightness + 12.0):
        conf = min(0.97, 0.78 + (aspect_ratio * 0.03) + ((particle_mean_b - mean_tea_brightness) * 0.003))
        return "stalk", round(conf, 2)

    # 3. Foreign Matter / Extraneous Inorganic Matter:
    # Extreme neutral brightness (white stone / quartz / glass grit > 200) or vivid synthetic color outlier (e.g. blue/cyan plastic)
    is_high_brightness_grit = particle_mean_b > 200.0
    is_synthetic_tint = (b_mean > r_mean + 20 and b_mean > 80)
    if is_high_brightness_grit or is_synthetic_tint:
        conf = min(0.98, 0.85 + (0.1 if is_high_brightness_grit else 0.05))
        return "foreign_matter", round(conf, 2)

    # 4. Discolored / Pale Flake:
    # Flake shape (AR < 2.0), but significantly higher brightness (unfermented) or yellowish shift
    if (aspect_ratio < 2.0) and (particle_mean_b > mean_tea_brightness + 20.0):
        conf = min(0.95, 0.75 + ((particle_mean_b - mean_tea_brightness) * 0.004))
        return "pale_flake", round(conf, 2)

    return None


def detect_unauthorized_particles(
    image_bytes: bytes, filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detects unauthorized foreign materials, stalks, coarse fibers, and discolored particles.
    Generates bounding boxes (normalized & pixel coordinates) and an annotated preview image.
    """
    # 1. Format validation
    if filename:
        ext = Path(filename).suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Invalid or corrupted image file: {str(e)}")

    # 2. Non-tea image validation
    is_valid, validation_error = validate_tea_sample_image(pil_image)
    if not is_valid:
        raise ValueError(validation_error)

    # Convert to OpenCV RGB image
    img_rgb = np.array(pil_image)
    orig_h, orig_w = img_rgb.shape[:2]

    # Resize image to normalized working resolution (e.g. max 900px) for consistent detection
    max_dim = 900
    scale = max_dim / max(orig_h, orig_w)
    work_w = int(orig_w * scale)
    work_h = int(orig_h * scale)
    img_work = cv2.resize(img_rgb, (work_w, work_h), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img_work, cv2.COLOR_RGB2GRAY)

    # Estimate background threshold
    bg_thresh = min(225, max(130, int(np.percentile(gray, 85))))
    _, fg_mask = cv2.threshold(gray, bg_thresh, 255, cv2.THRESH_BINARY_INV)

    # Compute mean brightness across normal dark tea particles
    dark_tea_mask = (fg_mask > 0) & (gray < 115)
    mean_tea_brightness = float(np.mean(gray[dark_tea_mask])) if np.sum(dark_tea_mask) > 100 else 75.0

    # Find candidate anomaly regions (brighter or discolored matter within foreground)
    anomaly_mask = (fg_mask > 0) & (gray > (mean_tea_brightness + 15.0))
    # Also check chromatic anomalies (yellow/green or red shifts)
    r_ch, g_ch, b_ch = img_work[:, :, 0], img_work[:, :, 1], img_work[:, :, 2]
    tint_anomaly = (fg_mask > 0) & (
        ((g_ch > r_ch * 1.05) & (g_ch > 60)) |
        ((r_ch > b_ch * 1.45) & (r_ch > 105))
    )
    combined_anomaly = (anomaly_mask | tint_anomaly).astype(np.uint8) * 255

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    clean_anomaly = cv2.morphologyEx(combined_anomaly, cv2.MORPH_OPEN, kernel, iterations=1)
    clean_anomaly = cv2.morphologyEx(clean_anomaly, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(clean_anomaly, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detected_defects: List[Dict[str, Any]] = []
    annotated_bgr = cv2.cvtColor(img_work, cv2.COLOR_RGB2BGR)

    box_id = 1
    total_defect_area = 0

    for c in contours:
        classification = classify_defect_particle(c, img_work, gray, mean_tea_brightness)
        if classification is None:
            continue

        defect_type, confidence = classification
        cfg = DEFECT_CONFIG.get(defect_type, DEFECT_CONFIG["stalk"])

        x, y, w, h = cv2.boundingRect(c)
        area_px = int(cv2.contourArea(c))
        aspect_ratio = round(max(w, h) / max(1.0, min(w, h)), 2)
        total_defect_area += area_px

        # Normalized coordinates relative to working image dimensions (0.0 to 1.0)
        norm_ymin = round(y / work_h, 4)
        norm_xmin = round(x / work_w, 4)
        norm_ymax = round((y + h) / work_h, 4)
        norm_xmax = round((x + w) / work_w, 4)

        # Scale coordinates back to original image dimensions
        orig_x = int(round(x / scale))
        orig_y = int(round(y / scale))
        orig_w_box = int(round(w / scale))
        orig_h_box = int(round(h / scale))

        defect_item = {
            "id": box_id,
            "defect_type": defect_type,
            "label": cfg["label"],
            "description": cfg["description"],
            "color_hex": cfg["color_hex"],
            "badge_bg": cfg["badge_bg"],
            "badge_text": cfg["badge_text"],
            "confidence": confidence,
            "confidence_percentage": round(confidence * 100.0, 1),
            "area_px": area_px,
            "aspect_ratio": aspect_ratio,
            "bbox_normalized": [norm_ymin, norm_xmin, norm_ymax, norm_xmax],
            "bbox_pixel": [orig_x, orig_y, orig_w_box, orig_h_box],
            "center": [round((norm_xmin + norm_xmax) / 2.0, 4), round((norm_ymin + norm_ymax) / 2.0, 4)],
        }
        detected_defects.append(defect_item)

        # Draw bounding box on annotated preview image
        bgr_color = cfg["color_bgr"]
        cv2.rectangle(annotated_bgr, (x, y), (x + w, y + h), bgr_color, 2)

        # Draw label tag
        tag_text = f"#{box_id} {cfg['label']} ({int(confidence*100)}%)"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.38
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(tag_text, font, font_scale, thickness)

        tag_y = max(18, y - 5)
        tag_x = max(2, x)
        cv2.rectangle(
            annotated_bgr,
            (tag_x, tag_y - th - 4),
            (tag_x + tw + 6, tag_y + 2),
            bgr_color,
            -1,
        )
        cv2.putText(
            annotated_bgr,
            tag_text,
            (tag_x + 3, tag_y - 2),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

        box_id += 1

    # Encode annotated image to Base64 JPEG
    success, buffer = cv2.imencode(".jpg", annotated_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if success:
        b64_str = base64.b64encode(buffer).decode("utf-8")
        annotated_image_data = f"data:image/jpeg;base64,{b64_str}"
    else:
        annotated_image_data = None

    # Count defects by category
    counts_by_type = {
        "stalk": 0,
        "fiber": 0,
        "pale_flake": 0,
        "foreign_matter": 0,
    }
    for d in detected_defects:
        dtype = d["defect_type"]
        if dtype in counts_by_type:
            counts_by_type[dtype] += 1

    total_defects = len(detected_defects)
    has_defects = total_defects > 0

    # Total sample foreground pixels
    fg_pixels = int(np.sum(fg_mask > 0))
    defect_density_pct = round((total_defect_area / max(1, fg_pixels)) * 100.0, 2)

    # Determine Purity / Cleanliness Grade
    if total_defects == 0:
        cleanliness_grade = "Grade A (Pristine / Clean Export Standard)"
        verdict = "Clean Sample: No unauthorized foreign particle materials, stalks, or coarse fibers detected."
    elif total_defects <= 3 and counts_by_type["foreign_matter"] == 0:
        cleanliness_grade = "Grade B (Commercial Quality / Minor Stalk Tolerance)"
        verdict = f"Commercial Quality: Detected {total_defects} minor particle defect(s). Conforms to domestic commercial bulk tolerance."
    else:
        cleanliness_grade = "Grade C (Substandard / High Foreign Matter)"
        verdict = f"Quality Defect Alert: Detected {total_defects} unauthorized particle(s) including {counts_by_type['stalk']} stalk(s) and {counts_by_type['foreign_matter']} foreign matter. Requires winnowing/sifting before packaging."

    return {
        "success": True,
        "component": "Component 03: Unauthorized Particle Material & Defect Detection",
        "has_unauthorized_particles": has_defects,
        "total_defects": total_defects,
        "defect_counts": counts_by_type,
        "defects": detected_defects,
        "defect_density_pct": defect_density_pct,
        "cleanliness_grade": cleanliness_grade,
        "commercial_verdict": verdict,
        "annotated_image": annotated_image_data,
        "image_dimensions": {"width": orig_w, "height": orig_h},
    }
