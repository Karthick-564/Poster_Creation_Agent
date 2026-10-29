"""Unit tests for the vision reviewer and 3-second test."""
import json
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image
import pytest

from poster_agent.spec.models import PosterSpec, BBox, TextElement, LogoPlacement
from poster_agent.reviewer.reviewer import (
    PosterReviewer,
    ReviewResult,
    ThreeSecondTest,
    encode_image_base64,
    create_downscaled_preview,
)


@pytest.fixture
def sample_spec() -> PosterSpec:
    return PosterSpec(
        canvas_width_px=1200,
        canvas_height_px=1600,
        dpi=300,
        template_id="event_portrait_hero",
        palette=["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"],
        text_safe_zones=[BBox(y_min=180, x_min=50, y_max=900, x_max=950)],
        elements=[
            TextElement(
                id="headline_1",
                role="headline",
                text="Apex AI Hackathon 2026",
                source="brief",
                font="Outfit",
                size=36,
                weight=800,
                color="#FFFFFF",
                box=BBox(y_min=180, x_min=80, y_max=280, x_max=920),
            ),
            TextElement(
                id="date_1",
                role="date",
                text="November 12-14, 2026",
                source="brief",
                font="Inter",
                size=20,
                weight=600,
                color="#00F5D4",
                box=BBox(y_min=750, x_min=80, y_max=810, x_max=600),
            ),
            TextElement(
                id="venue_1",
                role="venue",
                text="Auditorium Hall, Apex Institute",
                source="brief",
                font="Inter",
                size=18,
                weight=500,
                color="#FFFFFF",
                box=BBox(y_min=820, x_min=80, y_max=870, x_max=800),
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
        assumptions=["Standard layout"],
        missing_fields=[],
        qr_code="https://apextech.edu",
    )


@pytest.fixture
def test_image(tmp_path) -> Path:
    img = Image.new("RGB", (1200, 1600), color=(15, 25, 45))
    path = tmp_path / "poster_test.png"
    img.save(path)
    return path


def test_encode_and_downscale(test_image):
    b64 = encode_image_base64(test_image)
    assert isinstance(b64, str)
    assert len(b64) > 100

    downscaled = create_downscaled_preview(test_image, max_dim=360)
    assert max(downscaled.size) <= 360
    assert downscaled.size[0] == 270 or downscaled.size[1] == 360


def test_reviewer_heuristic_fallback(sample_spec, test_image):
    # Endpoint points to non-existent server, should gracefully fallback
    reviewer = PosterReviewer(model_name="LFM3-VL-2B", thinking_mode=False)
    result = reviewer.review(test_image, sample_spec)

    assert isinstance(result, ReviewResult)
    assert 1 <= result.hierarchy <= 5
    assert 1 <= result.readability <= 5
    assert result.three_second_test.passed is True
    assert result.three_second_test.event == "Apex AI Hackathon 2026"
    assert len(result.fixes) >= 1
    assert result.thinking_enabled is False


def test_reviewer_mock_client_with_thinking(sample_spec, test_image):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="""<think>
Evaluating headline visibility and balance. The headline is large and crisp.
Date and venue are well aligned.
</think>
{
  "hierarchy": 5,
  "balance": 4,
  "readability": 5,
  "brand_fit": 5,
  "polish": 4,
  "three_second_test": {
    "event": "Apex AI Hackathon 2026",
    "date": "November 12-14, 2026",
    "venue": "Auditorium Hall, Apex Institute",
    "passed": true
  },
  "fixes": ["Slightly brighten the footer link."]
}"""
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    reviewer = PosterReviewer(client=mock_client, model_name="LFM3-VL-2B", thinking_mode=True)
    result = reviewer.review(test_image, sample_spec)

    assert result.hierarchy == 5
    assert result.polish == 4
    assert result.three_second_test.passed is True
    assert "headline visibility" in (result.raw_thinking or "").lower()
    assert result.fixes == ["Slightly brighten the footer link."]

    # Verify kwargs passed to client
    called_kwargs = mock_client.chat.completions.create.call_args[1]
    assert called_kwargs.get("extra_body") == {"thinking": True}
    assert called_kwargs.get("response_format") == {"type": "json_object"}


def test_reviewer_invalid_json_triggers_fallback(sample_spec, test_image):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="INVALID NON-JSON OUTPUT"))]
    mock_client.chat.completions.create.return_value = mock_response

    reviewer = PosterReviewer(client=mock_client, model_name="LFM3-VL-2B")
    result = reviewer.review(test_image, sample_spec)

    # Must not crash, should fall back to heuristic
    assert isinstance(result, ReviewResult)
    assert result.hierarchy >= 1
    assert result.three_second_test.event == "Apex AI Hackathon 2026"

