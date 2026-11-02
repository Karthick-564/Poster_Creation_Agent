"""Unit and contract tests for VectorCraft MCP Server."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from poster_agent.mcp.vectorcraft_server import VectorCraftMCPServer
from poster_agent.renderer.vectorcraft_renderer import VectorCraftResult


@pytest.fixture
def mcp_server(tmp_path):
    srv = VectorCraftMCPServer(session_id="test_mcp_session", base_dir=Path.cwd())
    # Override session dir to tmp_path to avoid cluttering runs during unit tests
    srv.session_dir = tmp_path / "runs" / "test_mcp_session"
    srv.session_dir.mkdir(parents=True, exist_ok=True)
    return srv


def test_tool_definitions_list(mcp_server):
    tools = mcp_server.get_tool_definitions()
    tool_names = {t["name"] for t in tools}
    expected = {
        "create_doc",
        "load_brief",
        "add_shape_rectangle",
        "add_text",
        "place_image",
        "soft_scrim",
        "radial_light",
        "measure",
        "render_preview",
        "save_session",
        "load_session",
        "export",
    }
    assert expected.issubset(tool_names)


def test_verbatim_validation_no_brief(mcp_server):
    mcp_server.create_doc(1080, 1920)
    res = mcp_server.add_text("ANY TEXT", 100, 100, 24)
    assert "error" in res
    assert "VerbatimValidationError" in res["error"]
    assert "no brief loaded" in res["error"]


def test_verbatim_validation_rejects_hallucination(mcp_server):
    mcp_server.create_doc(1080, 1920)
    load_res = mcp_server.load_brief("briefs/brief_c4_demo.txt")
    assert load_res.get("status") == "ok"

    # Completely fabricated copy
    res = mcp_server.add_text("FREE CRYPTO GIVEAWAY", 100, 100, 32)
    assert "error" in res
    assert "VerbatimValidationError" in res["error"]
    assert "FREE CRYPTO GIVEAWAY" in res["error"]

    # Partial token boundary check (e.g. 'Recruit' against 'We Are Recruiting')
    res_sub = mcp_server.add_text("Recruit", 100, 100, 32)
    assert "error" in res_sub
    assert "VerbatimValidationError" in res_sub["error"]


def test_verbatim_validation_accepts_valid_content(mcp_server):
    mcp_server.create_doc(1080, 1920)
    load_res = mcp_server.load_brief("briefs/brief_c4_demo.txt")
    assert load_res.get("status") == "ok"

    res = mcp_server.add_text("GDG KCT", 100, 100, 48, role="headline")
    assert res.get("status") == "ok"
    assert "row_id" in res
    assert len(mcp_server.manifest_rows) == 1
    assert mcp_server.manifest_rows[0]["text"] == "GDG KCT"


def test_place_image_security_and_path_validation(mcp_server):
    # Path outside project root (platform-neutral /etc/passwd style)
    outside_path = "/etc/passwd"
    res = mcp_server.place_image(outside_path)
    assert "error" in res
    assert "SecurityError" in res["error"]

    # Non-existent path inside project
    missing_path = "assets/non_existent_fake_image_12345.png"
    res2 = mcp_server.place_image(missing_path)
    assert "error" in res2
    assert "FileNotFoundError" in res2["error"]


def test_contrast_floor_catches_white_on_white_and_blocks_export(mcp_server, tmp_path):
    mcp_server.create_doc(1080, 1920)
    mcp_server.load_brief("briefs/brief_c4_demo.txt")

    # Plant white text on default white canvas (#FFFFFF on #FFFFFF)
    res = mcp_server.add_text("We Are Recruiting", 100, 400, 72, color="#FFFFFF", role="headline")
    assert res.get("status") == "ok"

    measure_res = mcp_server.measure()
    assert measure_res["passed"] is False
    failures = measure_res["failures"]
    contrast_failures = [f for f in failures if f["kind"] == "contrast"]
    assert len(contrast_failures) >= 1
    assert "Low contrast" in contrast_failures[0]["detail"]
    assert contrast_failures[0]["measured"]["contrast_ratio"] == 1.0

    # Export MUST be blocked while contrast fails
    out_png = tmp_path / "contrast_blocked.png"
    export_res = mcp_server.export(str(out_png))
    assert "error" in export_res
    assert "ExportBlockedError" in export_res["error"]

    # Remediate by adding dark background rectangle
    mcp_server.add_shape_rectangle(0, 0, 1080, 1920, fill="#070B19")
    rem_measure = mcp_server.measure()
    rem_contrast_failures = [f for f in rem_measure["failures"] if f["kind"] == "contrast"]
    assert len(rem_contrast_failures) == 0


def test_measure_pure_coordinate_math_catches_defects(mcp_server):
    mcp_server.create_doc(1080, 1920)
    mcp_server.load_brief("briefs/brief_c4_demo.txt")

    # 1. Plant canvas bounds escape
    res_esc = mcp_server.add_text("RECRUITMENT 2026", 10, 10, 60, role="headline")
    assert res_esc.get("status") == "ok"

    # 2. Plant row overlap (exact same coordinates)
    res_ov = mcp_server.add_text("RECRUITMENT 2026", 10, 10, 60, role="headline_duplicate")
    assert res_ov.get("status") == "ok"

    measure_res = mcp_server.measure()
    assert measure_res["passed"] is False
    assert measure_res["failure_count"] >= 2
    failures = measure_res["failures"]
    kinds = {f["kind"] for f in failures}
    assert "canvas_bounds" in kinds
    assert "row_overlap" in kinds
    assert "dedupe" in kinds
    assert measure_res["score"] < 10.0


def test_export_blocked_on_unmeasured_or_failed_gates(mcp_server, tmp_path):
    mcp_server.create_doc(1080, 1920)
    out_png = tmp_path / "out.png"

    # Blocked: measure() not run yet
    res = mcp_server.export(str(out_png))
    assert "error" in res
    assert "ExportBlockedError" in res["error"]
    assert "measure() has not been run" in res["error"]

    # Blocked: measure() failed
    mcp_server.load_brief("briefs/brief_c4_demo.txt")
    mcp_server.add_text("GDG KCT", 5, 5, 50)  # escapes safe margin (x=5 < 48.6)
    mcp_server.measure()
    res2 = mcp_server.export(str(out_png))
    assert "error" in res2
    assert "ExportBlockedError" in res2["error"]
    assert "failing QA gates" in res2["error"]


def test_export_permitted_when_green(mcp_server, tmp_path):
    mcp_server.create_doc(1080, 1920)
    mcp_server.load_brief("briefs/brief_c4_demo.txt")

    # Layout covering required content, margins, and vertical bands with verbatim text
    res1 = mcp_server.add_text("LEARN / BUILD / GROW", 100, 100, 24, role="eyebrow")
    assert res1.get("status") == "ok"
    res2 = mcp_server.add_text("We Are Recruiting", 100, 400, 72, role="headline")
    assert res2.get("status") == "ok"
    res3 = mcp_server.add_text("OPEN POSITIONS", 100, 800, 36, role="subtitle")
    assert res3.get("status") == "ok"
    res4 = mcp_server.add_text("Team Members", 100, 950, 28, role="position")
    assert res4.get("status") == "ok"
    res5 = mcp_server.add_text("Wednesday, 12 November 2026, 10:00 AM", 100, 1200, 24, role="date")
    assert res5.get("status") == "ok"
    res6 = mcp_server.add_text("GDG KCT Lounge, Kumaraguru College of Technology", 100, 1300, 22, role="venue")
    assert res6.get("status") == "ok"
    res7 = mcp_server.add_text("Apply Online", 100, 1600, 32, role="cta")
    assert res7.get("status") == "ok"
    res8 = mcp_server.add_text("BE THE CHANGE. JOIN GDG KCT!", 100, 1750, 20, role="closing")
    assert res8.get("status") == "ok"

    measure_res = mcp_server.measure()
    assert measure_res["passed"] is True
    assert measure_res["failure_count"] == 0

    # Mock renderer execute to decouple test from external CLI binary
    mcp_server.renderer.execute = MagicMock(return_value=VectorCraftResult(
        success=True,
        output_png=tmp_path / "final.png",
        execution_time_sec=0.12,
        command_count=len(mcp_server.renderer.commands),
    ))

    out_png = tmp_path / "final.png"
    export_res = mcp_server.export(str(out_png))
    assert export_res.get("status") == "ok"
    assert export_res.get("score") == 10.0
    mcp_server.renderer.execute.assert_called_once()


def test_session_save_and_load_roundtrip(mcp_server, tmp_path):
    mcp_server.create_doc(1080, 1920)
    mcp_server.load_brief("briefs/brief_c4_demo.txt")
    mcp_server.soft_scrim(0, 0, 1080, 400, direction="to_bottom")
    mcp_server.add_text("GDG KCT", 100, 200, 40, role="headline")

    vcs_path = tmp_path / "test_session.vcs"
    save_res = mcp_server.save_session(str(vcs_path))
    assert save_res.get("status") == "ok"
    assert vcs_path.exists()

    # Load in fresh server instance
    new_server = VectorCraftMCPServer(session_id="roundtrip_session", base_dir=Path.cwd())
    load_res = new_server.load_session(str(vcs_path))
    assert load_res.get("status") == "ok"
    assert new_server.doc_width == 1080.0
    assert new_server.doc_height == 1920.0
    assert len(new_server.manifest_rows) == 1
    assert new_server.manifest_rows[0]["text"] == "GDG KCT"
    assert len(new_server.renderer.commands) == len(mcp_server.renderer.commands)


def test_jsonrpc_protocol_framing(mcp_server):
    # 1. Initialize
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    }
    resp = mcp_server.handle_message(init_msg)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "vectorcraft-mcp"

    # 2. Notification (no id) -> None
    notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    assert mcp_server.handle_message(notif) is None

    # 3. Tools list
    tl_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    resp2 = mcp_server.handle_message(tl_msg)
    assert resp2["id"] == 2
    assert "tools" in resp2["result"]

    # 4. Tools call
    call_msg = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "create_doc",
            "arguments": {"width": 1080, "height": 1920},
        },
    }
    resp3 = mcp_server.handle_message(call_msg)
    assert resp3["id"] == 3
    assert resp3["result"]["isError"] is False
    content_data = json.loads(resp3["result"]["content"][0]["text"])
    assert content_data["doc_width"] == 1080.0

    # 5. Unknown method protocol error
    bad_msg = {"jsonrpc": "2.0", "id": 4, "method": "unknown_rpc_method"}
    resp4 = mcp_server.handle_message(bad_msg)
    assert resp4["id"] == 4
    assert "error" in resp4
    assert resp4["error"]["code"] == -32601


def test_design_tools_dispatch(mcp_server):
    mcp_server.create_doc(1080, 1350)
    
    # Test add_shape_ellipse
    res_ell = mcp_server.add_shape_ellipse(100, 200, 50, 50, fill="#00F5D4")
    assert res_ell["status"] == "ok"
    assert res_ell["ellipse"] == [100.0, 200.0, 50.0, 50.0]

    # Test add_path
    res_path = mcp_server.add_path("M 0 0 L 100 100 Z", stroke="#FF3D68", stroke_width=2.0)
    assert res_path["status"] == "ok"
    assert res_path["d"] == "M 0 0 L 100 100 Z"

    # Test set_transparency
    res_tr = mcp_server.set_transparency(opacity=0.8, blend="screen")
    assert res_tr["status"] == "ok"
    assert res_tr["blend"] == "screen"

    # Test add_effect
    res_eff = mcp_server.add_effect("stylize.feather", params={"radius": 15.0})
    assert res_eff["status"] == "ok"
    assert res_eff["effect"] == "stylize.feather"

