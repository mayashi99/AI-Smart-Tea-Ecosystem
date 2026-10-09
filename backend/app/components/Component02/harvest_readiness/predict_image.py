
from pathlib import Path
import argparse
import torch
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = (
    BASE_DIR
    / "runs"
    / "harvest_readiness_yolo11n_50epochs"
    / "weights"
    / "best.pt"
)

def predict_image(image_path):
    image_file = Path(image_path).expanduser().resolve()

    if not MODEL_PATH.is_file():
        print(f"Model not found: {MODEL_PATH}")
        return

    if not image_file.is_file():
        print(f"Image not found: {image_file}")
        return

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = YOLO(str(MODEL_PATH))

    results = model.predict(
        source=str(image_file),
        imgsz=224,
        device=device,
        verbose=False
    )

    result = results[0]

    if result.probs is None:
        print("Could not get classification probabilities.")
        return

    class_id = int(result.probs.top1)
    class_name = model.names[class_id]
    confidence = float(result.probs.top1conf) * 100

    print("\n--- Tea Harvest Readiness ---")
    print(f"Image      : {image_file.name}")
    print(f"Prediction : {class_name}")
    print(f"Confidence : {confidence:.2f}%")
    print(f"Device     : {device}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path", help="Path to an image")
    args = parser.parse_args()

    predict_image(args.image_path)
