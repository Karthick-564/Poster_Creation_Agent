"""Unit tests for Ideogram 4.0 Payload Builder v2 (Phase D Commit 3a).

Verifies:
1. compositional_deconstruction.elements is ALWAYS 1-2 concrete bbox objects, never empty [].
2. style_description is a flat string with inline palette hexes.
3. aspect_ratio strictly matches canvas (9:16, 4:5, etc.) and ComfyUI ResolutionSelector label.
4. No negative text trigger incantations ("NO TEXT", "NO WORDS", etc.) and zero stray punctuation runs.
"""
import re
import pytest

from poster_agent.generators.ideogram_v2 import (
    build_ideogram_v2_payload,
    resolve_aspect_ratio_and_resolution,
    sanitize_plain_caption,
)


def test_sanitize_plain_caption_removes_negative_incantations():
    dirty = "PURE NON-TEXT BACKGROUND ARTWORK: modern robotics lab with absolutely no text, no words, no letters, no signage: , , , pure art with no typography."
    cleaned = sanitize_plain_caption(dirty)
    assert "no text" not in cleaned.lower()
    assert "no words" not in cleaned.lower()
    assert "no letters" not in cleaned.lower()
    assert "typography" not in cleaned.lower()
    assert "signage" not in cleaned.lower()
    assert ", ," not in cleaned
    assert cleaned.endswith(".")


def test_resolve_aspect_ratio_and_resolution():
    # 9:16 story (1080x1920)
    aspect_916, label_916, w_916, h_916 = resolve_aspect_ratio_and_resolution(1080.0, 1920.0)
    assert aspect_916 == "9:16"
    assert "9:16" in label_916
    assert (w_916, h_916) == (768, 1344)

    # 4:5 portrait (1080x1350)
    aspect_45, label_45, w_45, h_45 = resolve_aspect_ratio_and_resolution(1080.0, 1350.0)
    assert aspect_45 == "4:5"
    assert "4:5" in label_45
    assert (w_45, h_45) == (896, 1120)

    # 1:1 square
    aspect_11, label_11, w_11, h_11 = resolve_aspect_ratio_and_resolution(1080.0, 1080.0)
    assert aspect_11 == "1:1"
    assert (w_11, h_11) == (1024, 1024)


def test_build_ideogram_v2_payload_schema():
    desc = "Engineering workshop with robotic arm prototypes and soft diffuse ambient lighting."
    palette = ["#070B19", "#00F5D4", "#FEE440", "#FFFFFF"]
    payload = build_ideogram_v2_payload(
        description=desc,
        palette=palette,
        canvas_w=1080.0,
        canvas_h=1920.0,
        light_direction="top_left",
    )

    # 1. High level description
    assert "high_level_description" in payload
    hld = payload["high_level_description"]
    assert isinstance(hld, str)
    assert "no text" not in hld.lower()
    assert not re.search(r",\s*,", hld)

    # 2. Style description: flat string with inline palette hexes
    assert "style_description" in payload
    sd = payload["style_description"]
    assert isinstance(sd, str)
    for hex_code in palette[:3]:
        assert hex_code.upper() in sd

    # 3. Compositional deconstruction
    assert "compositional_deconstruction" in payload
    comp = payload["compositional_deconstruction"]
    assert "background" in comp
    assert "elements" in comp
    elems = comp["elements"]
    assert isinstance(elems, list)
    assert 1 <= len(elems) <= 2, "elements must ALWAYS be 1-2 concrete bbox objects, never empty"

    for elem in elems:
        assert "bbox" in elem
        bbox = elem["bbox"]
        assert len(bbox) == 4
        assert 0 <= bbox[0] < bbox[2] <= 1000
        assert 0 <= bbox[1] < bbox[3] <= 1000
        assert "desc" in elem
        assert "color_palette" in elem

    # 4. Aspect ratio
    assert payload["aspect_ratio"] == "9:16"
