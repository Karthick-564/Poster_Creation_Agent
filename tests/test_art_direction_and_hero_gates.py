"""Unit tests for Unified Art Direction Spec, Adapters, and Deterministic Hero Gates."""
import numpy as np
from pathlib import Path
from PIL import Image
import pytest

from poster_agent.agentic.art_direction_spec import (
    ArtDirectionSpec,
    PaletteTokens,
    LightingSpec,
    SpatialZones,
    HeroSpec,
    resolve_archetype_spec,
    spec_to_ideogram_payload,
    spec_to_flux_prompt,
    spec_to_qwen_hero_prompts,
)
from poster_agent.checks.hero_gates import evaluate_hero_quality, HeroGateResult


def test_art_direction_spec_validation():
    # Valid spec
    spec = ArtDirectionSpec(
        archetype="tech_hackathon",
        motif="faint perspective grid",
        palette=PaletteTokens(
            base="#070B19", primary="#00F5D4", secondary="#7B2FFF", accent="#FF3D68", text="#F0F6FC"
        ),
        light=LightingSpec(key_direction="upper-left", key_color="#00F5D4", rim="cyan"),
        zones=SpatialZones(
            title=[0, 0, 250, 1000],
            hero=[250, 150, 750, 850],
            details=[750, 0, 1000, 1000],
        ),
        hero=HeroSpec(
            object="holographic microprocessor with glowing circuit traces",
            materials=["brushed gunmetal", "translucent cyan acrylic"],
            perspective="front three-quarter",
            width_pct=45.0,
        ),
    )
    assert spec.archetype == "tech_hackathon"
    assert spec.palette.primary == "#00F5D4"


def test_art_direction_spec_rejects_bad_coordinates():
    with pytest.raises(ValueError):
        # Inverted or out-of-bound coords: ymin > ymax
        SpatialZones(title=[300, 0, 200, 1000])

    with pytest.raises(ValueError):
        # Invalid hex
        PaletteTokens(base="invalid_hex", primary="#00F5D4", secondary="#7B2FFF", accent="#FF3D68")


def test_ideogram_adapter_no_background_hero_conflict():
    spec = resolve_archetype_spec(brief_title="CYBER HACKATHON 2026", brief_category="hackathon")
    payload = spec_to_ideogram_payload(spec, canvas_w=1080.0, canvas_h=1920.0)

    # 1. Structure check
    assert "high_level_description" in payload
    assert "style_description" in payload
    assert "compositional_deconstruction" in payload

    # 2. Compositional deconstruction elements
    elems = payload["compositional_deconstruction"]["elements"]
    assert len(elems) == 3

    # Hero zone element is a refined architectural setting, NOT a dense competing object
    hero_elem = elems[0]
    assert hero_elem["bbox"] == spec.zones.hero
    assert "architectural" in hero_elem["desc"].lower() or "soft" in hero_elem["desc"].lower() or "subtle" in hero_elem["desc"].lower()

    # Title zone is calm and flat
    title_elem = elems[1]
    assert title_elem["bbox"] == spec.zones.title
    assert "calm" in title_elem["desc"].lower() or "unbroken" in title_elem["desc"].lower()

    # Details zone is calm and flat
    details_elem = elems[2]
    assert details_elem["bbox"] == spec.zones.details

    # All bounding boxes verify [ymin, xmin, ymax, xmax] with ymin < ymax and xmin < xmax in 0..1000
    for el in elems:
        ymin, xmin, ymax, xmax = el["bbox"]
        assert 0 <= ymin < ymax <= 1000
        assert 0 <= xmin < xmax <= 1000


def test_flux_adapter_contains_spatial_and_palette_tokens():
    spec = resolve_archetype_spec(brief_title="NOIR BEATS 2026", brief_category="cultural")
    prompt = spec_to_flux_prompt(spec)
    assert isinstance(prompt, str)
    assert spec.palette.base in prompt
    assert spec.light.key_direction in prompt
    assert "zero text" in prompt.lower()


def test_qwen_adapter_separates_positive_and_negative():
    spec = resolve_archetype_spec(brief_title="ROBOTICS EXPO 2026", brief_category="robotics")
    pos, neg = spec_to_qwen_hero_prompts(spec)

    assert "transparent background" in pos.lower()
    assert "empty alpha channel" in pos.lower()
    assert spec.light.key_direction in pos
    assert "no cutoff edges" in pos.lower()

    # Negative directives strictly in neg prompt
    assert "blurry" in neg
    assert "watermark" in neg
    assert "floor shadow" in neg


def test_deterministic_hero_gates_evaluates_sharpness_and_alpha(tmp_path: Path):
    # 1. Create a pristine test cutout: 512x512 with centered sharp circle and empty border
    w, h = 512, 512
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    arr = np.zeros((h, w, 4), dtype=np.uint8)

    # Centered solid circle (radius 120, margin > 100px)
    cy, cx = h // 2, w // 2
    y_grid, x_grid = np.ogrid[:h, :w]
    dist_sq = (x_grid - cx) ** 2 + (y_grid - cy) ** 2
    solid_circle = dist_sq <= (120 ** 2)

    # Add high-frequency texture inside circle for sharpness
    noise_pattern = (np.sin(x_grid / 4.0) * np.cos(y_grid / 4.0) * 127 + 128).astype(np.uint8)
    arr[solid_circle, 0] = noise_pattern[solid_circle]
    arr[solid_circle, 1] = 200
    arr[solid_circle, 2] = 255
    arr[solid_circle, 3] = 255

    clean_hero_path = tmp_path / "clean_hero.png"
    Image.fromarray(arr).save(clean_hero_path)

    res = evaluate_hero_quality(clean_hero_path)
    assert res.passed is True
    assert res.score >= 70.0
    assert res.touches_border is False
    assert 15.0 <= res.coverage_pct <= 40.0
    assert res.sharpness > 40.0

    # 2. Test cropped subject: touches image border
    arr_cropped = arr.copy()
    arr_cropped[:3, :] = [255, 255, 255, 255] # Touches top border
    cropped_path = tmp_path / "cropped_hero.png"
    Image.fromarray(arr_cropped).save(cropped_path)

    res_cropped = evaluate_hero_quality(cropped_path)
    assert res_cropped.passed is False
    assert res_cropped.touches_border is True
    assert "perimeter" in res_cropped.reason.lower() or "touches" in res_cropped.reason.lower()

