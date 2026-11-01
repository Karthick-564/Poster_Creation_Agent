"""Generate high-fidelity assets for NOVA CTF, AURORA, and GREEN LOOP acceptance tests."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def create_nova_ctf_assets(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = 1080, 1350

    # Background: #0A0E17 with cyber grid and radial glow
    bg = Image.new("RGBA", (w, h), (10, 14, 23, 255))
    draw = ImageDraw.Draw(bg)
    # Subtle cyber grid
    for x in range(0, w, 60):
        draw.line([(x, 0), (x, h)], fill=(0, 255, 156, 18), width=1)
    for y in range(0, h, 60):
        draw.line([(0, y), (w, y)], fill=(0, 209, 255, 18), width=1)
    # Radial glow in center
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([w//2 - 350, h//2 - 350, w//2 + 350, h//2 + 350], fill=(0, 209, 255, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    bg = Image.alpha_composite(bg, glow)
    bg_path = out_dir / "nova_bg.png"
    bg.save(bg_path)

    # Hero: Isometric cyber core cutout
    hw, hh = 500, 500
    hero = Image.new("RGBA", (hw, hh), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(hero)
    cx, cy = hw // 2, hh // 2
    # Draw glowing isometric hexagon cube
    pts = [
        (cx, cy - 180), (cx + 160, cy - 80), (cx + 160, cy + 100),
        (cx, cy + 190), (cx - 160, cy + 100), (cx - 160, cy - 80)
    ]
    hdraw.polygon(pts, fill=(15, 23, 42, 230), outline=(0, 255, 156, 255), width=4)
    # Interior isometric lines
    hdraw.line([(cx, cy - 180), (cx, cy + 20)], fill=(0, 209, 255, 255), width=3)
    hdraw.line([(cx + 160, cy - 80), (cx, cy + 20)], fill=(0, 209, 255, 255), width=3)
    hdraw.line([(cx - 160, cy - 80), (cx, cy + 20)], fill=(0, 209, 255, 255), width=3)
    hdraw.line([(cx, cy + 20), (cx, cy + 190)], fill=(0, 255, 156, 255), width=4)
    # Central glowing node
    hdraw.ellipse([cx - 35, cy - 15, cx + 35, cy + 55], fill=(0, 255, 156, 240), outline=(255, 255, 255, 255), width=2)
    hero_path = out_dir / "nova_hero.png"
    hero.save(hero_path)

    # 3D Title asset for testing OCR fallback
    # Title is "NOVA CTF 2026"
    title_img = Image.new("RGBA", (800, 160), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(title_img)
    tdraw.text((50, 40), "NOVA CTF 2026", fill=(0, 255, 156, 255))
    title_path = out_dir / "nova_title_3d.png"
    title_img.save(title_path)

    return bg_path, hero_path, title_path


def create_aurora_assets(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = 1080, 1350

    # Background: #0E0728 with cosmic aurora gradients
    bg = Image.new("RGBA", (w, h), (14, 7, 40, 255))
    aurora = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    adraw = ImageDraw.Draw(aurora)
    # Aurora ribbons
    adraw.ellipse([w//2 - 400, h//3 - 200, w//2 + 500, h//3 + 400], fill=(122, 231, 199, 60))
    adraw.ellipse([w//2 - 500, h//2 - 100, w//2 + 300, h//2 + 500], fill=(255, 77, 109, 50))
    adraw.ellipse([w//2 - 200, int(h * 0.65) - 150, w//2 + 400, int(h * 0.65) + 350], fill=(255, 183, 3, 40))
    aurora = aurora.filter(ImageFilter.GaussianBlur(100))
    bg = Image.alpha_composite(bg, aurora)
    bg_path = out_dir / "aurora_bg.png"
    bg.save(bg_path)

    # Hero: Prism crystal with aurora reflections
    hw, hh = 500, 500
    hero = Image.new("RGBA", (hw, hh), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(hero)
    cx, cy = hw // 2, hh // 2
    pts = [(cx, cy - 190), (cx + 150, cy + 130), (cx, cy + 190), (cx - 150, cy + 130)]
    hdraw.polygon(pts, fill=(36, 36, 62, 220), outline=(122, 231, 199, 255), width=3)
    # Facets
    hdraw.line([(cx, cy - 190), (cx, cy + 190)], fill=(255, 77, 109, 240), width=3)
    hdraw.line([(cx - 150, cy + 130), (cx, cy - 20)], fill=(255, 183, 3, 240), width=2)
    hdraw.line([(cx + 150, cy + 130), (cx, cy - 20)], fill=(122, 231, 199, 240), width=2)
    hero_path = out_dir / "aurora_hero.png"
    hero.save(hero_path)

    return bg_path, hero_path


def create_green_loop_assets(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = 1080, 1920

    # Background: Earthy warm cream #F4EBD0 with organic paper-cut ripples
    bg = Image.new("RGBA", (w, h), (244, 235, 208, 255))
    layers = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(layers)
    # Soft organic concentric curves (river and leaves)
    ldraw.ellipse([-150, 400, w + 200, 1100], fill=(47, 93, 80, 25))
    ldraw.ellipse([100, 700, w + 300, 1500], fill=(233, 162, 59, 20))
    ldraw.ellipse([-200, 1100, w + 100, 1850], fill=(200, 85, 61, 15))
    layers = layers.filter(ImageFilter.GaussianBlur(60))
    bg = Image.alpha_composite(bg, layers)
    bg_path = out_dir / "green_loop_bg.png"
    bg.save(bg_path)

    # Hero: Paper-cut botanical leaf rosette in #2F5D50 and #E9A23B
    hw, hh = 540, 540
    hero = Image.new("RGBA", (hw, hh), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(hero)
    cx, cy = hw // 2, hh // 2
    # Layered organic paper leaves
    # Back leaf
    hdraw.ellipse([cx - 160, cy - 190, cx + 160, cy + 150], fill=(47, 93, 80, 240), outline=(31, 42, 36, 255), width=3)
    # Accent leaf
    hdraw.ellipse([cx - 100, cy - 140, cx + 180, cy + 120], fill=(233, 162, 59, 230), outline=(200, 85, 61, 255), width=3)
    # Fore leaf
    hdraw.ellipse([cx - 140, cy - 80, cx + 100, cy + 180], fill=(47, 93, 80, 255), outline=(244, 235, 208, 255), width=3)
    # Sprout vein
    hdraw.line([(cx, cy - 140), (cx, cy + 150)], fill=(244, 235, 208, 255), width=4)
    hero_path = out_dir / "green_loop_hero.png"
    hero.save(hero_path)

    return bg_path, hero_path


if __name__ == "__main__":
    out_dir = Path("runs/synthetic_acceptance_assets")
    create_nova_ctf_assets(out_dir)
    create_aurora_assets(out_dir)
    create_green_loop_assets(out_dir)
    print("Generated all acceptance assets successfully.")

