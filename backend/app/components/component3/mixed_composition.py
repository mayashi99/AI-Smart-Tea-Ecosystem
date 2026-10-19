"""
Component 03: Mixed Tea Grade Composition & Granulometry Analysis Module.
Analyzes dry tea leaf samples to determine whether multiple tea grades
(e.g., BOP mixed with DUST or BOP 1A) have been blended or adulterated.
Combines YOLO11 classification distribution with particle granulometry (size distribution).
"""

import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import cv2
import numpy as np
from PIL import Image

from app.config import (
    ALLOWED_EXTENSIONS,
    TEA_GRADES_INFO,
)
from app.components.component3.predict import get_loaded_model
from app.components.component3.validator import validate_tea_sample_image

logger = logging.getLogger(__name__)

# Typical particle size profiles in pixels (normalized at 800px image scale)
GRADE_SIZE_PROFILES = {
    "DUST": {"label": "Very Fine (<0.5mm)", "mean_px": 8, "range": (2, 20)},
    "Fngs1": {"label": "Fine Fannings (~0.8mm)", "mean_px": 25, "range": (12, 45)},
    "FBOPF_Exsp": {"label": "Fine Tippy Fannings", "mean_px": 35, "range": (15, 65)},
    "FBOPF_sp": {"label": "Medium Tippy Fannings", "mean_px": 45, "range": (20, 80)},
    "FBOP": {"label": "Semi-Broken Flowery", "mean_px": 75, "range": (35, 130)},
    "BOP": {"label": "Medium Broken Leaf (~1.5mm)", "mean_px": 95, "range": (45, 170)},
    "BOP_1A": {"label": "Bold Clean Broken (~2.2mm)", "mean_px": 145, "range": (80, 240)},
    "BP": {"label": "Heavy Bold Broken (~2.8mm)", "mean_px": 190, "range": (110, 320)},
}


def extract_particle_granulometry(img_rgb: np.ndarray) -> Dict[str, Any]:
    """
    Extracts particle size distribution (granulometry) using OpenCV morphology.
    """
    h, w = img_rgb.shape[:2]
    scale = 800.0 / max(h, w)
    img_res = cv2.resize(img_rgb, (int(w * scale), int(h * scale)))
    gray = cv2.cvtColor(img_res, cv2.COLOR_RGB2GRAY)

    # Dynamic thresholding for presentation background
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    bg_thresh = min(220, max(130, int(np.percentile(gray, 85))))
    _, thresh = cv2.threshold(blur, bg_thresh, 255, cv2.THRESH_BINARY_INV)

    # Clean small noise
    kernel = np.ones((3, 3), np.uint8)
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    # Connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(opened)
    areas = stats[1:, cv2.CC_STAT_AREA]

    # Filter out background or large connected bed clumps (> 20000 px)
    particle_areas = [float(a) for a in areas if 4 < a < 25000]

    if not particle_areas:
        return {
            "total_particles": 0,
            "mean_particle_area": 0.0,
            "median_particle_area": 0.0,
            "size_std": 0.0,
            "cv_dispersion": 0.0,
            "fine_ratio": 0.0,
            "medium_ratio": 0.0,
            "bold_ratio": 0.0,
            "bimodal_index": 0.0,
        }

    arr_areas = np.array(particle_areas)
    mean_a = float(np.mean(arr_areas))
    std_a = float(np.std(arr_areas))
    median_a = float(np.median(arr_areas))
    cv_dispersion = round(std_a / max(1.0, mean_a), 3)

    # Bins: Fine (Dust/Fannings: < 35), Medium (BOP/FBOP: 35-150), Bold (BOP_1A/BP: > 150)
    total_count = len(particle_areas)
    fine_count = int(np.sum(arr_areas < 35))
    medium_count = int(np.sum((arr_areas >= 35) & (arr_areas <= 150)))
    bold_count = int(np.sum(arr_areas > 150))

    fine_pct = round((fine_count / total_count) * 100.0, 1)
    med_pct = round((medium_count / total_count) * 100.0, 1)
    bold_pct = round((bold_count / total_count) * 100.0, 1)

    # Bimodality coefficient: Pearson's skewness & kurtosis heuristic
    # A sample with mixed grades (e.g. coarse leaves mixed with fine dust) exhibits high bimodal index
    non_zero_bins = sum([fine_pct > 12.0, med_pct > 12.0, bold_pct > 12.0])
    bimodal_index = round(min(1.0, (cv_dispersion * 0.4) + (0.25 * max(0, non_zero_bins - 1))), 2)

    return {
        "total_particles": total_count,
        "mean_particle_area": round(mean_a, 1),
        "median_particle_area": round(median_a, 1),
        "size_std": round(std_a, 1),
        "cv_dispersion": cv_dispersion,
        "fine_particles_pct": fine_pct,
        "medium_particles_pct": med_pct,
        "bold_particles_pct": bold_pct,
        "bimodal_index": bimodal_index,
    }


def analyze_mixed_composition(
    image_bytes: bytes, filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Performs comprehensive Mixed Tea Grade Composition Analysis.
    Combines YOLO11 model probabilistic ranking with particle granulometry.
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

    # 3. Model inference for grade probabilities
    model, model_path = get_loaded_model()
    results = model.predict(source=pil_image, imgsz=224, verbose=False)
    if not results or len(results) == 0:
        raise RuntimeError("YOLO model returned no predictions for the provided image.")

    r = results[0]
    probs = getattr(r, "probs", None)
    if probs is None:
        raise RuntimeError("No classification probabilities returned by YOLO model.")

    # Post-inference OOD confidence check
    is_valid_ood, ood_error = validate_tea_sample_image(pil_image, probs=probs)
    if not is_valid_ood:
        raise ValueError(ood_error)

    # 4. Extract particle granulometry using OpenCV
    img_cv = np.array(pil_image)
    granulometry = extract_particle_granulometry(img_cv)

    # 5. Compute composition percentages
    # Extract model probability distribution
    raw_probs = probs.data.tolist()
    class_probs = {model.names[i]: float(raw_probs[i]) for i in range(len(model.names))}

    # Sort descending
    sorted_grades = sorted(class_probs.items(), key=lambda x: x[1], reverse=True)
    top_grade, top_conf = sorted_grades[0]
    second_grade, second_conf = sorted_grades[1]
    third_grade, third_conf = sorted_grades[2]

    FINE_GRADES = {"DUST", "Fngs1", "FBOPF_Exsp", "FBOPF_sp"}
    BROKEN_GRADES = {"BOP", "BOP_1A", "FBOP", "BP"}

    # Synthesize probability evidence with physical particle granulometry
    mix_factor = granulometry["bimodal_index"]
    fine_pct = granulometry.get("fine_particles_pct", 0.0)
    med_pct = granulometry.get("medium_particles_pct", 0.0)
    bold_pct = granulometry.get("bold_particles_pct", 0.0)
    coarse_pct = med_pct + bold_pct

    # Physical mixture detection across distinct standard sifting fractions
    # (e.g. mixture of coarse broken leaf with fine dust specks)
    is_physical_blend = (fine_pct >= 18.0 and coarse_pct >= 22.0) or (mix_factor >= 0.70 and fine_pct >= 14.0 and coarse_pct >= 18.0)

    if is_physical_blend:
        is_mixed = True
        if top_grade in FINE_GRADES:
            # Top grade is fine dust, but coarse broken particles are physically present
            candidate_broken = next((g for g, _ in sorted_grades if g in BROKEN_GRADES), "BOP")
            second_grade = candidate_broken
            pct_secondary = round(max(20.0, min(48.0, coarse_pct * 0.55)), 1)
            pct_primary = round(100.0 - pct_secondary, 1)
            pct_tertiary = 0.0
            pct_other = 0.0
            second_conf = class_probs.get(second_grade, 0.0)
        else:
            # Top grade is broken leaf, but fine dust particles are physically present
            candidate_fine = next((g for g, _ in sorted_grades if g in FINE_GRADES), "DUST")
            second_grade = candidate_fine
            pct_secondary = round(max(20.0, min(48.0, fine_pct * 0.85)), 1)
            pct_primary = round(100.0 - pct_secondary, 1)
            pct_tertiary = 0.0
            pct_other = 0.0
            second_conf = class_probs.get(second_grade, 0.0)
    else:
        # Granulometry is relatively unimodal; evaluate model confidence distribution
        sum_top3 = top_conf + second_conf + third_conf
        if sum_top3 > 0:
            raw_p1 = (top_conf / sum_top3)
            raw_p2 = (second_conf / sum_top3)
            raw_p3 = (third_conf / sum_top3)
        else:
            raw_p1, raw_p2, raw_p3 = 1.0, 0.0, 0.0

        # Adjust for physical particle mixture evidence
        adj_p2 = raw_p2 + (0.10 * mix_factor if second_conf > 0.08 else 0.0)
        adj_p3 = raw_p3 + (0.04 * mix_factor if third_conf > 0.04 else 0.0)
        adj_p1 = max(0.40, 1.0 - (adj_p2 + adj_p3))

        total_adj = adj_p1 + adj_p2 + adj_p3
        pct_primary = round((adj_p1 / total_adj) * 100.0, 1)
        pct_secondary = round((adj_p2 / total_adj) * 100.0, 1)
        pct_tertiary = round((adj_p3 / total_adj) * 100.0, 1)
        pct_other = max(0.0, round(100.0 - (pct_primary + pct_secondary + pct_tertiary), 1))

        # Determine whether the sample is mixed
        is_mixed = bool((pct_secondary >= 14.0) or (mix_factor >= 0.50 and pct_secondary >= 9.0))

    if not is_mixed:
        mix_severity = "pure_single_grade"
        mix_status_text = "Pure Single Grade"
        commercial_verdict = (
            f"Pure Single Grade: Sample exhibits high uniformity conforming to standard "
            f"{top_grade} ({TEA_GRADES_INFO.get(top_grade, {}).get('name', top_grade)}) particle cut. "
            f"No significant presence of foreign or off-grade tea particle cuts detected."
        )
    elif pct_secondary < 22.0:
        mix_severity = "minor_grade_variation"
        mix_status_text = "Minor Grade Variation Detected"
        commercial_verdict = (
            f"Minor Variation: Primarily {top_grade} ({pct_primary}%) with slight presence of "
            f"{second_grade} ({pct_secondary}%). Acceptable within commercial standard tolerance."
        )
    elif pct_secondary < 35.0:
        mix_severity = "moderately_mixed"
        mix_status_text = "Mixed Grade Detected"
        commercial_verdict = (
            f"Mixed Composition Alert: Significant presence of {second_grade} ({pct_secondary}%) "
            f"detected within {top_grade} ({pct_primary}%). Sample is a multi-grade blend or unevenly sifted cut."
        )
    else:
        mix_severity = "heavily_blended"
        mix_status_text = "High Degree Multi-Grade Blend"
        commercial_verdict = (
            f"High Admixture Warning: Substantial blending detected between {top_grade} ({pct_primary}%) "
            f"and {second_grade} ({pct_secondary}%). Does not conform to single-grade auction certification."
        )

    # Uniformity score (100 = completely pure single grade, 0 = highly adulterated)
    uniformity_score = round(max(10.0, min(100.0, (pct_primary * 1.1) - (mix_factor * 25.0))), 1)

    # Build detailed composition breakdown list
    composition_list = [
        {
            "rank": 1,
            "grade": top_grade,
            "full_name": TEA_GRADES_INFO.get(top_grade, {}).get("name", top_grade),
            "category": TEA_GRADES_INFO.get(top_grade, {}).get("category", "Tea Grade"),
            "percentage": pct_primary,
            "role": "Primary Base Grade",
            "model_confidence": round(top_conf, 4),
            "size_profile": GRADE_SIZE_PROFILES.get(top_grade, {}).get("label", "Standard"),
            "color_hex": "#059669",
        },
        {
            "rank": 2,
            "grade": second_grade,
            "full_name": TEA_GRADES_INFO.get(second_grade, {}).get("name", second_grade),
            "category": TEA_GRADES_INFO.get(second_grade, {}).get("category", "Tea Grade"),
            "percentage": pct_secondary,
            "role": "Secondary Mixed Grade" if is_mixed else "Trace Variation",
            "model_confidence": round(second_conf, 4),
            "size_profile": GRADE_SIZE_PROFILES.get(second_grade, {}).get("label", "Standard"),
            "color_hex": "#d97706" if is_mixed else "#64748b",
        },
    ]

    if pct_tertiary > 4.0:
        composition_list.append({
            "rank": 3,
            "grade": third_grade,
            "full_name": TEA_GRADES_INFO.get(third_grade, {}).get("name", third_grade),
            "category": TEA_GRADES_INFO.get(third_grade, {}).get("category", "Tea Grade"),
            "percentage": pct_tertiary,
            "role": "Tertiary Admixture",
            "model_confidence": round(third_conf, 4),
            "size_profile": GRADE_SIZE_PROFILES.get(third_grade, {}).get("label", "Standard"),
            "color_hex": "#8b5cf6",
        })

    if pct_other > 0:
        composition_list.append({
            "rank": 4,
            "grade": "Other / Off-grades",
            "full_name": "Undifferentiated Off-Grade Fragments",
            "category": "Off-Grade Siftings",
            "percentage": pct_other,
            "role": "Off-grade Particles",
            "model_confidence": 0.0,
            "size_profile": "Mixed Residuals",
            "color_hex": "#94a3b8",
        })

    return {
        "success": True,
        "component": "Component 03: Mixed Tea Grade Composition & Granulometry Analysis",
        "is_mixed": is_mixed,
        "mix_severity": mix_severity,
        "mix_status": mix_status_text,
        "uniformity_score": uniformity_score,  # 0 to 100
        "commercial_verdict": commercial_verdict,
        "primary_grade": {
            "grade": top_grade,
            "full_name": TEA_GRADES_INFO.get(top_grade, {}).get("name", top_grade),
            "percentage": pct_primary,
            "confidence": round(top_conf, 4),
        },
        "secondary_grade": {
            "grade": second_grade,
            "full_name": TEA_GRADES_INFO.get(second_grade, {}).get("name", second_grade),
            "percentage": pct_secondary,
            "confidence": round(second_conf, 4),
        } if pct_secondary > 5.0 else None,
        "composition_breakdown": composition_list,
        "granulometry_metrics": granulometry,
        "methodology": {
            "granulometric_segmentation": "OpenCV Morphological Connected Component Analysis",
            "model_probabilistic_inference": "Ultralytics YOLO11 Classification Probability Mapping",
            "compliance_standards": "Sri Lanka Tea Board (SLTB) / TRI Standard Tea Grade Classifications",
        },
    }
