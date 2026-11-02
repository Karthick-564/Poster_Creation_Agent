"""Unit and integration tests for Stage 2b Asset Resolution and Conditional Tooling (Commit 1)."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pytest
from PIL import Image

from poster_agent.assets.resolver import AssetResolver, ResolvedAsset
from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.unified_pipeline import UnifiedPosterPipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_valid_concept_fixture() -> dict:
    return {
        "thesis": "Circular sustainability hackathon empowering youth innovation.",
        "archetype": "focal_point",
        "archetype_rationale": "Central hero commanding the composition.",
        "movement": "orbital",
        "light_plan": {
            "key_direction": "top_left",
            "key_intensity": 85,
            "fill_intensity": 40,
            "rim": {"enabled": True, "color_hex": "#00F5D4"},
            "notes": "Directional rim light from top left",
        },
        "palette": {
            "bg_60": "#070B19",
            "hero_30": "#00F5D4",
            "accent_10": "#FEE440",
            "notes": "60/30/10 compliant palette",
        },
        "typography": {
            "body_stance": "Swiss clean grotesque",
            "tracking_stance": "Wide uppercase tracking",
        },
        "accent_row_choice": "Grand prize ribbon and register CTA",
        "assets": {
            "hero": {
                "ideogram_caption": "3D organic crystalline core",
                "negative_caption": "text, letters, numbers, words, watermark",
                "aspect": "4:5",
            },
            "background": {
                "ideogram_caption": "Atmospheric mist and fiber optics backdrop",
            },
            "accents": [
                {"id": "accent_glow", "ideogram_caption": "Subtle radial cyan light spill"}
            ],
        },
        "calm_regions_requested": [
            [0, 0, 350, 1000],
            [680, 0, 1000, 1000],
        ],
        "self_check": {
            "assumptions": "Standard mock run parameters",
            "unsupported_artifacts": [],
        },
    }


def get_valid_layout_fixture() -> dict:
    return {
        "slots": [
            {
                "row_id": "title_main",
                "role": "headline",
                "zone": [120, 60, 240, 940],
                "justify": "center",
                "align": "middle",
                "size_class": "headline",
                "font": "Inter",
                "treatment": "none",
                "max_lines": 1,
            },
            {
                "row_id": "date_main",
                "role": "subhead",
                "zone": [720, 60, 780, 940],
                "justify": "center",
                "align": "middle",
                "size_class": "subhead",
                "font": "Inter",
                "treatment": "none",
            },
        ],
        "layer_plan": [
            {"asset": "bg", "z": 0, "blend": "normal", "opacity": 100},
            {"asset": "hero", "z": 3, "blend": "normal", "opacity": 100},
        ],
        "scrims": [
            {
                "zone": [0, 0, 360, 1000],
                "direction": "to_bottom",
                "opacity_start": 0.85,
                "opacity_end": 0.0,
            }
        ],
        "checks": [{"id": "c1", "assertion": "Slots sit in calm regions"}],
        "calm_regions_used": [[0, 0, 350, 1000]],
        "rationale": "Clean hierarchy in calm zones",
    }


def _create_dummy_image(path: Path, size: tuple[int, int] = (200, 200), min_bytes: int = 25000) -> Path:
    """Create a decodable test image >= min_bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Generate high-entropy noise so compression doesn't shrink below min_bytes
    arr = np.random.randint(0, 256, (size[1], size[0], 3), dtype=np.uint8)
    img = Image.fromarray(arr, "RGB")
    img.save(path, format="PNG")
    # If smaller than min_bytes, append metadata/padding
    if path.stat().st_size < min_bytes:
        with open(path, "ab") as f:
            f.write(b"\x00" * (min_bytes - path.stat().st_size + 100))
    return path


def test_resolver_ladder_supplied_exists_and_missing_fallthrough():
    with tempfile.TemporaryDirectory() as td:
        t_root = Path(td)
        img_path = t_root / "supplied_hero.png"
        _create_dummy_image(img_path)

        # 1. Supplied exists and valid
        brief_extractor = BriefExtractor()
        brief = brief_extractor.extract(f"Title: Test\nDate: May 1\nVenue: Hall\nhero_path: {img_path.name}")
        resolver = AssetResolver(project_root=t_root)
        concept_plan = {"asset_plan": []}

        res = resolver.resolve_slot("hero", brief, concept_plan)
        assert res.source == "supplied"
        assert res.path == img_path.name
        assert any("[Ladder Step 1: supplied] MATCH" in l for l in resolver.logs)

        # 2. Supplied missing -> fallthrough to archive/native/generated
        brief_missing = brief_extractor.extract("Title: Test\nDate: May 1\nVenue: Hall\nhero_path: missing_phantom.png")
        resolver_miss = AssetResolver(project_root=t_root)
        res_miss = resolver_miss.resolve_slot("hero", brief_missing, concept_plan)
        assert res_miss.source != "supplied"
        assert any("[Ladder Step 1: supplied] FAILED" in l for l in resolver_miss.logs)


def test_resolver_ladder_archive_hit_and_miss():
    with tempfile.TemporaryDirectory() as td:
        t_root = Path(td)
        archive_dir = t_root / "assets" / "photos"
        archive_dir.mkdir(parents=True, exist_ok=True)
        img_a = archive_dir / "campus_atrium_building.png"
        img_b = archive_dir / "campus_dome_hall.png"
        _create_dummy_image(img_a)
        _create_dummy_image(img_b)

        resolver = AssetResolver(project_root=t_root)
        brief_extractor = BriefExtractor()

        # Archive match on "campus" keyword
        brief_match = brief_extractor.extract("Title: Campus Orientation\nDate: June 1\nVenue: Main Hall\nmood: campus building")
        concept_plan = {"asset_plan": []}
        res = resolver.resolve_slot("background", brief_match, concept_plan)
        assert res.source == "archive"
        # Deterministic alphabetical tie-break: img_a comes before img_b
        assert "campus_atrium_building.png" in res.path

        # Archive miss when no keywords match
        brief_miss = brief_extractor.extract("Title: Abstract Philosophy\nDate: June 1\nVenue: Room 1")
        resolver2 = AssetResolver(project_root=t_root)
        res2 = resolver2.resolve_slot("background", brief_miss, concept_plan)
        assert res2.source in ("native", "generated")


def test_resolver_ladder_native_and_generated():
    resolver = AssetResolver()
    brief_extractor = BriefExtractor()
    brief = brief_extractor.extract("Title: Commemorative Wishes\nDate: July 1\nVenue: Online\nmood: plain wishes")

    # Native via plain wishes mood
    res_native = resolver.resolve_slot("hero", brief, {"asset_plan": []})
    assert res_native.source == "native"
    assert res_native.path == "native"

    # Native via declared source: native
    brief_std = brief_extractor.extract("Title: Regular Fest\nDate: July 1\nVenue: Hall")
    concept_native = {
        "asset_plan": [
            {"slot": "hero", "source": "native", "ref": "native", "style_note": "none", "reason": "typographic only"}
        ]
    }
    res_decl_native = resolver.resolve_slot("hero", brief_std, concept_native)
    assert res_decl_native.source == "native"

    # Generated via declared source: generated
    concept_gen = {
        "asset_plan": [
            {"slot": "hero", "source": "generated", "ref": "3d core", "style_note": "clean", "reason": "visual punch"}
        ]
    }
    res_gen = resolver.resolve_slot("hero", brief_std, concept_gen)
    assert res_gen.source == "generated"
    assert "qwen-image-2.1" in res_gen.path


def test_concept_without_asset_plan_resolves_native_for_hero_and_bg():
    resolver = AssetResolver()
    brief_extractor = BriefExtractor()
    brief = brief_extractor.extract("Title: Minimal Design\nDate: Aug 1\nVenue: Hall")
    concept_no_plan = {}
    resolved = resolver.resolve_all(brief, concept_no_plan)
    assert resolved["hero"].source == "native"
    assert resolved["hero"].path == "native"
    assert resolved["background"].source == "native"
    assert resolved["background"].path == "native"


def test_brief_asset_parsing_and_no_leak_to_verbatim_text():
    raw_brief = """
Title: AI HACKATHON 2026
Date: DEC 12-14
Venue: TECH PARK
hero_path: assets/sample_hero.png
background_path: assets/sample_bg.png
qr_link: https://example.com/apply
logo_path: assets/sample_logo.png
    """.strip()

    extractor = BriefExtractor()
    brief = extractor.extract(raw_brief)

    # Asset references correctly parsed
    assert brief.get_asset_ref("hero_path") == "assets/sample_hero.png"
    assert brief.get_asset_ref("background_path") == "assets/sample_bg.png"
    assert brief.get_asset_ref("qr_link") == "https://example.com/apply"
    assert brief.get_asset_ref("logo_path") == "assets/sample_logo.png"

    # CRITICAL: Asset reference strings MUST NOT leak into verbatim text fields
    for field_key in ["hero_path", "background_path", "qr_link", "logo_path"]:
        assert field_key not in brief.fields, f"Asset key '{field_key}' leaked into verbatim fields!"


def test_stage1_missing_supplied_asset_fails_loudly():
    raw_brief = """
Title: GHOST FEST
Date: JAN 1
Venue: VOID
hero_path: assets/nonexistent_phantom_ghost_file.png
    """.strip()

    pipeline = UnifiedPosterPipeline(run_id="test_missing_asset_fail", use_mock=False)
    with pytest.raises(RuntimeError, match="Supplied asset references not found on disk"):
        pipeline.execute(raw_brief)


def test_conditional_stage_live_comfy_down_completes_when_assets_native(monkeypatch):
    """LIVE mode run where concept declares native assets must complete with ComfyUI DOWN."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
    pipeline = UnifiedPosterPipeline(run_id="test_comfy_down_native_run", use_mock=False)

    # Fake ComfyUI strictly down: is_alive is False, generation methods raise if called
    fake_comfy = MagicMock()
    fake_comfy.is_alive.return_value = False
    fake_comfy.generate_qwen_rgba.side_effect = RuntimeError("ComfyUI called unexpectedly!")
    fake_comfy.generate_ideogram_background.side_effect = RuntimeError("ComfyUI called unexpectedly!")
    pipeline.comfy = fake_comfy

    # Concept plan declaring native assets
    concept = get_valid_concept_fixture()
    concept["asset_plan"] = [
        {"slot": "hero", "source": "native", "ref": "native", "style_note": "none", "reason": "text poster"},
        {"slot": "background", "source": "native", "ref": "native", "style_note": "none", "reason": "brand field"},
    ]
    layout = get_valid_layout_fixture()

    responses = [concept, layout]
    fake_gemini = MagicMock()
    fake_gemini.generate_json = MagicMock(side_effect=lambda **kw: responses.pop(0))
    fake_gemini.critique_image.return_value = {
        "ocr_check": {"title_verbatim": True, "date_verbatim": True, "venue_verbatim": True},
        "aesthetic_audit": {"is_editorial_poster": True, "zero_web_button_cards": True, "critique": "Excellent native layout."},
        "overall_score": 9,
        "verdict": "READY_FOR_PRINT",
    }
    pipeline.gemini = fake_gemini

    brief_text = "Title: NATIVE CELEBRATION\nDate: FEB 10\nVenue: GRAND ATRIUM"
    try:
        res = pipeline.execute(brief_text=brief_text)
    except RuntimeError as e:
        if "The system cannot find the path specified" in str(e):
            pytest.skip(f"WSL path-interop skipped ({e})")
        raise

    assert res is not None
    # Generator methods were never called
    fake_comfy.generate_qwen_rgba.assert_not_called()
    fake_comfy.generate_ideogram_background.assert_not_called()

    # plan.json written with resolved_assets
    plan_path = pipeline.run_dir / "plan.json"
    assert plan_path.exists()
    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    assert "resolved_assets" in plan_data
    assert plan_data["resolved_assets"]["hero"]["source"] == "native"
    assert plan_data["resolved_assets"]["background"]["source"] == "native"


def test_mock_regression_canned_fallback():
    """Mock mode regression: pipeline executes, canned path works, plan written."""
    pipeline = UnifiedPosterPipeline(run_id="test_mock_regression", use_mock=True)
    brief_text = "Title: MOCK REGRESSION\nDate: MARCH 15\nVenue: AUDITORIUM"
    try:
        res = pipeline.execute(brief_text=brief_text)
    except RuntimeError as e:
        if "The system cannot find the path specified" in str(e):
            pytest.skip(f"WSL path-interop skipped ({e})")
        raise

    assert res is not None
    plan_path = pipeline.run_dir / "plan.json"
    assert plan_path.exists()
    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    assert "resolved_assets" in plan_data
    assert "hero" in plan_data["resolved_assets"]
    assert "background" in plan_data["resolved_assets"]
