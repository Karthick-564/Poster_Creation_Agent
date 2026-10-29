"""Unit and integration tests for Planner and Verbatim Verifier."""
import json
import os
from unittest.mock import MagicMock
import pytest

from poster_agent.context.loader import load_context
from poster_agent.spec.models import PosterSpec, BBox, TextElement, LogoPlacement
from poster_agent.planner.templates import get_template_library
from poster_agent.planner.verifier import (
    VerbatimViolationError,
    MissingFieldsError,
    verify_verbatim_strings,
    verify_spec,
)
from poster_agent.planner.planner import PosterPlanner


@pytest.fixture
def context():
    return load_context()


@pytest.fixture
def sample_brief():
    return (
        "Join us for the ANNUAL ROBO WARS 2026 organized by AI & Robotics Club. "
        "Date: NOVEMBER 15 2026. Venue: MAIN AUDITORIUM. "
        "Showcasing combat robots and autonomous drones."
    )


@pytest.fixture
def valid_spec():
    return PosterSpec(
        canvas_width_px=2480,
        canvas_height_px=3508,
        dpi=300,
        template_id="event_portrait_hero",
        palette=["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"],
        text_safe_zones=[BBox(y_min=500, x_min=50, y_max=950, x_max=950)],
        elements=[
            TextElement(
                id="headline_1",
                role="headline",
                text="ANNUAL ROBO WARS 2026",
                source="brief",
                font="Outfit",
                size=48,
                weight=800,
                color="#FFFFFF",
                box=BBox(y_min=120, x_min=80, y_max=220, x_max=920),
            ),
            TextElement(
                id="date_1",
                role="date",
                text="NOVEMBER 15 2026",
                source="brief",
                font="Inter",
                size=22,
                weight=600,
                color="#00F5D4",
                box=BBox(y_min=700, x_min=80, y_max=750, x_max=450),
            ),
            TextElement(
                id="venue_1",
                role="venue",
                text="MAIN AUDITORIUM",
                source="brief",
                font="Inter",
                size=20,
                weight=500,
                color="#FFFFFF",
                box=BBox(y_min=760, x_min=80, y_max=810, x_max=500),
            ),
            TextElement(
                id="college_name",
                role="label",
                text="Apex Institute of Technology",
                source="context",
                font="Inter",
                size=16,
                weight=600,
                color="#E0E1DD",
                box=BBox(y_min=50, x_min=80, y_max=90, x_max=400),
            ),
        ],
        logos=[
            LogoPlacement(
                file="college_logo.png",
                box=BBox(y_min=40, x_min=80, y_max=100, x_max=280),
                clear_space_px=20,
            )
        ],
        art_slots=[],
        assumptions=["Cyberpunk robot aesthetics"],
        missing_fields=[],
        qr_code="https://apextech.edu",
    )


# -------------------------------------------------------------
# Template Library Tests
# -------------------------------------------------------------

def test_template_library_loading():
    library = get_template_library()
    templates = library.list_all()
    assert len(templates) >= 4

    hero = library.get("event_portrait_hero")
    assert hero is not None
    assert hero.orientation == "portrait"
    assert len(hero.slots) >= 6

    prompt_text = library.format_for_prompt()
    assert "event_portrait_hero" in prompt_text
    assert "event_minimal" in prompt_text


# -------------------------------------------------------------
# Verbatim Verifier Tests
# -------------------------------------------------------------

def test_verifier_passes_on_verbatim_text(valid_spec, sample_brief, context):
    violations = verify_verbatim_strings(spec=valid_spec, brief_text=sample_brief, context=context)
    assert len(violations) == 0
    # Must not raise
    verify_spec(spec=valid_spec, brief_text=sample_brief, context=context)


def test_verifier_catches_invented_brief_string(valid_spec, sample_brief, context):
    # Alter headline to something not in brief
    valid_spec.elements[0].text = "SUPER CYBER ROBOTICS CHAMPIONSHIP 9000"
    violations = verify_verbatim_strings(spec=valid_spec, brief_text=sample_brief, context=context)
    assert len(violations) >= 1
    assert "invented" in violations[0].lower() or "not in brief" in violations[0].lower()

    with pytest.raises(VerbatimViolationError):
        verify_spec(spec=valid_spec, brief_text=sample_brief, context=context)


def test_verifier_catches_invalid_context_string(valid_spec, sample_brief, context):
    # Alter context element to nonexistent institution
    valid_spec.elements[3].text = "Fictional Magic University of Antarctica"
    violations = verify_verbatim_strings(spec=valid_spec, brief_text=sample_brief, context=context)
    assert len(violations) >= 1
    assert "not in context.md" in violations[0].lower()

    with pytest.raises(VerbatimViolationError):
        verify_spec(spec=valid_spec, brief_text=sample_brief, context=context)


def test_verifier_stops_on_missing_fields(valid_spec, sample_brief, context):
    valid_spec.missing_fields = ["date", "venue"]
    with pytest.raises(MissingFieldsError) as exc_info:
        verify_spec(spec=valid_spec, brief_text=sample_brief, context=context)
    assert "date" in exc_info.value.missing_fields


# -------------------------------------------------------------
# Planner Execution Tests (Mocked Groq)
# -------------------------------------------------------------

def test_planner_with_mock_client(valid_spec, sample_brief, context):
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()

    mock_message.content = valid_spec.model_dump_json()
    mock_choice.message = mock_message
    mock_completion.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_completion

    planner = PosterPlanner(client=mock_client)
    spec = planner.plan(requirements_text=sample_brief, context=context)

    assert spec.template_id == "event_portrait_hero"
    assert spec.elements[0].text == "ANNUAL ROBO WARS 2026"
    assert len(spec.missing_fields) == 0


def test_planner_raises_when_mock_returns_invented_text(valid_spec, sample_brief, context):
    valid_spec.elements[0].text = "Completely Made Up Headline"

    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()

    mock_message.content = valid_spec.model_dump_json()
    mock_choice.message = mock_message
    mock_completion.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_completion

    planner = PosterPlanner(client=mock_client)
    with pytest.raises(VerbatimViolationError):
        planner.plan(requirements_text=sample_brief, context=context)


def test_planner_raises_when_mock_returns_missing_fields(valid_spec, sample_brief, context):
    valid_spec.missing_fields = ["venue"]

    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()

    mock_message.content = valid_spec.model_dump_json()
    mock_choice.message = mock_message
    mock_completion.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_completion

    planner = PosterPlanner(client=mock_client)
    with pytest.raises(MissingFieldsError):
        planner.plan(requirements_text=sample_brief, context=context)

