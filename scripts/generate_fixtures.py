"""Generate test fixtures for Step 2 check validation."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont
from poster_agent.spec.models import PosterSpec, BBox, TextElement, LogoPlacement


def create_base_spec() -> PosterSpec:
    return PosterSpec(
        canvas_width_px=1200,
        canvas_height_px=1600,
        dpi=300,
        template_id="event_portrait_hero",
        palette=["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"],
        text_safe_zones=[BBox(y_min=200, x_min=50, y_max=900, x_max=950)],
        elements=[
            TextElement(
                id="headline_1",
                role="headline",
                text="APEX TECH SUMMIT 2026",
                source="brief",
                font="Outfit",
                size=36,
                weight=800,
                color="#FFFFFF",
                box=BBox(y_min=180, x_min=80, y_max=280, x_max=920),
            ),
            TextElement(
                id="subhead_1",
                role="subheadline",
                text="ANNUAL AI AND ROBOTICS SHOWCASE",
                source="brief",
                font="Inter",
                size=20,
                weight=600,
                color="#00F5D4",
                box=BBox(y_min=300, x_min=80, y_max=360, x_max=920),
            ),
            TextElement(
                id="date_1",
                role="date",
                text="OCTOBER 30 2026",
                source="brief",
                font="Inter",
                size=18,
                weight=600,
                color="#FEE440",
                box=BBox(y_min=750, x_min=80, y_max=800, x_max=600),
            ),
            TextElement(
                id="venue_1",
                role="venue",
                text="MAIN AUDITORIUM TECH CAMPUS",
                source="brief",
                font="Inter",
                size=16,
                weight=500,
                color="#FFFFFF",
                box=BBox(y_min=820, x_min=80, y_max=870, x_max=800),
            ),
        ],
        logos=[
            LogoPlacement(
                file="college_logo.png",
                box=BBox(y_min=40, x_min=80, y_max=120, x_max=350),
                clear_space_px=20,
            )
        ],
        art_slots=[],
        assumptions=["Clean promotional event poster"],
        missing_fields=[],
        qr_code="https://apextech.edu/summit",
    )


def generate_fixture_images(fixtures_dir: Path | str = "tests/fixtures"):
    f_dir = Path(fixtures_dir)
    f_dir.mkdir(parents=True, exist_ok=True)
    w, h = 1200, 1600

    try:
        font_headline = ImageFont.truetype("arial.ttf", 52)
        font_subhead = ImageFont.truetype("arial.ttf", 32)
        font_body = ImageFont.truetype("arial.ttf", 26)
    except Exception:
        font_headline = font_subhead = font_body = ImageFont.load_default()

    logo_path = Path("assets/college_logo.png")
    logo_img = Image.open(logo_path).convert("RGBA") if logo_path.exists() else None

    # 1. Clean Poster (PASSES ALL CHECKS)
    img_clean = Image.new("RGB", (w, h), (11, 19, 43))
    d_clean = ImageDraw.Draw(img_clean)
    if logo_img:
        logo_copy = logo_img.copy()
        logo_copy.thumbnail((270, 80))
        img_clean.paste(logo_copy, (96, 64), logo_copy)
    d_clean.text((96, 288), "APEX TECH SUMMIT 2026", fill=(255, 255, 255), font=font_headline)
    d_clean.text((96, 480), "ANNUAL AI AND ROBOTICS SHOWCASE", fill=(0, 245, 212), font=font_subhead)
    d_clean.text((96, 1200), "OCTOBER 30 2026", fill=(254, 228, 64), font=font_body)
    d_clean.text((96, 1312), "MAIN AUDITORIUM TECH CAMPUS", fill=(255, 255, 255), font=font_body)
    img_clean.save(f_dir / "clean_poster.png")

    # 2. Duplicated Headline Poster (FAILS OCR DUPLICATION)
    img_dup = Image.new("RGB", (w, h), (11, 19, 43))
    d_dup = ImageDraw.Draw(img_dup)
    if logo_img:
        logo_copy = logo_img.copy()
        logo_copy.thumbnail((270, 80))
        img_dup.paste(logo_copy, (96, 64), logo_copy)
    d_dup.text((96, 288), "APEX TECH SUMMIT 2026", fill=(255, 255, 255), font=font_headline)
    d_dup.text((96, 480), "ANNUAL AI AND ROBOTICS SHOWCASE", fill=(0, 245, 212), font=font_subhead)
    # Duplicated headline line further down!
    d_dup.text((96, 750), "APEX TECH SUMMIT 2026", fill=(255, 255, 255), font=font_headline)
    d_dup.text((96, 1200), "OCTOBER 30 2026", fill=(254, 228, 64), font=font_body)
    d_dup.text((96, 1312), "MAIN AUDITORIUM TECH CAMPUS", fill=(255, 255, 255), font=font_body)
    img_dup.save(f_dir / "duplicated_headline.png")

    # 3. Wrong Order Poster (FAILS OCR ORDER CHECK)
    # Subheading placed in the middle of or above the headline
    img_order = Image.new("RGB", (w, h), (11, 19, 43))
    d_order = ImageDraw.Draw(img_order)
    if logo_img:
        logo_copy = logo_img.copy()
        logo_copy.thumbnail((270, 80))
        img_order.paste(logo_copy, (96, 64), logo_copy)
    # Line 1 of headline
    d_order.text((96, 240), "APEX TECH", fill=(255, 255, 255), font=font_headline)
    # Interrupted by subheadline right in the middle!
    d_order.text((96, 360), "ANNUAL AI AND ROBOTICS SHOWCASE", fill=(0, 245, 212), font=font_subhead)
    # Line 2 of headline
    d_order.text((96, 480), "SUMMIT 2026", fill=(255, 255, 255), font=font_headline)
    d_order.text((96, 1200), "OCTOBER 30 2026", fill=(254, 228, 64), font=font_body)
    d_order.text((96, 1312), "MAIN AUDITORIUM TECH CAMPUS", fill=(255, 255, 255), font=font_body)
    img_order.save(f_dir / "wrong_order.png")

    print("All fixtures generated successfully in tests/fixtures/")


if __name__ == "__main__":
    generate_fixture_images()
