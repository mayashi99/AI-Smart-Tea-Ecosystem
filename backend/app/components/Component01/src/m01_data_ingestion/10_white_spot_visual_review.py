
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import csv
import math

# =====================================================
# STEP 10 - WHITE SPOT VISUAL QUALITY REVIEW
# =====================================================

ROOT = Path(__file__).resolve().parents[2]

INPUT_CSV = (
    ROOT / "data" / "processed"
    / "white_spot_screened_candidates.csv"
)

OUTPUT_DIR = (
    ROOT / "outputs" / "figures"
    / "white_spot_final_review"
)

REVIEW_CSV = (
    ROOT / "outputs" / "reports"
    / "white_spot_visual_quality_review.csv"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)

if not INPUT_CSV.is_file():
    raise FileNotFoundError(INPUT_CSV)

with INPUT_CSV.open(
    "r", encoding="utf-8", newline=""
) as file:
    records = list(csv.DictReader(file))

if not records:
    raise ValueError("No White Spot candidates found.")

# -----------------------------------------------------
# CONTACT SHEET SETTINGS
# -----------------------------------------------------

COLUMNS = 5
ROWS = 6
PER_SHEET = COLUMNS * ROWS

CELL_WIDTH = 190
CELL_HEIGHT = 185

review_rows = []

# -----------------------------------------------------
# BUILD INDEXED REVIEW RECORDS
# -----------------------------------------------------

for index, record in enumerate(records, start=1):

    image_path = ROOT / record["crop_path"]

    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    review_rows.append({
        "image_id": f"WS_{index:03d}",
        "crop_path": record["crop_path"],
        "original_split": record["original_split"],
        "source_image": record["source_image"],
        "review_status": "pending",
        "review_notes": "",
    })

# Do not overwrite previous manual decisions
if not REVIEW_CSV.exists():

    with REVIEW_CSV.open(
        "w", encoding="utf-8", newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(review_rows[0].keys())
        )

        writer.writeheader()
        writer.writerows(review_rows)

# -----------------------------------------------------
# GENERATE CONTACT SHEETS
# -----------------------------------------------------

sheet_count = math.ceil(
    len(review_rows) / PER_SHEET
)

for sheet_index in range(sheet_count):

    start = sheet_index * PER_SHEET
    end = start + PER_SHEET

    subset = review_rows[start:end]

    sheet = Image.new(
        "RGB",
        (
            COLUMNS * CELL_WIDTH,
            ROWS * CELL_HEIGHT
        ),
        "white"
    )

    draw = ImageDraw.Draw(sheet)

    for local_index, record in enumerate(subset):

        row = local_index // COLUMNS
        column = local_index % COLUMNS

        x = column * CELL_WIDTH
        y = row * CELL_HEIGHT

        image_path = ROOT / record["crop_path"]

        with Image.open(image_path) as opened:

            image = ImageOps.exif_transpose(opened)
            image = image.convert("RGB")

            thumbnail = ImageOps.contain(
                image,
                (175, 145)
            )

        image_x = (
            x + (CELL_WIDTH - thumbnail.width) // 2
        )

        image_y = y + 5

        sheet.paste(
            thumbnail,
            (image_x, image_y)
        )

        label = (
            f"{record['image_id']} "
            f"({record['original_split']})"
        )

        draw.text(
            (x + 10, y + 155),
            label,
            fill="black"
        )

    sheet_path = (
        OUTPUT_DIR
        / f"white_spot_review_{sheet_index + 1:02d}.png"
    )

    sheet.save(sheet_path)

    print(f"Saved: {sheet_path}")

# -----------------------------------------------------
# FINAL SUMMARY
# -----------------------------------------------------

print("=" * 65)
print("STEP 10 - WHITE SPOT VISUAL QUALITY REVIEW")
print("=" * 65)

print(f"Total screened candidates: {len(records)}")
print(f"Contact sheets generated: {sheet_count}")

print("\nVisual review CSV:")
print(REVIEW_CSV)

print("\nContact sheets:")
print(OUTPUT_DIR)

print("\nReview status values:")
print("approve = visually acceptable candidate")
print("exclude = unsuitable image")
print("pending = not reviewed")

print("\nNo original images modified.")
print("STEP 10 COMPLETED")
