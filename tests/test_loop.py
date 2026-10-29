"""Unit and integration tests for RepairLoop and RunLogger."""
from pathlib import Path
import pytest

from poster_agent.config.settings import AppConfig, RepairConfig
from poster_agent.context.loader import load_context
from poster_agent.spec.models import PosterSpec, BBox, TextElement, LogoPlacement
from poster_agent.generators.mock import MockGenerator
from poster_agent.renderer.renderer import PosterRenderer
from poster_agent.checks.runner import CheckRunner
from poster_agent.loop.repair import RepairLoop, RepairAction


@pytest.fixture
def context():
    return load_context()


@pytest.fixture
def valid_spec():
    return PosterSpec(
        canvas_width_px=1200,
        canvas_height_px=1600,
        dpi=300,
        template_id="event_portrait_hero",
        palette=["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"],
        text_safe_zones=[BBox(y_min=200, x_min=50, y_max=900, x_max=950)],
        elements=[
            TextElement(
                id="headline_1",
                role="headline",
                text="APEX TECH SUMMIT 2026",
                source="brief",
                font="Outfit",
                size=36,
                weight=800,
                color="#FFFFFF",
                box=BBox(y_min=180, x_min=80, y_max=280, x_max=920),
            ),
            TextElement(
                id="subhead_1",
                role="subheadline",
                text="ANNUAL AI AND ROBOTICS SHOWCASE",
                source="brief",
                font="Inter",
                size=20,
                weight=600,
                color="#00F5D4",
                box=BBox(y_min=300, x_min=80, y_max=360, x_max=920),
            ),
            TextElement(
                id="date_1",
                role="date",
                text="OCTOBER 30 2026",
                source="brief",
                font="Inter",
                size=18,
                weight=600,
                color="#FFFFFF",
                box=BBox(y_min=750, x_min=80, y_max=800, x_max=600),
            ),
        ],
        logos=[
            LogoPlacement(
                file="college_logo.png",
                box=BBox(y_min=40, x_min=80, y_max=120, x_max=350),
                clear_space_px=20,
            )
        ],
        art_slots=[],
        assumptions=["Standard promotional poster"],
        missing_fields=[],
        qr_code="https://apextech.edu/summit",
    )


def test_repair_loop_clean_success(valid_spec, context, tmp_path):
    config = AppConfig(
        repair=RepairConfig(max_iterations=3, candidates=1)
    )
    generator = MockGenerator(default_output_dir=tmp_path / "mock_art")
    renderer = PosterRenderer()
    runner = CheckRunner()

    loop = RepairLoop(
        generator=generator,
        renderer=renderer,
        runner=runner,
        config=config,
    )

    req_text = "APEX TECH SUMMIT 2026 with ANNUAL AI AND ROBOTICS SHOWCASE on OCTOBER 30 2026"
    result = loop.run(
        spec=valid_spec,
        requirements_text=req_text,
        context=context,
        base_dir=tmp_path / "runs",
    )

    assert result.status == "SUCCESS"
    assert result.iterations_used == 1
    assert result.best_candidate is not None
    assert result.best_candidate.blocking_count == 0

    # Verify log files created
    assert result.run_dir.exists()
    assert (result.run_dir / "requirements.txt").exists()
    assert (result.run_dir / "context_snapshot.md").exists()
    assert (result.run_dir / "spec_v1.json").exists()
    assert (result.run_dir / "final.png").exists()
    assert (result.run_dir / "run_summary.json").exists()
    assert (result.run_dir / "iteration_1" / "decision.txt").exists()


def test_repair_loop_recovers_from_spec_flaw(valid_spec, context, tmp_path):
    # Introduce defect: text color matches background (contrast failure)
    valid_spec.elements[0].color = "#0B142F"

    config = AppConfig(
        repair=RepairConfig(max_iterations=3, candidates=1)
    )
    generator = MockGenerator(default_output_dir=tmp_path / "mock_art")
    renderer = PosterRenderer()
    runner = CheckRunner()

    loop = RepairLoop(
        generator=generator,
        renderer=renderer,
        runner=runner,
        config=config,
    )

    req_text = "APEX TECH SUMMIT 2026 with ANNUAL AI AND ROBOTICS SHOWCASE on OCTOBER 30 2026"
    result = loop.run(
        spec=valid_spec,
        requirements_text=req_text,
        context=context,
        base_dir=tmp_path / "runs",
    )

    # Should detect contrast failure, apply EDIT_SPEC, and succeed on iteration 2
    assert result.status == "SUCCESS"
    assert result.iterations_used == 2
    assert result.final_spec.elements[0].color == "#FFFFFF"
    assert (result.run_dir / "spec_v2.json").exists()


def test_repair_loop_exhausts_budget_on_permanent_defect(valid_spec, context, tmp_path):
    config = AppConfig(
        repair=RepairConfig(max_iterations=2, candidates=1)
    )
    generator = MockGenerator(default_output_dir=tmp_path / "mock_art")
    renderer = PosterRenderer()
    # Mock runner that always returns blocking failure
    runner = CheckRunner()
    
    # Two elements occupy identical bounding box, creating permanent geometric collision
    valid_spec.elements[0].box = BBox(y_min=180, x_min=80, y_max=280, x_max=920)
    valid_spec.elements[1].box = BBox(y_min=180, x_min=80, y_max=280, x_max=920)

    loop = RepairLoop(
        generator=generator,
        renderer=renderer,
        runner=runner,
        config=config,
    )

    result = loop.run(
        spec=valid_spec,
        requirements_text="APEX TECH SUMMIT 2026",
        context=context,
        base_dir=tmp_path / "runs",
    )

    assert result.status == "FAILED"
    assert result.iterations_used == 2
    assert len(result.failure_reasons) >= 1
    assert "FAILED" in result.summary
