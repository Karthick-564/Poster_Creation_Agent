"""Unit test for editable VectorCraft session files (.vcs) (Phase D Commit 3b).

Verifies:
- Saving full VectorCraft command stream to session_poster.vcs
- Reloading session via load_session()
- Re-executing produces an identical text manifest and command stream
"""
import json
from pathlib import Path
import pytest
from PIL import Image

from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.renderer.composer import compose
from poster_agent.renderer.vectorcraft_renderer import VectorCraftRenderer


CLI_PATH = (
    Path(__file__).resolve().parent.parent
    / "tools"
    / "vectorcraft_bin"
    / "vectorcraft-0.19.0-windows-x64-portable"
    / "vectorcraft-cli.exe"
)


def test_session_vcs_save_and_reload(tmp_path):
    brief_text = """
    POSTER BRIEF: SESSION TEST
    Format: 1080 x 1920 px (9:16 story)
    Title: VCS SESSION DEMO
    Eyebrow: EDITABLE POSTER
    Tagline: HAND EDITABLE COMMAND STREAM
    Call to action: Learn More
    """
    extractor = BriefExtractor()
    brief = extractor.extract(brief_text)
    bg_p = tmp_path / "bg.png"
    Image.new("RGB", (1080, 1920), "#070B19").save(bg_p)

    vc = compose(
        brief=brief,
        palette=["#070B19", "#00F5D4", "#FEE440", "#FFFFFF"],
        bg_path=bg_p,
        archetype="focal_point",
        width=1080.0,
        height=1920.0,
        layout_plan={"slots": []},
    )

    session_path = tmp_path / "session_poster.vcs"
    metadata = {"title": "VCS SESSION DEMO", "run_id": "test_run_123"}
    vc.save_session(session_path, metadata=metadata)

    assert session_path.exists()

    with open(session_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["vcs_version"] == "1.0"
    assert data["metadata"]["title"] == "VCS SESSION DEMO"
    assert len(data["commands"]) == len(vc.commands)

    # Reload from session
    reloaded_vc = VectorCraftRenderer.load_session(session_path)
    assert len(reloaded_vc.commands) == len(vc.commands)
    assert reloaded_vc.doc_width == vc.doc_width
    assert reloaded_vc.doc_height == vc.doc_height
    assert len(reloaded_vc._queued_texts) == len(vc._queued_texts)


def test_session_vcs_re_render_parity(tmp_path):
    if not CLI_PATH.exists():
        pytest.skip("VectorCraft CLI binary not found")

    brief_text = """
    POSTER BRIEF: RE-RENDER PARITY
    Format: 1080 x 1920 px (9:16 story)
    Title: PARITY TEST
    Eyebrow: SESSION V2
    Tagline: IDENTICAL MANIFEST
    """
    extractor = BriefExtractor()
    brief = extractor.extract(brief_text)
    bg_p = tmp_path / "bg.png"
    Image.new("RGB", (1080, 1920), "#070B19").save(bg_p)

    vc1 = compose(
        brief=brief,
        palette=["#070B19", "#00F5D4", "#FEE440", "#FFFFFF"],
        bg_path=bg_p,
        archetype="focal_point",
        width=1080.0,
        height=1920.0,
        layout_plan={"slots": []},
    )
    vc1.cli_path = CLI_PATH

    out1_png = tmp_path / "render1.png"
    try:
        res1 = vc1.execute(output_png=out1_png, work_dir=tmp_path / "work1")
    except RuntimeError as ex:
        if "The system cannot find the path specified" in str(ex):
            pytest.skip("WSL path interop limitation")
        raise
    if not res1.success and res1.error_message and "The system cannot find the path specified" in res1.error_message:
        pytest.skip(f"WSL path limitation: {res1.error_message}")

    assert res1.success

    # Save session
    session_file = tmp_path / "session_poster.vcs"
    vc1.save_session(session_file)

    # Reload and re-render
    reloaded_vc = VectorCraftRenderer.load_session(session_file, cli_path=CLI_PATH)
    out2_png = tmp_path / "render2.png"
    try:
        res2 = reloaded_vc.execute(output_png=out2_png, work_dir=tmp_path / "work2")
    except RuntimeError as ex:
        if "The system cannot find the path specified" in str(ex):
            pytest.skip("WSL path interop limitation")
        raise
    if not res2.success and res2.error_message and "The system cannot find the path specified" in res2.error_message:
        pytest.skip(f"WSL path limitation: {res2.error_message}")

    assert res2.success

    # Text manifest parity check
    m1_texts = [item.get("text") for item in res1.text_manifest]
    m2_texts = [item.get("text") for item in res2.text_manifest]
    assert m1_texts == m2_texts
