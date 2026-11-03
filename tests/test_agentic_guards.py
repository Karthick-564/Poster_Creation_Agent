"""Fast, pure-logic guard tests for the agentic poster designer.

Guards:
1. Verbatim validation rejects non-brief text, accepts exact text
2. Contrast gate catches a known low-contrast pair
3. Locked items cannot be deleted or moved/updated
4. Export is blocked when any gate fails
5. Free regions calculation treats locked zones and placed items as obstacles
6. Model validation fails loudly on invalid model names
"""
from pathlib import Path
import pytest

from poster_agent.agentic.llm_backend import (
    AnthropicBackend,
    GeminiBackend,
    ModelValidationError,
    get_backend,
)
from poster_agent.agentic.structure import lock_all_zones
from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.mcp.vectorcraft_server import VectorCraftMCPServer


@pytest.fixture
def mcp(tmp_path):
    server = VectorCraftMCPServer(session_id="guard_test_session", base_dir=Path.cwd())
    server.session_dir = tmp_path / "runs" / "guard_test_session"
    server.session_dir.mkdir(parents=True, exist_ok=True)
    server.create_doc(1080, 1920)
    server.load_brief("briefs/brief_c4_demo.txt")
    return server


# ---------------------------------------------------------------------------
# 1. Verbatim Validation
# ---------------------------------------------------------------------------

def test_verbatim_validation_rejects_non_brief_text(mcp):
    """Verbatim check must reject any string not found whole-token in the brief."""
    res = mcp.add_text(
        text="TOTALLY FABRICATED HEADLINE NEVER IN BRIEF",
        x=100,
        y=200,
        size=48,
    )
    assert "error" in res
    assert "VerbatimValidationError" in res["error"]


def test_verbatim_validation_accepts_exact_text(mcp):
    """Verbatim check must accept exact whole-token strings from the brief."""
    res = mcp.add_text(
        text="GDG KCT",
        x=100,
        y=200,
        size=48,
        role="headline",
    )
    assert res.get("status") == "ok"
    assert res.get("item_id") == "headline_1"


# ---------------------------------------------------------------------------
# 2. Contrast Gate
# ---------------------------------------------------------------------------

def test_contrast_gate_catches_low_contrast(mcp):
    """Contrast gate must catch white text on white/light background."""
    # Place white background substrate
    mcp.add_shape_rectangle(x=0, y=0, width=1080, height=1920, fill="#FFFFFF")
    # Place white text on white background
    mcp.add_text(
        text="GDG KCT",
        x=100,
        y=200,
        size=48,
        color="#FFFFFF",
        role="headline",
    )
    measure_res = mcp.measure()
    assert measure_res["passed"] is False
    contrast_fails = [f for f in measure_res["failures"] if f["kind"] == "contrast"]
    assert len(contrast_fails) > 0
    assert "headline_1" in contrast_fails[0]["target"] or "headline" in contrast_fails[0]["target"]


# ---------------------------------------------------------------------------
# 3. Locked Items Immutability
# ---------------------------------------------------------------------------

def test_locked_items_cannot_be_deleted(mcp):
    """Locked items must refuse deletion with a typed LockedItemError."""
    # Place a locked header
    mcp.add_shape_rectangle(
        x=800, y=50, width=200, height=60, fill="#1E2842", item_id="locked_header_logo", locked=True
    )
    del_res = mcp.delete_item("locked_header_logo")
    assert "error" in del_res
    assert "LockedItemError" in del_res["error"]
    assert "locked and cannot be deleted" in del_res["error"]

    # Verify item is still present
    items = mcp.list_items()["items"]
    assert any(it["id"] == "locked_header_logo" for it in items)


def test_locked_items_cannot_be_updated(mcp):
    """Locked items must refuse updates/moves with a typed LockedItemError."""
    mcp.add_shape_rectangle(
        x=0, y=1840, width=1080, height=80, fill="#1E2842", item_id="locked_footer_rect", locked=True
    )
    upd_res = mcp.update_item("locked_footer_rect", {"y": 1000, "height": 40})
    assert "error" in upd_res
    assert "LockedItemError" in upd_res["error"]
    assert "locked and cannot be modified" in upd_res["error"]

    # Verify geometry was not changed
    items = mcp.list_items()["items"]
    rect_item = next(it for it in items if it["id"] == "locked_footer_rect")
    assert rect_item["rect"][1] == 1840.0


# ---------------------------------------------------------------------------
# 4. Export Blockage
# ---------------------------------------------------------------------------

def test_export_is_blocked_when_gate_fails(mcp, tmp_path):
    """Export must be strictly blocked if measure has not run or fails gates."""
    out_png = tmp_path / "test_blocked.png"
    # 1. Blocked before measure
    exp_res1 = mcp.export(output_png=str(out_png))
    assert "error" in exp_res1
    assert "ExportBlockedError" in exp_res1["error"]

    # 2. Blocked when measure fails (white text on white)
    mcp.add_shape_rectangle(x=0, y=0, width=1080, height=1920, fill="#FFFFFF")
    mcp.add_text(text="GDG KCT", x=100, y=200, size=48, color="#FFFFFF")
    mcp.measure()
    exp_res2 = mcp.export(output_png=str(out_png))
    assert "error" in exp_res2
    assert "ExportBlockedError" in exp_res2["error"]
    assert not out_png.exists()


# ---------------------------------------------------------------------------
# 5. Free Regions & Locked Zones Obstacle Treatment
# ---------------------------------------------------------------------------

def test_get_free_regions_treats_locked_zones_as_obstacles(mcp):
    """Free regions calculation must treat locked header, footer, and QR as obstacles."""
    raw_brief = Path("briefs/brief_c4_demo.txt").read_text(encoding="utf-8")
    brief = BriefExtractor().extract(raw_brief)
    lock_res = lock_all_zones(mcp, brief, school_id="KCT")

    assert lock_res["header"]["locked"] is True
    assert lock_res["footer"]["locked"] is True

    free_res = mcp.get_free_regions(min_width=200, min_height=60)
    assert free_res["status"] == "ok"
    assert free_res["free_region_count"] > 0

    # Ensure none of the returned free regions intersect the locked footer bar
    footer_y = lock_res["footer"]["rect"][1]
    for region in free_res["free_regions"]:
        reg_bottom = region["y"] + region["height"]
        assert reg_bottom <= footer_y + 1.0, f"Region {region} overlaps locked footer at y={footer_y}"


def test_list_items_reports_all_fields_and_locked_status(mcp):
    """list_items must report id, type, rect, text, z_order, and locked flag for every item."""
    mcp.add_shape_rectangle(x=0, y=0, width=1080, height=1920, fill="#070B19", item_id="bg_rect")
    mcp.add_shape_rectangle(x=0, y=1840, width=1080, height=80, fill="#1E2842", item_id="locked_bar", locked=True)
    mcp.add_text(text="GDG KCT", x=80, y=200, size=48, role="headline", item_id="head_txt")

    res = mcp.list_items()
    assert res["status"] == "ok"
    assert res["count"] == 3
    items = res["items"]

    it_map = {it["id"]: it for it in items}
    assert it_map["bg_rect"]["locked"] is False
    assert it_map["bg_rect"]["type"] == "rectangle"

    assert it_map["locked_bar"]["locked"] is True
    assert it_map["locked_bar"]["type"] == "rectangle"

    assert it_map["head_txt"]["locked"] is False
    assert it_map["head_txt"]["type"] == "text"
    assert it_map["head_txt"]["text"] == "GDG KCT"


# ---------------------------------------------------------------------------
# 6. Model Validation Fails Loudly
# ---------------------------------------------------------------------------

def test_model_validation_fails_loudly_on_invalid_model():
    """Model backends must validate model names at startup and fail loudly if invalid."""
    with pytest.raises(ModelValidationError):
        AnthropicBackend(model="nonexistent-claude-model-xyz")

    with pytest.raises(ModelValidationError):
        GeminiBackend(model="fake-gemini-hallucinated-model")

    # Valid models must pass validation without error
    backend_anthropic = AnthropicBackend(model="claude-sonnet-5-5")
    assert backend_anthropic.model == "claude-sonnet-5-5"

    backend_gemini = GeminiBackend(model="gemini-2.5-flash")
    assert backend_gemini.model == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# 7. Milestone 3: Critic Checklist & Router Guards
# ---------------------------------------------------------------------------

def test_critic_checklist_schema_and_evaluation():
    """CriticStage must evaluate the 9-point design checklist and return structured proof."""
    from poster_agent.agentic.critic import CriticStage, CRITIC_CHECKLIST_SCHEMA

    critic = CriticStage(backend=None) # Offline deterministic mode
    gate_res = {"passed": True, "failures": [], "v_band_coverage_pct": 85.0}
    manifest = [{"role": "headline", "text": "BIG EVENT"}]

    res = critic.run_checklist_review(
        final_image_path=Path("nonexistent.png"),
        brief_fields={"title": "BIG EVENT"},
        palette=["#070B19", "#00F5D4"],
        gate_results=gate_res,
        manifest_rows=manifest,
        has_hero=False,
        ocr_passed=True,
    )

    assert "items" in res
    assert res["passed"] is True
    for key in CRITIC_CHECKLIST_SCHEMA:
        assert key in res["items"]
        assert "passed" in res["items"][key]
        assert "evidence" in res["items"][key]
        assert "target_stage" in res["items"][key]


def test_router_routes_deterministic_failures_to_s4():
    """Router must map gate collisions/bounds/contrast to S4 Designer."""
    from poster_agent.agentic.router import Router

    router = Router()
    gate_res = {
        "passed": False,
        "failures": [{"kind": "row_overlap", "target": "headline,date", "detail": "Overlap detected"}],
    }
    decision = router.route(cycle=1, gate_results=gate_res, ocr_results={"passed": True})

    assert decision.should_reroute is True
    assert decision.target_stage == "S4"
    assert "row_overlap" in decision.reroute_action.failing_check


def test_router_routes_background_ocr_to_s3():
    """Router must map baked pseudo-text in background to S3 Generation."""
    from poster_agent.agentic.router import Router

    router = Router()
    ocr_res = {
        "passed": False,
        "bg_unmapped_tokens": ["pseudo123"],
        "failures": [{"kind": "background_ocr", "target": "bg.png"}],
    }
    decision = router.route(cycle=1, gate_results={"passed": True}, ocr_results=ocr_res)

    assert decision.should_reroute is True
    assert decision.target_stage == "S3"
    assert decision.reroute_action.target_stage == "S3"


def test_router_halts_on_missing_logo():
    """Router must halt honestly if institutional logo is obstructed or missing (never generate)."""
    from poster_agent.agentic.router import Router

    router = Router()
    gate_res = {
        "passed": False,
        "failures": [{"kind": "bounds", "target": "locked_header_logo", "detail": "Logo obstructed"}],
    }
    decision = router.route(cycle=1, gate_results=gate_res, ocr_results={"passed": True})

    assert decision.should_reroute is False
    assert decision.target_stage == "HALT"
    assert "logo" in decision.halt_reason.lower()


def test_router_halts_honestly_when_cycle_limit_exceeded():
    """Router must halt honestly when reaching the maximum 3 cycles limit."""
    from poster_agent.agentic.router import Router

    router = Router()
    gate_res = {
        "passed": False,
        "failures": [{"kind": "contrast", "target": "venue", "detail": "Low contrast"}],
    }
    decision = router.route(cycle=3, gate_results=gate_res, ocr_results={"passed": True})

    assert decision.should_reroute is False
    assert decision.target_stage == "HALT"
    assert "maximum review cycles" in decision.halt_reason.lower()


