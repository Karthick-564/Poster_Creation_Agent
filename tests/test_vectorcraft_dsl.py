"""Unit tests for VectorCraft Rich Renderer DSL (Phase B).

Covers:
- Mock-safe command structure assertions (no CLI execution required).
- Headless execution smoke test exercising fit_headline + dropShadow + soft_scrim + radial_light + orbital_text.
"""
import tempfile
from pathlib import Path
import pytest

from poster_agent.renderer.vectorcraft_renderer import VectorCraftRenderer

CLI_PATH = (
    Path(__file__).resolve().parent.parent
    / "tools"
    / "vectorcraft_bin"
    / "vectorcraft-0.19.0-windows-x64-portable"
    / "vectorcraft-cli.exe"
)


def test_command_structure_soft_scrim():
    """Verify soft_scrim command structure and paint-before-create sequence."""
    renderer = VectorCraftRenderer(cli_path=CLI_PATH if CLI_PATH.exists() else Path("dummy/path"))
    renderer.soft_scrim(
        x=0,
        y=0,
        width=1080,
        height=400,
        stops=[(0.0, "#000000", 0.9), (1.0, "#000000", 0.0)],
        direction="to_bottom",
    )

    cmds = renderer.commands
    assert len(cmds) == 3
    assert cmds[0]["command"] == "select.none"
    assert cmds[1]["command"] == "paint.setFill"
    assert "gradient" in cmds[1]["params"]

    grad = cmds[1]["params"]["gradient"]
    assert grad["kind"] == "linear"
    assert len(grad["stops"]) == 2
    assert grad["stops"][0]["opacity"] == 0.9
    assert grad["stops"][1]["opacity"] == 0.0
    assert grad["start"] == [540.0, 0]
    assert grad["end"] == [540.0, 400]

    assert cmds[2]["command"] == "shape.rectangle"
    assert cmds[2]["params"] == {"x": 0, "y": 0, "width": 1080, "height": 400}


def test_command_structure_radial_light():
    """Verify radial_light emits gradient fill, ellipse, and transparency.set blend."""
    renderer = VectorCraftRenderer(cli_path=CLI_PATH if CLI_PATH.exists() else Path("dummy/path"))
    renderer.radial_light(
        cx=300,
        cy=400,
        radius=150,
        color="#00F5D4",
        alpha_stop_inner=0.8,
        alpha_stop_outer=0.0,
        blend_mode="screen",
    )

    cmds = renderer.commands
    assert len(cmds) == 4
    assert cmds[0]["command"] == "select.none"
    assert cmds[1]["command"] == "paint.setFill"
    assert cmds[1]["params"]["gradient"]["kind"] == "radial"
    assert cmds[2]["command"] == "shape.ellipse"
    assert cmds[2]["params"] == {"x": 150.0, "y": 250.0, "width": 300.0, "height": 300.0}
    assert cmds[3]["command"] == "transparency.set"
    assert cmds[3]["params"]["blend"] == "screen"


def test_command_structure_orbital_text():
    """Verify orbital_text creates path and attaches text.createInPath referencing $last.id."""
    renderer = VectorCraftRenderer(cli_path=CLI_PATH if CLI_PATH.exists() else Path("dummy/path"))
    renderer.orbital_text(
        path_d="M 100 200 C 200 150 400 150 500 200",
        text="CURVED EDITORIAL HEADLINE",
        size=24,
        font="Bahnschrift",
        color="#FFFFFF",
        role="curved_title",
    )

    cmds = renderer.commands
    assert len(cmds) == 2
    assert cmds[0]["command"] == "path.create"
    assert cmds[0]["params"]["d"] == "M 100 200 C 200 150 400 150 500 200"

    assert cmds[1]["command"] == "text.createInPath"
    params = cmds[1]["params"]
    assert params["path"] == "$last.id"
    assert params["mode"] == "onPath"
    assert params["text"] == "CURVED EDITORIAL HEADLINE"
    assert params["size"] == 24


def test_command_structure_add_effect():
    """Verify add_effect targets $last.id or specific id."""
    renderer = VectorCraftRenderer(cli_path=CLI_PATH if CLI_PATH.exists() else Path("dummy/path"))
    renderer.add_effect("stylize.dropShadow", params={"blur": 5.0}, target_id="$last")

    cmds = renderer.commands
    assert len(cmds) == 1
    assert cmds[0]["command"] == "effect.apply"
    assert cmds[0]["params"]["effect"] == "stylize.dropShadow"
    assert cmds[0]["params"]["id"] == "$last.id"
    assert cmds[0]["params"]["params"]["blur"] == 5.0


@pytest.mark.skipif(not CLI_PATH.exists(), reason="VectorCraft CLI binary not found on host")
def test_headless_smoke_rich_dsl():
    """Headless integration smoke test verifying engine execution of rich DSL helpers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        work_path = Path(tmpdir)
        png_path = work_path / "rich_dsl_smoke.png"

        renderer = VectorCraftRenderer(cli_path=CLI_PATH)
        renderer.new_document(width=600, height=800, units="Points", color_mode="rgb", raster_resolution=300)

        # 1. Soft scrim (dark header fade)
        renderer.soft_scrim(
            x=0, y=0, width=600, height=350,
            stops=[(0.0, "#0B132B", 0.9), (1.0, "#0B132B", 0.0)],
            direction="to_bottom",
        )

        # 2. Radial atmospheric light
        renderer.radial_light(
            cx=300, cy=300, radius=200,
            color="#00F5D4", alpha_stop_inner=0.7, alpha_stop_outer=0.0,
            blend_mode="screen",
        )

        # 3. Area text + fit_headline
        renderer.area_text(
            text="FESTIVAL OF DESIGN",
            x=50, y=80, width=500, height=60,
            size=36, font="Arial", color="#FFFFFF",
            fit="autoHeight", role="main_headline",
        )
        renderer.fit_headline()

        # 4. Attach dropShadow effect to headline
        renderer.add_effect(
            effect_name="stylize.dropShadow",
            params={"mode": "multiply", "opacity": 75.0, "x": 0.0, "y": 6.0, "blur": 8.0, "color": "#000000"},
            target_id="$last",
        )

        # 5. Orbital text along a spline
        renderer.orbital_text(
            path_d="M 100 500 C 200 450 400 450 500 500",
            text="AUTONOMOUS PRINT PIPELINE 2026",
            size=16, font="Arial", color="#00BBF9",
            role="banner_curve",
        )

        res = renderer.execute(output_png=png_path, work_dir=work_path)

        assert res.success, f"Headless execution failed: {res.error_message}"
        assert png_path.exists(), "Output PNG was not generated"
        assert png_path.stat().st_size > 10000, "PNG file is unexpectedly tiny"

        # Check step results: all executed successfully
        for step in res.step_results:
            assert step.get("step") in ("cmd", "export"), f"Unexpected step: {step}"

        # Check manifest
        assert len(res.text_manifest) >= 2
        roles = [m["role"] for m in res.text_manifest]
        assert "main_headline" in roles
        assert "banner_curve" in roles
