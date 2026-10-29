"""Unit tests for Ideogram 4.0 adapter, prompt builder, and Qwen generator."""
from pathlib import Path
import pytest

from poster_agent.spec.models import PosterSpec, BBox, TextElement, ArtSlot
from poster_agent.generators.ideogram import (
    IdeogramPromptBuilder,
    IdeogramGenerator,
    StubTransport,
)
from poster_agent.generators.qwen import QwenImageGenerator


@pytest.fixture
def sample_spec():
    return PosterSpec(
        canvas_width_px=1200,
        canvas_height_px=1600,
        dpi=300,
        template_id="event_portrait_hero",
        palette=["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"],
        text_safe_zones=[BBox(y_min=100, x_min=50, y_max=350, x_max=950)],
        elements=[
            TextElement(
                id="headline_1",
                role="headline",
                text="CYBER HACKATHON 2026",
                source="brief",
                font="Outfit",
                size=48,
                weight=800,
                color="#FFFFFF",
                box=BBox(y_min=120, x_min=80, y_max=220, x_max=920),
            ),
            TextElement(
                id="subhead_1",
                role="subheadline",
                text="48 HOURS OF AUTONOMOUS AI CODING",
                source="brief",
                font="Inter",
                size=22,
                weight=600,
                color="#00F5D4",
                box=BBox(y_min=240, x_min=80, y_max=300, x_max=920),
            ),
        ],
        logos=[],
        art_slots=[
            ArtSlot(
                id="hero_cube",
                prompt="A glowing iridescent hypercube pulsing with circuit lines",
                box=BBox(y_min=350, x_min=150, y_max=750, x_max=850),
                transparent=False,
            )
        ],
        assumptions=["Dark cyberpunk style with neon highlights"],
        missing_fields=[],
    )


def test_ideogram_prompt_keys_order(sample_spec):
    prompt = IdeogramPromptBuilder.build_prompt(spec=sample_spec, strategy="B")
    keys = list(prompt.keys())
    assert keys == ["high_level_description", "style_description", "compositional_deconstruction"]

    # High level description max words
    word_count = len(prompt["high_level_description"].split())
    assert word_count <= 50

    # Style description checks
    style = prompt["style_description"]
    assert "aesthetics" in style
    assert "lighting" in style
    assert "medium" in style
    assert "art_style" in style
    assert "photo" not in style  # EITHER photo OR art_style, never both!
    assert "color_palette" in style

    # Palette checks
    for color in style["color_palette"]:
        assert color == color.upper()
        assert color.startswith("#")
        assert len(color) == 7

    # Compositional deconstruction
    comp = prompt["compositional_deconstruction"]
    assert "background" in comp
    assert "elements" in comp


def test_strategy_b_omits_text_elements(sample_spec):
    # Strategy B: only art elements sent; text rendered by HTML renderer
    prompt = IdeogramPromptBuilder.build_prompt(spec=sample_spec, strategy="B")
    elems = prompt["compositional_deconstruction"]["elements"]

    for el in elems:
        assert el["type"] == "obj"
        assert "text" not in el

    # Safe zones mentioned in background
    assert "safe zones" in prompt["compositional_deconstruction"]["background"].lower()


def test_strategy_a_includes_text_elements(sample_spec):
    # Strategy A: text elements are included with exact strings
    prompt = IdeogramPromptBuilder.build_prompt(spec=sample_spec, strategy="A")
    elems = prompt["compositional_deconstruction"]["elements"]

    text_elems = [e for e in elems if e["type"] == "text"]
    assert len(text_elems) == 2
    assert text_elems[0]["text"] == "CYBER HACKATHON 2026"
    assert text_elems[1]["text"] == "48 HOURS OF AUTONOMOUS AI CODING"

    # Element key order check
    for te in text_elems:
        keys = list(te.keys())
        assert keys == ["type", "bbox", "text", "desc", "color_palette"]

        # Check bbox is in range and min < max
        ymin, xmin, ymax, xmax = te["bbox"]
        assert 0 <= ymin < ymax <= 1000
        assert 0 <= xmin < xmax <= 1000


def test_ideogram_generator_generation(tmp_path, sample_spec):
    generator = IdeogramGenerator(strategy="B", transport_type="stub")
    results = generator.generate(spec=sample_spec, count=2, base_seed=12345, output_dir=tmp_path)

    assert len(results) == 2
    assert results[0].seed == 12345
    assert results[1].seed == 12346
    assert results[0].image_path.exists()
    assert results[0].image_path.stat().st_size > 0
    assert "high_level_description" in results[0].payload


def test_qwen_image_generator(tmp_path, sample_spec):
    qwen = QwenImageGenerator()
    results = qwen.generate(spec=sample_spec, count=1, base_seed=54321, output_dir=tmp_path)

    assert len(results) == 1
    assert results[0].seed == 54321
    assert results[0].image_path.exists()
    assert "qwen_image" in results[0].payload["model"]

