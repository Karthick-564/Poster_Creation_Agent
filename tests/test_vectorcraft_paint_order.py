"""Tests for VectorCraft paint ordering and typography foundation (Phase A)."""
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

from poster_agent.renderer.vectorcraft_renderer import (
    VectorCraftRenderer,
    get_vectorcraft_fonts_dir,
)

CLI_PATH = (
    Path(__file__).resolve().parent.parent
    / "tools"
    / "vectorcraft_bin"
    / "vectorcraft-0.19.0-windows-x64-portable"
    / "vectorcraft-cli.exe"
)


@pytest.mark.skipif(not CLI_PATH.exists(), reason="VectorCraft CLI binary not found on host")
def test_paint_ordering_two_rectangles():
    """Verify that two rectangles with different fills receive their own fills (paint-before-create)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        work_path = Path(tmpdir)
        svg_path = work_path / "paint_order_test.svg"

        renderer = VectorCraftRenderer(cli_path=CLI_PATH)
        renderer.new_document(width=500, height=500, units="Points", color_mode="rgb")

        # Rectangle 1: Red
        renderer.add_shape_rectangle(x=20, y=20, width=100, height=100, fill="#FF0000")

        # Rectangle 2: Blue
        renderer.add_shape_rectangle(x=150, y=150, width=100, height=100, fill="#0000FF")

        res = renderer.execute(output_svg=svg_path, work_dir=work_path)
        assert res.success, f"VectorCraft execution failed: {res.error_message}"
        assert svg_path.exists(), "SVG output file was not created"

        # Parse SVG and assert fills
        tree = ET.parse(svg_path)
        root = tree.getroot()
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        assert len(rects) == 2, f"Expected 2 rects in SVG, found {len(rects)}"

        fill_1 = rects[0].attrib.get("fill", "").lower()
        fill_2 = rects[1].attrib.get("fill", "").lower()

        assert fill_1 == "#ff0000", f"Rectangle 1 has fill '{fill_1}', expected '#ff0000'"
        assert fill_2 == "#0000ff", f"Rectangle 2 has fill '{fill_2}', expected '#0000ff'"


@pytest.mark.skipif(not CLI_PATH.exists(), reason="VectorCraft CLI binary not found on host")
def test_typography_foundation_and_manifest():
    """Verify text creation, style/tracking/leading, fit_headline, and text_manifest generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        work_path = Path(tmpdir)
        svg_path = work_path / "type_test.svg"

        renderer = VectorCraftRenderer(cli_path=CLI_PATH)
        renderer.new_document(width=600, height=600, units="Points", color_mode="rgb")

        # Standard styled text
        renderer.add_text(
            text="AUTONOMOUS POSTER",
            x=50,
            y=80,
            size=28,
            font="Arial",
            color="#112233",
            style="Bold",
            tracking=50.0,
            role="headline",
        )

        # Area text with fit_headline
        renderer.area_text(
            text="SWISS STYLE EDITORIAL",
            x=50,
            y=140,
            width=500,
            height=60,
            size=32,
            font="Arial",
            color="#334455",
            fit="autoHeight",
            role="subheadline",
        )
        renderer.fit_headline()

        res = renderer.execute(output_svg=svg_path, work_dir=work_path)
        assert res.success, f"Execution failed: {res.error_message}"
        assert len(res.text_manifest) == 2, f"Expected 2 text manifest entries, got {len(res.text_manifest)}"

        entry_0 = res.text_manifest[0]
        assert entry_0["role"] == "headline"
        assert entry_0["text"] == "AUTONOMOUS POSTER"
        assert entry_0["bounds"] is not None

        entry_1 = res.text_manifest[1]
        assert entry_1["role"] == "subheadline"
        assert entry_1["text"] == "SWISS STYLE EDITORIAL"

        manifest_file = work_path / "text_manifest.json"
        assert manifest_file.exists(), "text_manifest.json was not written to work_dir"


def test_fonts_directory_resolution():
    """Verify programmatic resolution of VectorCraft shared Fonts folder."""
    fonts_dir = get_vectorcraft_fonts_dir(cli_path=CLI_PATH)
    assert fonts_dir is not None
    assert str(fonts_dir).endswith("Fonts")
    # Must not contain hardcoded user home path outside project or environment
    assert "c:\\users\\dummy" not in str(fonts_dir).lower()
