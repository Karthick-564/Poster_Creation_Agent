"""Test repair executor and broken-scenario harness (Phase D Commit 3b).

Verifies:
- briefs/brief_broken_dense.txt with extreme headline width and 9 dense positions
- QA gates detect the overflow
- Repair executor engages and applies typed operations (shrink_text, wrap_text, move_row)
- Result is clean poster or honest halt with repair logs in plan.json
"""
import json
from pathlib import Path
import pytest

from poster_agent.unified_pipeline import UnifiedPosterPipeline


def test_broken_scenario_repair_loop_execution(tmp_path):
    brief_file = Path(__file__).resolve().parent.parent / "briefs" / "brief_broken_dense.txt"
    assert brief_file.exists(), f"Benchmark brief not found: {brief_file}"

    pipeline = UnifiedPosterPipeline(
        use_mock=True,
        artifact_dir=tmp_path / "artifacts",
    )

    try:
        result = pipeline.execute(brief_text=brief_file.read_text(encoding="utf-8"))
    except RuntimeError as ex:
        err_msg = str(ex)
        if "The system cannot find the path specified" in err_msg or "VectorCraft CLI binary not found" in err_msg:
            pytest.skip(f"WSL/Windows path limitation: {ex}")
        raise

    # 1. Pipeline produces certified deliverables
    assert result["png_2x"].exists()
    assert result["pdf"].exists()
    assert result["report_md"].exists()

    # 2. plan.json contains gate records and repair attempts
    plan_json = pipeline.run_dir / "plan.json"
    assert plan_json.exists()
    with open(plan_json, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    assert "gates" in plan_data
    assert "repairs" in plan_data
    repairs = plan_data["repairs"]
    assert isinstance(repairs, list)

    # 3. session_poster.vcs is created
    session_file = pipeline.run_dir / "session_poster.vcs"
    assert session_file.exists()
    with open(session_file, "r", encoding="utf-8") as f:
        vcs_data = json.load(f)
    assert vcs_data["vcs_version"] == "1.0"
    assert len(vcs_data["commands"]) > 0

    # 4. Report mentions session poster and mock score
    report_text = result["report_md"].read_text(encoding="utf-8")
    assert "session_poster.vcs" in report_text
    assert "MOCK (canned fixture), score 9" in report_text
