"""Tests for the v2 MCP frontend. No network or Windows binary required."""
from pathlib import Path

from poster_agent.mcp.v2_server import V2PosterMCPServer

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


def _server(project_root: Path | None = None) -> V2PosterMCPServer:
    return V2PosterMCPServer(project_root=project_root or Path.cwd(), session_id="test_v2_mcp")


def test_tool_definitions_cover_core_and_designer():
    names = {tool["name"] for tool in _server().get_tool_definitions()}
    assert names == {"run_poster", "plan_poster", "get_brand_contract", "list_schools"}


def test_brand_and_candidate_tools():
    server = _server()
    brand = server.get_brand_contract("KCT")
    assert brand["palette"]["primary"] == "#1E2842"
    assert brand["logo"]["clear_space_mm"] == 10.0

    plan = server.plan_poster(brief_text=BRIEF, format_name="square")
    assert len(plan["candidates"]) >= 3
    scores = [candidate["score"] for candidate in plan["candidates"]]
    assert scores == sorted(scores, reverse=True)
    assert plan["format"]["width"] == 1080


def test_run_poster_mock_passes_and_writes_raster(tmp_path):
    server = _server()
    result = server.run_poster(
        brief_text=BRIEF,
        output_dir=str(tmp_path / "run"),
        max_candidates=1,
    )
    assert result["success"] is True
    assert result["gates"]["passed"] is True
    assert Path(result["output_path"]).exists()
    assert result["candidate"] == "hero-band"


def test_run_poster_rejects_unknown_mode(tmp_path):
    result = _server().run_poster(
        brief_text=BRIEF,
        mode="teleport",
        output_dir=str(tmp_path / "run"),
    )
    assert "error" in result
    assert "mode" in result["error"]


def test_json_rpc_lifecycle(tmp_path):
    server = _server()
    initialized = server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    assert initialized["result"]["serverInfo"]["name"] == "poster-v2-mcp"

    listed = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert len(listed["result"]["tools"]) == 4

    called = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_brand_contract",
                "arguments": {"school": "KCT"},
            },
        }
    )
    assert called["result"]["isError"] is False
    assert '"school_id": "KCT"' in called["result"]["content"][0]["text"]

    unknown = server.handle_message({"jsonrpc": "2.0", "id": 4, "method": "nope"})
    assert unknown["error"]["code"] == -32601

    assert server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_tool_returns_error():
    result = _server().dispatch_tool("rm_rf", {"path": "/"})
    assert "ToolNotFound" in result["error"]
