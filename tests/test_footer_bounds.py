"""Unit test for footer bar bottom-edge margin clearance (Phase D Commit 3a).

Verifies:
- Footer bar closing line text bounds respect canvas bottom margin.
- Zero bottom-margin escaping defects.
"""
from poster_agent.renderer.composer import emit_footer_bar_row
from poster_agent.renderer.vectorcraft_renderer import VectorCraftRenderer
from poster_agent.qa.gates import check_canvas_bounds


def test_footer_bar_baseline_respects_canvas_bottom_margin():
    width = 1080.0
    height = 1920.0
    margin_px = width * 0.045  # 48.6 pt
    vc = VectorCraftRenderer()

    row_meta = emit_footer_bar_row(
        vc=vc,
        text="BE THE CHANGE. JOIN GDG KCT!",
        width=width,
        height=height,
        font="Inter",
        fill_color="#1E2842",
        text_color="#FFFFFF",
        bar_height=80.0,
    )

    # Find the text command
    text_cmd = next(c for c in vc.commands if c.get("command") == "text.create")
    p = text_cmd["params"]
    text_y = p["y"]
    size = p["size"]

    # Calculate bounding box bounds as done by QA gates
    top_y = text_y - (size * 0.88)
    bottom_y = top_y + (size * 1.15)

    # Assert strictly inside safe canvas bounds
    max_safe_y = height - margin_px
    assert bottom_y <= max_safe_y + 0.01, (
        f"Footer text bottom {bottom_y:.2f} escapes bottom safe margin {max_safe_y:.2f}"
    )

    # Also verify via check_canvas_bounds gate
    row_manifest = [{
        "id": "footer_row",
        "role": "_structure_footer",
        "bounds": {
            "x": p["x"] - 100.0,
            "y": top_y,
            "width": 200.0,
            "height": size * 1.15,
        },
    }]
    failures = check_canvas_bounds(row_manifest, canvas_w=width, canvas_h=height, margin_px=margin_px)
    assert len(failures) == 0, f"Canvas bounds gate failed on footer: {failures}"
