"""Run once: python -m app.components.Component02.setup_image_validation"""
from transformers import CLIPModel, CLIPProcessor
from .image_validation import MODEL_DIR, MODEL_ID


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    cache_dir = MODEL_DIR.parent / "download_cache"
    processor = CLIPProcessor.from_pretrained(MODEL_ID, cache_dir=cache_dir)
    model = CLIPModel.from_pretrained(MODEL_ID, use_safetensors=True, cache_dir=cache_dir)
    processor.save_pretrained(MODEL_DIR)
    model.save_pretrained(MODEL_DIR)
    print(f"Image validation model saved to {MODEL_DIR}")


if __name__ == "__main__":
    main()
