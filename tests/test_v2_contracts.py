"""Contract and brand tests for the v2 core."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from poster_agent.v2.brand import get_brand, load_brand_contracts, resolve_format
from poster_agent.v2.contracts import Box, FormatSpec, TextBlock


def test_kct_brand_contract_is_complete():
    brand = get_brand("KCT")
    assert brand.name == "Kumaraguru College of Technology"
    assert brand.palette["primary"] == "#1E2842"
    assert brand.palette["secondary"] == "#85CEBD"
    assert brand.logo.placement == "top-right"
    assert brand.logo.clear_space_mm == 10.0
    assert brand.logo.solid_field_only is True
    assert "logo" in brand.mandatory_elements
    assert "title" in brand.mandatory_elements


def test_clear_space_is_ten_millimetres():
    brand = get_brand("KCT")
    fmt = resolve_format(brand, "story")
    expected = 10.0 / 25.4 * fmt.dpi
    assert brand.clear_space_px(fmt) == pytest.approx(expected)


def test_format_aliases():
    brand = get_brand("KCT")
    assert resolve_format(brand, "9:16").width == 1080
    assert resolve_format(brand, "9:16").height == 1920
    assert resolve_format(brand, "square").width == 1080


def test_load_contracts_rejects_unknown_school():
    with pytest.raises(KeyError):
        get_brand("NOPE")


def test_box_conversion_and_intersection():
    box = Box(x=100, y=200, w=300, h=400)
    assert box.to_px(1000, 2000) == (100.0, 400.0, 300.0, 800.0)
    assert box.intersects(Box(x=300, y=500, w=200, h=200)) is True
    assert box.intersects(Box(x=500, y=700, w=100, h=100)) is False


def test_box_rejects_overflow():
    with pytest.raises(ValidationError):
        Box(x=900, y=100, w=200, h=100)


def test_text_block_rejects_bad_color():
    with pytest.raises(ValidationError):
        TextBlock(
            id="headline",
            role="headline",
            text="TEST",
            box=Box(x=10, y=10, w=100, h=100),
            size=40,
            color="navy",
        )
