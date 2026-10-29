"""Unit tests for PosterSpec, Config, and Context loader."""
import os
import pytest
from pydantic import ValidationError

from poster_agent.config import AppConfig, load_config, get_config
from poster_agent.context import ContextBundle, load_context
from poster_agent.spec import (
    BBox,
    TextElement,
    LogoPlacement,
    ArtSlot,
    PosterSpec,
    get_groq_strict_json_schema,
)


def sample_valid_spec_data():
    return {
        "canvas_width_px": 2480,
        "canvas_height_px": 3508,
        "dpi": 300,
        "template_id": "event_portrait_hero",
        "palette": ["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"],
        "text_safe_zones": [
            {"y_min": 500, "x_min": 50, "y_max": 950, "x_max": 950}
        ],
        "elements": [
            {
                "id": "headline_1",
                "role": "headline",
                "text": "TECH SYMPOSIUM 2026",
                "source": "brief",
                "font": "Outfit",
                "size": 48,
                "weight": 800,
                "color": "#FFFFFF",
                "box": {"y_min": 100, "x_min": 100, "y_max": 200, "x_max": 900},
            },
            {
                "id": "date_1",
                "role": "date",
                "text": "OCTOBER 30, 2026",
                "source": "brief",
                "font": "Inter",
                "size": 20,
                "weight": 600,
                "color": "#00F5D4",
                "box": {"y_min": 220, "x_min": 100, "y_max": 260, "x_max": 500},
            },
        ],
        "logos": [
            {
                "file": "college_logo.png",
                "box": {"y_min": 20, "x_min": 50, "y_max": 60, "x_max": 250},
                "clear_space_px": 20,
            }
        ],
        "art_slots": [
            {
                "id": "hero_art",
                "prompt": "Futuristic quantum neural network node, neon cyber art",
                "box": {"y_min": 300, "x_min": 50, "y_max": 700, "x_max": 950},
                "transparent": False,
            }
        ],
        "assumptions": ["Cyberpunk style aligns with tech symposium brief"],
        "missing_fields": [],
        "qr_code": "https://apextech.edu/events/register",
    }


def test_valid_spec_creation():
    data = sample_valid_spec_data()
    spec = PosterSpec.model_validate(data)
    assert spec.canvas_width_px == 2480
    assert spec.template_id == "event_portrait_hero"
    assert len(spec.elements) == 2
    assert spec.elements[0].text == "TECH SYMPOSIUM 2026"
    assert spec.elements[0].box.to_list() == [100, 100, 200, 900]


def test_spec_extra_fields_forbidden():
    data = sample_valid_spec_data()
    data["extra_unsupported_key"] = "forbidden_value"
    with pytest.raises(ValidationError):
        PosterSpec.model_validate(data)


def test_bbox_validation():
    # Valid
    box = BBox(y_min=50, x_min=50, y_max=200, x_max=500)
    assert box.to_list() == [50, 50, 200, 500]

    # Pixel conversion
    left, top, right, bottom = box.to_pixels(1000, 2000)
    assert left == 50
    assert top == 100
    assert right == 500
    assert bottom == 400

    # Inverted y coordinates (y_min >= y_max)
    with pytest.raises(ValidationError):
        BBox(y_min=300, x_min=50, y_max=200, x_max=500)

    # Inverted x coordinates (x_min >= x_max)
    with pytest.raises(ValidationError):
        BBox(y_min=50, x_min=600, y_max=200, x_max=500)

    # Out of range coordinates (>1000)
    with pytest.raises(ValidationError):
        BBox(y_min=50, x_min=50, y_max=1200, x_max=500)

    # Out of range coordinates (<0)
    with pytest.raises(ValidationError):
        BBox(y_min=-10, x_min=50, y_max=200, x_max=500)


def test_color_hex_validation():
    data = sample_valid_spec_data()
    data["elements"][0]["color"] = "invalid_color"
    with pytest.raises(ValidationError):
        PosterSpec.model_validate(data)

    data = sample_valid_spec_data()
    data["palette"].append("not_a_hex")
    with pytest.raises(ValidationError):
        PosterSpec.model_validate(data)


def test_groq_strict_json_schema():
    schema = get_groq_strict_json_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "elements" in schema["properties"]
    assert set(schema["properties"].keys()) == set(schema["required"])

    # Check nested defs
    for def_name, def_schema in schema.get("$defs", {}).items():
        if def_schema.get("type") == "object":
            assert def_schema["additionalProperties"] is False
            assert set(def_schema["properties"].keys()) == set(def_schema["required"])


def test_context_loader():
    context = load_context()
    assert len(context.raw_markdown) > 0
    assert "Apex Institute of Technology" in context.college_details.values() or "Institution Name" in context.college_details
    assert len(context.palette) >= 4
    assert len(context.logo_rules) >= 1
    assert "college_logo" in context.logo_rules
    assert context.logo_rules["college_logo"].min_width_px == 120
    assert context.contains_verbatim("Apex Institute of Technology")
    assert not context.contains_verbatim("Unannounced Random University 999")


def test_config_loader():
    cfg = load_config()
    assert cfg.groq.model in ("openai/gpt-oss-120b", "llama-3.3-70b-versatile")
    assert cfg.ideogram.strategy == "B"
    assert cfg.ideogram.transport == "comfyui"
    assert cfg.repair.max_iterations == 4

    # Test environment variable for secret
    orig_key = os.environ.get("GROQ_API_KEY")
    try:
        os.environ["GROQ_API_KEY"] = "test-secret-key-12345"
        assert cfg.groq.api_key == "test-secret-key-12345"
    finally:
        if orig_key is not None:
            os.environ["GROQ_API_KEY"] = orig_key
        elif "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]
