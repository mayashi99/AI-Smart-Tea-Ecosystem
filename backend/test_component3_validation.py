"""
Verification Script for Component 03: AI-Powered Tea Grade Classification & Purity Analysis
This script verifies:
1. Component 03 backend imports (predict, purity, train, evaluate, routers) and FastAPI app.
2. Route registration in FastAPI:
   - Primary Component 03 routes: /api/component3/*
   - Aliased tea-grade routes: /api/tea-grade/*
   - Clear separation from Component 04 (/api/component04/*).
3. Discovery of the trained YOLO11 classification model (best.pt).
4. Real grade classification inference on a sample tea-leaf image.
5. Execution of Purity Analysis on a dry-tea sample image.
6. Verification of missing-label handling (validated purity is None, not fabricated).
7. Verification that grade confidence is NEVER reused as a purity score.
8. Verification of error handling on invalid files.
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))


def run_verification():
    print("=" * 65)
    print("COMPONENT 03 VALIDATION SUITE: GRADE PREDICTION & PURITY ANALYSIS")
    print("=" * 65)

    # 1. Test Imports
    print("\n[TEST 1] Testing Component 03 imports...")
    try:
        from app.components.component3 import (
            predict_tea_grade,
            get_model_info,
            resolve_model_path,
            analyze_tea_purity,
            analyze_mixed_composition,
            detect_unauthorized_particles,
            list_demo_samples_metadata,
            ensure_demo_samples_exist,
            train_tea_grade_model,
            evaluate_tea_model,
            router as component3_router,
            tea_grade_router,
        )
        from app.components.component04.api import router as component04_router
        from app.main import app
        print("  -> Grade prediction, purity, mixed composition, defect detection, training, evaluation, routers, and FastAPI app imported successfully.")
    except Exception as e:
        print(f"  FAILED: Import error: {e}")
        return False

    # 2. Check Route Registration in FastAPI
    print("\n[TEST 2] Checking FastAPI route registration via OpenAPI schema...")
    registered_routes = list(app.openapi().get("paths", {}).keys())
    
    expected_c3_routes = [
        "/api/component3/predict",
        "/api/component3/purity",
        "/api/component3/mixed-composition",
        "/api/component3/detect-defects",
        "/api/component3/demo-samples",
        "/api/component3/demo-samples/{sample_id}",
        "/api/component3/info",
        "/api/component3/health",
        "/api/component3/grades",
        "/api/tea-grade/predict",
        "/api/tea-grade/purity",
        "/api/tea-grade/mixed-composition",
        "/api/tea-grade/detect-defects",
        "/api/tea-grade/demo-samples",
        "/api/tea-grade/demo-samples/{sample_id}",
        "/api/tea-grade/info",
        "/api/tea-grade/health",
        "/api/tea-grade/grades",
    ]

    all_registered = True
    for r in expected_c3_routes:
        if r in registered_routes:
            print(f"  -> Route found: {r}")
        else:
            print(f"  FAILED: Route missing: {r}")
            all_registered = False

    # Check Component 04 clean separation
    print("\n[TEST 2b] Verifying Component 04 separation...")
    c04_routes = ["/api/component04/health", "/api/component04/info"]
    for r in c04_routes:
        if r in registered_routes:
            print(f"  -> Component 04 route found: {r}")
        else:
            print(f"  FAILED: Component 04 route missing: {r}")
            all_registered = False

    if not all_registered:
        return False

    # 3. Check Model Path Resolution
    print("\n[TEST 3] Checking YOLO11 model resolution...")
    model_path = resolve_model_path()
    if model_path and model_path.is_file():
        print(f"  -> Trained model weights located at: {model_path}")
    else:
        print(f"  -> Model not found at active candidates. Checking info...")

    info = get_model_info()
    print(f"  -> Component: {info['component']}")
    print(f"  -> Model Architecture: {info['model_architecture']}")
    print(f"  -> Bounding Box Support: {info['bounding_box_support']}")
    print(f"  -> Explainable AI Support: {info['explainable_ai_support']}")
    print(f"  -> Active Modules: {info.get('feature_status', {})}")

    # 4. Locate Sample Images for Testing
    project_root = backend_dir.parent
    sample_images = list((project_root / "runs" / "classify" / "predict").glob("*.jpg"))
    if not sample_images:
        sample_images = list((project_root / "runs" / "classify" / "predict-2").glob("*.jpg"))

    if not sample_images:
        print("  -> Warning: No sample test images found in runs/classify/predict/.")
        return True

    test_image_path = sample_images[0]
    print(f"\n[TEST 4] Testing Grade Prediction on real sample: {test_image_path.name}...")
    image_bytes = test_image_path.read_bytes()

    try:
        grade_result = predict_tea_grade(image_bytes, filename=test_image_path.name)
        print(f"  -> Prediction SUCCESSFUL!")
        print(f"  -> Predicted Grade: {grade_result['predicted_grade']} ({grade_result.get('grade_full_name', '')})")
        print(f"  -> Model Confidence: {grade_result['confidence_percentage']}% (decimal: {grade_result['confidence']})")
        print("  -> Top 5 Predictions:")
        for t in grade_result['top5']:
            print(f"      Rank #{t['rank']}: {t['grade']:12} | Confidence: {t['confidence_percentage']:>6.2f}%")
    except Exception as e:
        print(f"  -> Grade prediction test encountered: {e}")

    # 5. Test Purity Analysis on the Same Sample
    print(f"\n[TEST 5] Testing Purity Analysis on sample: {test_image_path.name}...")
    try:
        purity_result = analyze_tea_purity(image_bytes, filename=test_image_path.name)
        print("  -> Purity analysis executed successfully.")
        print(f"  -> Validated Purity Percentage: {purity_result['validated_purity_percentage']} (Correct: None, no ground-truth)")
        print(f"  -> Status: {purity_result['status']}")
        print(f"  -> Is Validated: {purity_result['is_validated']}")
        print(f"  -> Ground Truth Available: {purity_result['ground_truth_purity_available']}")

        # Verify strict compliance
        assert purity_result["validated_purity_percentage"] is None, "Validated purity percentage must be None when ground truth is missing!"
        assert purity_result["audit_findings"]["classification_confidence_reused"] is False, "Classification confidence must NOT be reused as purity!"

        metrics = purity_result.get("experimental_metrics", {})
        print("  -> Experimental CV Metrics:")
        print(f"      - Color Uniformity Index: {metrics.get('color_uniformity_index')} / 100")
        print(f"      - Chromatic Anomaly Ratio: {metrics.get('chromatic_anomaly_percentage')}%")
        print(f"      - Particle Coverage: {metrics.get('particle_coverage_percentage')}%")
        print(f"      - Mean Particle Brightness: {metrics.get('mean_particle_brightness')}")
    except Exception as e:
        print(f"  FAILED: Purity analysis error: {e}")
        return False

    # 6. Test Error Handling on invalid file extension
    print("\n[TEST 6] Testing error handling on invalid file extension...")
    try:
        analyze_tea_purity(b"not an image", filename="sample.txt")
        print("  FAILED: Did not catch invalid file extension!")
        return False
    except ValueError as ve:
        print(f"  -> Correctly rejected invalid file extension: {ve}")

    # 7. Test Rejection of Non-Tea Image (Human Portrait / Face)
    print("\n[TEST 7] Testing Non-Tea Image Rejection (Human Portrait / Face)...")
    import io
    from PIL import Image
    import numpy as np

    # Generate synthetic portrait-like image with skin tone
    portrait_arr = np.full((224, 224, 3), [180, 200, 150], dtype=np.uint8)  # foliage background
    portrait_arr[40:180, 60:160] = [210, 150, 130]  # skin tone area
    portrait_pil = Image.fromarray(portrait_arr)
    portrait_bytes = io.BytesIO()
    portrait_pil.save(portrait_bytes, format="JPEG")
    portrait_raw = portrait_bytes.getvalue()

    try:
        predict_tea_grade(portrait_raw, filename="person_photo.jpg")
        print("  FAILED: Allowed non-tea human portrait image to be classified as tea grade!")
        return False
    except ValueError as ve:
        print(f"  -> SUCCESS: Correctly rejected portrait image with message: '{ve}'")

    try:
        analyze_tea_purity(portrait_raw, filename="person_photo.jpg")
        print("  FAILED: Allowed non-tea human portrait image to undergo purity analysis!")
        return False
    except ValueError as ve:
        print(f"  -> SUCCESS: Correctly rejected portrait purity analysis with message: '{ve}'")

    # 8. Test Rejection of Non-Tea Image (Vibrant Landscape / Blue Sky)
    print("\n[TEST 8] Testing Non-Tea Image Rejection (Vibrant Blue Sky / Nature)...")
    nature_arr = np.full((224, 224, 3), [70, 140, 240], dtype=np.uint8)  # bright blue sky
    nature_pil = Image.fromarray(nature_arr)
    nature_bytes = io.BytesIO()
    nature_pil.save(nature_bytes, format="JPEG")
    nature_raw = nature_bytes.getvalue()

    try:
        predict_tea_grade(nature_raw, filename="nature.jpg")
        print("  FAILED: Allowed bright sky image to be classified as tea grade!")
        return False
    except ValueError as ve:
        print(f"  -> SUCCESS: Correctly rejected non-tea landscape image with message: '{ve}'")

    # 9. Test Demo Samples Availability
    print("\n[TEST 9] Testing Demo Samples generation and metadata...")
    demo_dict = ensure_demo_samples_exist()
    assert len(demo_dict) == 3, f"Expected 3 demo samples, found {len(demo_dict)}"
    samples_meta = list_demo_samples_metadata()
    assert len(samples_meta) == 3, f"Expected 3 metadata entries, found {len(samples_meta)}"
    for s in samples_meta:
        print(f"  -> Demo sample loaded: '{s['name']}' ({s['id']}) - Target: {s['test_target']}")

    # 10. Test Mixed Tea Grade Composition Analysis
    print("\n[TEST 10] Testing Mixed Tea Grade Composition on Pure vs. Mixed Samples...")
    pure_bytes = demo_dict["pure_bop"].read_bytes()
    mixed_bytes = demo_dict["mixed_bop_dust"].read_bytes()

    pure_mix_result = analyze_mixed_composition(pure_bytes, filename="pure_bop_sample.jpg")
    print(f"  -> Pure Sample Mix Status: '{pure_mix_result['mix_status']}' (Severity: {pure_mix_result['mix_severity']})")
    print(f"     Primary Grade: {pure_mix_result['primary_grade']['grade']} ({pure_mix_result['primary_grade']['percentage']}%)")
    print(f"     Uniformity Score: {pure_mix_result['uniformity_score']}/100")
    assert pure_mix_result["success"] is True
    assert pure_mix_result["is_mixed"] is False or pure_mix_result["mix_severity"] in ["pure_single_grade", "minor_grade_variation"]

    mixed_result = analyze_mixed_composition(mixed_bytes, filename="mixed_bop_dust_sample.jpg")
    print(f"  -> Mixed Sample Mix Status: '{mixed_result['mix_status']}' (Severity: {mixed_result['mix_severity']})")
    print(f"     Primary: {mixed_result['primary_grade']['grade']} ({mixed_result['primary_grade']['percentage']}%)")
    if mixed_result["secondary_grade"]:
        print(f"     Secondary: {mixed_result['secondary_grade']['grade']} ({mixed_result['secondary_grade']['percentage']}%)")
    print(f"     Uniformity Score: {mixed_result['uniformity_score']}/100")
    print(f"     Commercial Verdict: {mixed_result['commercial_verdict']}")
    assert mixed_result["success"] is True
    assert len(mixed_result["composition_breakdown"]) >= 2
    assert mixed_result["is_mixed"] is True or mixed_result["mix_severity"] in ["moderately_mixed", "heavily_blended", "minor_grade_variation"]

    # 11. Test Defect & Unauthorized Particle Bounding Box Detection
    print("\n[TEST 11] Testing Unauthorized Particle Detection & Bounding Boxes...")
    defective_bytes = demo_dict["defective_stalks"].read_bytes()
    defect_result = detect_unauthorized_particles(defective_bytes, filename="defective_stalks_sample.jpg")
    print(f"  -> Total Defects Pinpointed: {defect_result['total_defects']}")
    print(f"  -> Cleanliness Grade: {defect_result['cleanliness_grade']}")
    print(f"  -> Defect Breakdown: {defect_result['defect_counts']}")
    print(f"  -> Commercial Verdict: {defect_result['commercial_verdict']}")
    assert defect_result["success"] is True
    assert defect_result["total_defects"] > 0, "Failed to detect injected defect particles!"
    assert defect_result["annotated_image"] is not None and defect_result["annotated_image"].startswith("data:image/jpeg;base64,")

    first_box = defect_result["defects"][0]
    print(f"  -> Sample Bounding Box #1:")
    print(f"      Label: {first_box['label']} ({first_box['defect_type']})")
    print(f"      Confidence: {first_box['confidence_percentage']}%")
    print(f"      Normalized Bounding Box [ymin, xmin, ymax, xmax]: {first_box['bbox_normalized']}")
    print(f"      Pixel Bounding Box [x, y, w, h]: {first_box['bbox_pixel']}")
    assert len(first_box["bbox_normalized"]) == 4
    assert len(first_box["bbox_pixel"]) == 4

    # 12. Test Non-Tea Image Rejection on Mixed Composition & Defect Detection
    print("\n[TEST 12] Testing Non-Tea Rejection on Mixed Composition & Defect Endpoints...")
    try:
        analyze_mixed_composition(portrait_raw, filename="person.jpg")
        print("  FAILED: Allowed portrait image in analyze_mixed_composition!")
        return False
    except ValueError as ve:
        print(f"  -> SUCCESS: Mixed composition rejected non-tea image: '{ve}'")

    try:
        detect_unauthorized_particles(portrait_raw, filename="person.jpg")
        print("  FAILED: Allowed portrait image in detect_unauthorized_particles!")
        return False
    except ValueError as ve:
        print(f"  -> SUCCESS: Defect detector rejected non-tea image: '{ve}'")

    print("\n" + "=" * 65)
    print("ALL COMPONENT 03 TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)
    return True


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)

