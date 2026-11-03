"""Gate tests for logo, hero alpha, OCR and the mock end-to-end slice."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.v2.assets import MockAssetBroker
from poster_agent.v2.brand import get_brand, resolve_format
from poster_agent.v2.composer import MockRenderer
from poster_agent.v2.contracts import (
    AssetBundle,
    Box,
    FormatSpec,
    ManifestRow,
    PosterSpec,
    RenderResult,
    ResolvedImage,
    TextBlock,
)
from poster_agent.v2.gates import _check_hero_alpha, _check_logo, _check_ocr, run_gates
from poster_agent.v2.pipeline import Pipeline
from poster_agent.v2.planner import KCTPlanner, rescale_logo_to_asset
from poster_agent.v2.reviewer import StaticReviewer

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


def _kct_spec():
    brand = get_brand("KCT")
    fmt = resolve_format(brand, "story")
    brief = BriefExtractor().extract(BRIEF)
    return brand, fmt, KCTPlanner().plan_candidates(brief, brand, fmt)[0]


def _small_spec():
    brand = get_brand("KCT")
    fmt = FormatSpec(width=400, height=600, dpi=300)
    brief = BriefExtractor().extract(BRIEF)
    return brand, fmt, KCTPlanner().plan_candidates(brief, brand, fmt)[0]


def _brand_with_logo(tmp_path, *, create: bool = True):
    """Return the KCT contract pointed at a hermetic temp logo path."""
    brand = get_brand("KCT")
    logo_path = tmp_path / "supplied_logo.png"
    if create:
        Image.new("RGBA", (600, 200), (30, 40, 66, 255)).save(logo_path)
    return brand.model_copy(
        update={"logo": brand.logo.model_copy(update={"asset": str(logo_path)})}
    )


def test_mock_pipeline_passes_end_to_end(tmp_path):
    brand = _brand_with_logo(tmp_path)
    broker = MockAssetBroker(tmp_path / "assets", allow_placeholder_logo=True)
    pipeline = Pipeline(broker=broker, renderer=MockRenderer(), brand=brand)
    result = pipeline.run(BRIEF, output_dir=tmp_path / "run")
    assert result.success, result.message
    assert result.gates.passed
    assert Path(result.output_path).exists()
    assert result.spec.qr is not None
    assert result.assets.logo is not None
    assert result.assets.logo.placeholder is False
    assert not any(issue.code == "logo_placeholder" for issue in result.gates.warnings)
    # The logo was rescaled from the supplied asset.
    # Compare pixel-space aspect ratios (box.w/h are normalised to 0-1000 on
    # independent axes, so they must be converted to pixels before dividing).
    fmt = result.spec.format
    _lx, _ly, lw_px, lh_px = result.spec.logo_slots[0].box.to_px(fmt.width, fmt.height)
    assert abs(
        (lw_px / lh_px)
        - (result.assets.logo.width / result.assets.logo.height)
    ) < 0.05


def test_missing_logo_blocks_delivery(tmp_path):
    brand = _brand_with_logo(tmp_path, create=False)
    broker = MockAssetBroker(tmp_path / "assets", allow_placeholder_logo=False)
    pipeline = Pipeline(
        broker=broker,
        renderer=MockRenderer(),
        brand=brand,
        max_asset_attempts=1,
    )
    result = pipeline.run(BRIEF, output_dir=tmp_path / "run", max_candidates=1)
    assert result.success is False
    assert any(issue.code == "logo_missing" for issue in result.gates.blocking)


def test_hero_alpha_gate_rejects_opaque_hero(tmp_path):
    brand, fmt, spec = _kct_spec()
    hero = spec.image("hero")
    path = tmp_path / "opaque_hero.png"
    Image.new("RGB", (512, 512), (120, 160, 180)).save(path)
    asset = ResolvedImage(
        slot_id=hero.id,
        role="hero",
        path=str(path),
        source="qwen",
        width=512,
        height=512,
        transparent=False,
    )
    issues = _check_hero_alpha(spec, AssetBundle(images={hero.id: asset}))
    assert any(issue.code == "hero_not_alpha" for issue in issues)


def test_hero_alpha_gate_rejects_fully_opaque_rgba(tmp_path):
    brand, fmt, spec = _kct_spec()
    hero = spec.image("hero")
    path = tmp_path / "opaque_rgba.png"
    Image.new("RGBA", (512, 512), (120, 160, 180, 255)).save(path)
    asset = ResolvedImage(
        slot_id=hero.id,
        role="hero",
        path=str(path),
        source="qwen",
        width=512,
        height=512,
        transparent=True,
    )
    issues = _check_hero_alpha(spec, AssetBundle(images={hero.id: asset}))
    assert any(issue.code == "hero_alpha_coverage" for issue in issues)


def test_hero_alpha_gate_accepts_bright_cutout(tmp_path):
    brand, fmt, spec = _kct_spec()
    hero = spec.image("hero")
    arr = np.zeros((512, 512, 4), dtype=np.uint8)
    arr[100:400, 100:400] = [180, 170, 160, 255]
    path = tmp_path / "cutout.png"
    Image.fromarray(arr, "RGBA").save(path)
    asset = ResolvedImage(
        slot_id=hero.id,
        role="hero",
        path=str(path),
        source="qwen",
        width=512,
        height=512,
        transparent=True,
    )
    issues = _check_hero_alpha(spec, AssetBundle(images={hero.id: asset}))
    assert issues == []


def test_logo_solid_field_gate_rejects_gradient(tmp_path):
    brand, fmt, spec = _small_spec()
    logo_asset = tmp_path / "logo.png"
    Image.new("RGBA", (300, 100), (10, 20, 40, 255)).save(logo_asset)
    x, y, w, h = spec.logo_slots[0].box.to_px(fmt.width, fmt.height)

    # Use a full-luminance horizontal gradient (white→black) so the ring
    # around the top-right logo slot has a spread large enough to trigger the
    # solid-field gate (spread > 22 or std > 9).
    arr = np.zeros((fmt.height, fmt.width, 3), dtype=np.uint8)
    ramp = np.linspace(255, 0, fmt.width, dtype=np.uint8)
    arr[:, :, 0] = ramp
    arr[:, :, 1] = ramp
    arr[:, :, 2] = ramp
    render_path = tmp_path / "render.png"
    Image.fromarray(arr).save(render_path)
    render = RenderResult(
        output_png=str(render_path),
        width=fmt.width,
        height=fmt.height,
        rows=[],
        logo_rect=(x, y, w, h),
    )
    asset = ResolvedImage(
        slot_id="brand_logo",
        role="decoration",
        path=str(logo_asset),
        source="supplied",
        width=300,
        height=100,
        transparent=True,
    )
    issues = _check_logo(spec, brand, AssetBundle(logo=asset), render)
    assert any(issue.code == "logo_solid_field" for issue in issues)


def test_ocr_gate_flags_missing_text():
    spec = PosterSpec(
        school_id="KCT",
        candidate_id="test",
        format=FormatSpec(width=400, height=600),
        palette=["#1E2842", "#FFFFFF"],
        background_color="#1E2842",
        text_blocks=[
            TextBlock(
                id="headline",
                role="headline",
                text="AI DESIGN SUMMIT",
                box=Box(x=50, y=50, w=800, h=200),
                size=40,
                color="#FFFFFF",
            )
        ],
        image_slots=[],
        logo_slots=[],
    )
    render = RenderResult(
        output_png="",
        width=400,
        height=600,
        rows=[
            ManifestRow(
                id="headline",
                role="headline",
                text="AI DESIGN SUMMIT",
                x=50,
                y=50,
                width=300,
                height=60,
                size=40,
            )
        ],
    )
    issues = _check_ocr(spec, render, ocr_lines=["completely different words"])
    assert any(issue.code == "ocr_text_mismatch" for issue in issues)

    ok = _check_ocr(spec, render, ocr_lines=["AI DESIGN SUMMIT"])
    assert ok == []


def test_manifest_gates_detect_logo_clear_space_collision(tmp_path):
    brand, fmt, spec = _small_spec()
    logo_asset = tmp_path / "logo.png"
    Image.new("RGBA", (300, 100), (255, 255, 255, 255)).save(logo_asset)
    x, y, w, h = spec.logo_slots[0].box.to_px(fmt.width, fmt.height)
    render_path = tmp_path / "render.png"
    Image.new("RGB", (fmt.width, fmt.height), "#FFFFFF").save(render_path)
    row = ManifestRow(
        id="headline",
        role="headline",
        text="COLLIDING",
        x=x,
        y=y,
        width=w,
        height=h,
        size=20,
    )
    render = RenderResult(
        output_png=str(render_path),
        width=fmt.width,
        height=fmt.height,
        rows=[row],
        logo_rect=(x, y, w, h),
    )
    asset = ResolvedImage(
        slot_id="brand_logo",
        role="decoration",
        path=str(logo_asset),
        source="supplied",
        width=300,
        height=100,
        transparent=True,
    )
    issues = _check_logo(spec, brand, AssetBundle(logo=asset), render)
    assert any(issue.code == "logo_clear_space" for issue in issues)


def test_vlm_review_maps_scores_and_routes_fixes():
    from poster_agent.v2.vlm_reviewer import PosterReviewerV2

    brand = get_brand("KCT")
    result = PosterReviewerV2._to_result(
        {
            "hierarchy": 4,
            "balance": 3,
            "readability": 4,
            "brand_fit": 3,
            "polish": 4,
            "three_second_test": {"passed": True},
            "fixes": [
                "Hero artwork is too small and lacks a clear silhouette.",
                "Headline contrast is weak over the background.",
            ],
        },
        brand,
    )
    assert 0.0 <= result.score <= 10.0
    assert result.score == pytest.approx(7.2)
    assert {issue.stage for issue in result.issues} == {"assets", "plan"}
    assert not result.blocking


def test_vlm_three_second_failure_is_blocking():
    from poster_agent.v2.vlm_reviewer import PosterReviewerV2

    brand = get_brand("KCT")
    result = PosterReviewerV2._to_result(
        {
            "hierarchy": 2,
            "balance": 2,
            "readability": 2,
            "brand_fit": 2,
            "polish": 2,
            "three_second_test": {"passed": False},
            "fixes": [],
        },
        brand,
    )
    assert result.score == pytest.approx(4.0)
    assert any(issue.code == "three_second_test" and issue.severity == "blocking" for issue in result.issues)


def test_review_below_threshold_returns_result_instead_of_raising(tmp_path):
    broker = MockAssetBroker(tmp_path / "assets", allow_placeholder_logo=True)
    pipeline = Pipeline(
        broker=broker,
        renderer=MockRenderer(),
        reviewer=StaticReviewer(score=4.0),
    )
    result = pipeline.run(BRIEF, output_dir=tmp_path / "run", max_candidates=1)

    assert result.success is False
    assert result.review is not None
    assert result.review.score == pytest.approx(4.0)
    assert "below threshold" in result.message
    assert any(attempt.stage == "review" for attempt in result.attempts)
    assert Path(result.output_path).exists()


def test_review_above_threshold_still_passes(tmp_path):
    broker = MockAssetBroker(tmp_path / "assets", allow_placeholder_logo=True)
    pipeline = Pipeline(
        broker=broker,
        renderer=MockRenderer(),
        reviewer=StaticReviewer(score=9.0),
    )
    result = pipeline.run(BRIEF, output_dir=tmp_path / "run", max_candidates=1)

    assert result.success is True
    assert result.review is not None
    assert result.message == "Passed deterministic gates and VLM review."


class _FlakyRenderer:
    """Fail the first render, then delegate to the mock renderer."""

    def __init__(self, failures: int = 1):
        self.failures = failures
        self.calls = 0
        self.inner = MockRenderer()

    def render(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("transient renderer failure")
        return self.inner.render(**kwargs)


def test_compose_failure_retries_same_candidate(tmp_path):
    broker = MockAssetBroker(tmp_path / "assets", allow_placeholder_logo=True)
    renderer = _FlakyRenderer(failures=1)
    pipeline = Pipeline(broker=broker, renderer=renderer, max_compose_attempts=2)

    result = pipeline.run(BRIEF, output_dir=tmp_path / "run", max_candidates=1)

    assert result.success is True
    assert renderer.calls == 2
    assert result.attempts[0].stage == "compose"
    assert result.attempts[0].outcome == "failed"
    assert result.spec.candidate_id == "hero-band"


def test_compose_retry_budget_exhaustion_raises_clearly(tmp_path):
    broker = MockAssetBroker(tmp_path / "assets", allow_placeholder_logo=True)
    renderer = _FlakyRenderer(failures=10)
    pipeline = Pipeline(broker=broker, renderer=renderer, max_compose_attempts=2)

    with pytest.raises(RuntimeError, match="renderable"):
        pipeline.run(BRIEF, output_dir=tmp_path / "run", max_candidates=1)
    assert renderer.calls == 2


def test_square_format_passes_end_to_end(tmp_path):
    broker = MockAssetBroker(tmp_path / "assets", allow_placeholder_logo=True)
    pipeline = Pipeline(broker=broker, renderer=MockRenderer())
    result = pipeline.run(
        BRIEF,
        format_name="square",
        output_dir=tmp_path / "run",
        max_candidates=1,
    )
    assert result.success, result.message
    assert result.spec.format.width == 1080
    assert result.spec.format.height == 1080
