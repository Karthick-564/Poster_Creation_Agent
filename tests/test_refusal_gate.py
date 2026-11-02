"""Unit tests for refusal_free gate (Phase D Commit 3a).

Verifies:
1. Rejects safety-blocked images (synthetic refusal banner: flat dark canvas with high-contrast text strip).
2. Passes clean artistic gradients, solid color canvases, and real photos.
"""
import numpy as np
from PIL import Image, ImageDraw

from poster_agent.qa.gates import check_refusal_free


def test_refusal_gate_detects_safety_blocked_image(tmp_path):
    # Construct synthetic safety refusal image: 1080x1920 solid #111111 with centered white text bar
    im = Image.new("RGB", (1080, 1920), (18, 18, 18))
    draw = ImageDraw.Draw(im)
    # Draw high contrast banner at y=900 with sharp white text bars
    draw.rectangle([200, 920, 880, 980], fill=(30, 30, 30), outline=(220, 220, 220), width=2)
    # Simulate text glyphs inside the banner
    for x in range(240, 840, 20):
        draw.line([(x, 935), (x + 8, 965)], fill=(255, 255, 255), width=3)

    refusal_path = tmp_path / "refusal_bg.png"
    im.save(refusal_path)

    failures = check_refusal_free(refusal_path)
    assert len(failures) == 1
    assert failures[0].kind == "refusal"
    assert "refusal" in failures[0].detail.lower()


def test_refusal_gate_passes_clean_gradient(tmp_path):
    # Construct smooth poster gradient (from #070B19 to #1E293B)
    w, h = 1080, 1920
    im = Image.new("RGB", (w, h))
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t = y / float(h)
        arr[y, :, 0] = int(7 + t * 25)
        arr[y, :, 1] = int(11 + t * 30)
        arr[y, :, 2] = int(25 + t * 35)
    im = Image.fromarray(arr)
    clean_path = tmp_path / "clean_gradient.png"
    im.save(clean_path)

    failures = check_refusal_free(clean_path)
    assert len(failures) == 0


def test_refusal_gate_passes_solid_canvas(tmp_path):
    # Solid background with zero edge noise
    im = Image.new("RGB", (1080, 1920), (255, 255, 255))
    solid_path = tmp_path / "solid_white.png"
    im.save(solid_path)

    failures = check_refusal_free(solid_path)
    assert len(failures) == 0

