"""Regression tests for the official KCT logo asset and its placement."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.v2.assets import PROJECT_ROOT, MockAssetBroker, resolve_logo
from poster_agent.v2.brand import get_brand, resolve_format
from poster_agent.v2.composer import MockRenderer
from poster_agent.v2.pipeline import Pipeline
from poster_agent.v2.planner import KCTPlanner, rescale_logo_to_asset

BRIEF = """Title: AI Design Summit 2026
Eyebrow: KUMARAGURU COLLEGE OF TECHNOLOGY
Tagline: HUMAN JUDGEMENT IN THE AGE OF GENERATIVE SYSTEMS
Subtitle: A one-day campus summit on design and automation.
Date: 14 November 2026
Time: 09:30 AM IST
Venue: Sir M. Visvesvaraya Hall, KCT Campus
CTA: Scan to register
QR link: https://events.kct.ac.in/ai-design-summit
Closing: DESIGN WITH INTENT.
Organizer: Department of Computer Science and Engineering
"""

OFFICIAL_LOGO = PROJECT_ROOT / "assets" / "brand" / "kct" / "kct_logo.png"


def _official_image() -> Image.Image:
    assert OFFICIAL_LOGO.exists(), f"Official KCT logo missing at {OFFICIAL_LOGO}"
    return Image.open(OFFICIAL_LOGO)


def test_official_logo_file_is_present_and_print_sized():
    with _official_image() as image:
        assert image.mode in ("RGBA", "LA")
        assert image.width >= 1200
        assert image.height >= 300
        assert image.width / image.height == pytest.approx(3.05, abs=0.03)
        assert image.getchannel("A").getextrema()[1] == 255


def test_official_logo_resolves_without_placeholder(tmp_path):
    brand = get_brand("KCT")
    warnings: list[str] = []
    asset = resolve_logo(brand, tmp_path, allow_placeholder=True, warnings=warnings)

    assert asset is not None
    assert asset.placeholder is False
    assert asset.generator == "official-asset"
    assert Path(asset.path).resolve() == OFFICIAL_LOGO.resolve()
    assert warnings == []


def test_canonical_logo_is_not_the_apex_demo_mark():
    apex = PROJECT_ROOT / "assets" / "logo_kumaraguru.png"
    with Image.open(apex) as demo, _official_image() as official:
        assert official.size != demo.size
        assert official.width > demo.width
    assert (
        hashlib.sha256(OFFICIAL_LOGO.read_bytes()).digest()
        != hashlib.sha256(apex.read_bytes()).digest()
    )


@pytest.mark.parametrize("format_name", ["story", "fourfive", "square", "A3", "A4"])
def test_official_logo_keeps_top_right_clear_space_and_aspect(format_name):
    brand = get_brand("KCT")
    fmt = resolve_format(brand, format_name)
    brief = BriefExtractor().extract(BRIEF)
    spec = KCTPlanner().plan_candidates(brief, brand, fmt)[0]

    with _official_image() as image:
        spec = rescale_logo_to_asset(spec, brand, image.width, image.height)
        asset_ratio = image.width / image.height

    x, y, w, h = spec.logo_slots[0].box.to_px(fmt.width, fmt.height)
    clear = brand.clear_space_px(fmt)
    inset = max(clear, brand.safe_margin_px(fmt))

    # Top-right anchor, 10 mm clear space and safe-area containment.
    assert x + w == pytest.approx(fmt.width - inset, abs=0.5)
    assert y == pytest.approx(inset, abs=0.5)
    assert x >= inset - 0.5
    assert y + h <= fmt.height - inset + 0.5

    # Intrinsic aspect ratio and contracted maximum width.
    assert w / h == pytest.approx(asset_ratio, rel=1e-3)
    assert w <= fmt.width * brand.logo.max_width_pct / 100.0 + 0.5


def test_pipeline_uses_official_logo_without_placeholder_warning(tmp_path):
    broker = MockAssetBroker(tmp_path / "assets", allow_placeholder_logo=True)
    pipeline = Pipeline(broker=broker, renderer=MockRenderer())
    result = pipeline.run(BRIEF, output_dir=tmp_path / "run", max_candidates=1)

    assert result.success, result.message
    assert result.assets.logo is not None
    assert result.assets.logo.placeholder is False
    assert Path(result.assets.logo.path).resolve() == OFFICIAL_LOGO.resolve()
    assert "logo_placeholder" not in {issue.code for issue in result.gates.warnings}


def test_provenance_manifest_matches_canonical_asset():
    manifest_path = OFFICIAL_LOGO.parent / "provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["canonical"] == "kct_logo.png"
    record = next(item for item in manifest["assets"] if item["file"] == "kct_logo.png")
    with _official_image() as image:
        assert record["width"] == image.width
        assert record["height"] == image.height
        assert record["aspect_ratio"] == pytest.approx(
            image.width / image.height, abs=0.01
        )
