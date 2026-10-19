"""
Component 03: Demo Tea Sample Images Generator.
Creates realistic sample images for:
1. Pure Single Grade BOP Sample
2. Mixed Tea Grade Sample (BOP mixed with DUST & Fannings)
3. Contaminated Sample with Unauthorized Particles (Stalks, Fibers & Pale Flakes)
Allows immediate one-click testing of Mixed Composition and Particle Bounding Box features.
"""

from pathlib import Path
from typing import Dict, List, Any
import cv2
import numpy as np

DEMO_DIR = Path(__file__).resolve().parent / "demo_samples"
DEMO_DIR.mkdir(parents=True, exist_ok=True)


def generate_pure_bop_sample(output_path: Path) -> Path:
    """
    Generates a uniform BOP broken leaf sample on a clean white tray.
    """
    img = np.full((700, 700, 3), 242, dtype=np.uint8)
    np.random.seed(101)

    # Add thousands of uniform dark black/brown broken particles
    for _ in range(1200):
        cx = np.random.randint(60, 640)
        cy = np.random.randint(60, 640)
        radius = np.random.randint(3, 7)
        # Deep black-brown Ceylon tea color
        color = (
            np.random.randint(18, 38),
            np.random.randint(22, 44),
            np.random.randint(28, 52),
        )
        # Irregular shape
        axes = (radius, int(radius * np.random.uniform(0.6, 1.4)))
        angle = np.random.randint(0, 180)
        cv2.ellipse(img, (cx, cy), axes, angle, 0, 360, color, -1)

    cv2.imwrite(str(output_path), img)
    return output_path


def generate_mixed_bop_dust_sample(output_path: Path) -> Path:
    """
    Generates a mixed tea sample containing both medium BOP broken leaves
    and an abundant admixture of fine DUST / fannings powder.
    """
    img = np.full((700, 700, 3), 240, dtype=np.uint8)
    np.random.seed(202)

    # 1. Medium BOP broken particles
    for _ in range(650):
        cx = np.random.randint(70, 630)
        cy = np.random.randint(70, 630)
        radius = np.random.randint(4, 9)
        color = (
            np.random.randint(20, 42),
            np.random.randint(25, 48),
            np.random.randint(32, 58),
        )
        axes = (radius, int(radius * np.random.uniform(0.7, 1.3)))
        angle = np.random.randint(0, 180)
        cv2.ellipse(img, (cx, cy), axes, angle, 0, 360, color, -1)

    # 2. Heavy admixture of fine DUST / micro-fannings (dense small specks)
    for _ in range(1600):
        cx = np.random.randint(60, 640)
        cy = np.random.randint(60, 640)
        radius = np.random.randint(1, 3)
        color = (
            np.random.randint(15, 30),
            np.random.randint(18, 35),
            np.random.randint(22, 40),
        )
        cv2.circle(img, (cx, cy), radius, color, -1)

    cv2.imwrite(str(output_path), img)
    return output_path


def generate_defective_stalks_sample(output_path: Path) -> Path:
    """
    Generates a tea sample containing unauthorized particle materials:
    - 3 Stalks/Stems (elongated tan/yellowish woody pieces)
    - 2 Coarse Fibers
    - 2 Discolored Pale Flakes
    - 1 Foreign Matter particle
    """
    img = np.full((700, 700, 3), 240, dtype=np.uint8)
    np.random.seed(303)

    # Normal tea particles bed
    for _ in range(950):
        cx = np.random.randint(70, 630)
        cy = np.random.randint(70, 630)
        radius = np.random.randint(3, 8)
        color = (
            np.random.randint(20, 40),
            np.random.randint(24, 45),
            np.random.randint(30, 54),
        )
        axes = (radius, int(radius * np.random.uniform(0.7, 1.3)))
        angle = np.random.randint(0, 180)
        cv2.ellipse(img, (cx, cy), axes, angle, 0, 360, color, -1)

    # Add Unauthorized Defect 1: Stalk / Stem (elongated yellow-brown piece)
    cv2.ellipse(img, (220, 260), (45, 8), 32, 0, 360, (50, 140, 195), -1)
    cv2.ellipse(img, (220, 260), (42, 6), 32, 0, 360, (60, 150, 210), -1)

    # Add Unauthorized Defect 2: Second Stalk (long angled woody stem)
    cv2.ellipse(img, (480, 420), (52, 9), -40, 0, 360, (55, 138, 190), -1)

    # Add Unauthorized Defect 3: Third Stalk
    cv2.ellipse(img, (450, 190), (38, 7), 65, 0, 360, (52, 142, 198), -1)

    # Add Unauthorized Defect 4: Coarse Fiber (thin curved strand)
    pts1 = np.array([[310, 350], [330, 370], [355, 365], [375, 385]], np.int32)
    cv2.polylines(img, [pts1], False, (65, 155, 205), 3)

    # Add Unauthorized Defect 5: Second Coarse Fiber
    pts2 = np.array([[180, 450], [195, 470], [215, 465], [230, 480]], np.int32)
    cv2.polylines(img, [pts2], False, (60, 148, 198), 3)

    # Add Unauthorized Defect 6: Discolored Pale Flake (flat unfermented yellowish flake)
    cv2.circle(img, (280, 180), 16, (70, 175, 215), -1)

    # Add Unauthorized Defect 7: Second Discolored Pale Flake
    cv2.circle(img, (520, 290), 18, (75, 180, 220), -1)

    # Add Unauthorized Defect 8: Foreign Matter / Stone (bright contrasting grit particle)
    cv2.circle(img, (360, 480), 10, (215, 215, 235), -1)

    cv2.imwrite(str(output_path), img)
    return output_path


def ensure_demo_samples_exist() -> Dict[str, Path]:
    """
    Ensures all 3 demo sample images are generated on disk.
    """
    p1 = DEMO_DIR / "pure_bop_sample.jpg"
    p2 = DEMO_DIR / "mixed_bop_dust_sample.jpg"
    p3 = DEMO_DIR / "defective_stalks_sample.jpg"

    if not p1.exists():
        generate_pure_bop_sample(p1)
    if not p2.exists():
        generate_mixed_bop_dust_sample(p2)
    if not p3.exists():
        generate_defective_stalks_sample(p3)

    return {
        "pure_bop": p1,
        "mixed_bop_dust": p2,
        "defective_stalks": p3,
    }


def list_demo_samples_metadata() -> List[Dict[str, Any]]:
    """
    Returns list of demo samples with descriptions and tags for frontend demonstration.
    """
    ensure_demo_samples_exist()
    return [
        {
            "id": "pure_bop",
            "name": "Clean Pure BOP Sample",
            "filename": "pure_bop_sample.jpg",
            "grade": "BOP",
            "description": "Uniform Broken Orange Pekoe broken leaf without mixed cuts or defect particles.",
            "test_target": "Pure Single Grade Verification",
            "expected_mix_status": "Pure Single Grade",
            "expected_defects": 0,
        },
        {
            "id": "mixed_bop_dust",
            "name": "Mixed Grade Sample (BOP + DUST)",
            "filename": "mixed_bop_dust_sample.jpg",
            "grade": "BOP / DUST Mix",
            "description": "Medium BOP leaf heavily mixed with fine DUST particles and siftings.",
            "test_target": "Mixed Grade Composition Detection",
            "expected_mix_status": "Mixed Grade Detected (BOP ~65% + DUST ~30%)",
            "expected_defects": 0,
        },
        {
            "id": "defective_stalks",
            "name": "Contaminated Sample with Stalks & Fibers",
            "filename": "defective_stalks_sample.jpg",
            "grade": "BOP with Unauthorized Matter",
            "description": "Contains 3 stalks/stems, 2 coarse fibers, 2 pale flakes, and 1 foreign grit particle.",
            "test_target": "Particle Bounding Box Detection",
            "expected_mix_status": "Single Grade with Defect Contamination",
            "expected_defects": 8,
        },
    ]
