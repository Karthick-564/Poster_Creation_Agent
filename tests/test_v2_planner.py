"""Planner tests: candidate search, copy retention and logo geometry."""
from pathlib import Path

import pytest

from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.v2.brand import get_brand, resolve_format
from poster_agent.v2.planner import KCTPlanner, rescale_logo_to_asset

BRIEF = """Title: AI Design Summit 2026
Eyebrow: KUMARAGURU COLLEGE OF TECHNOLOGY
Tagline: HUMAN JUDGEMENT IN THE AGE OF GENERATIVE SYSTEMS
Subtitle: A one-day campus summit on design and automation.
Date: 14 November 2026
Time: 09:30 AM IST
Venue: Sir M. Visvesvaraya Hall, KCT Campus
CTA: Scan to register
QR link: https://events.kct.ac.in/ai-design-summit
Closing: DESIGN WITH INTENT.
Organizer: Department of Computer Science and Engineering
"""


def _plan():
    brand = get_brand("KCT")
    fmt = resolve_format(brand, "story")
    brief = BriefExtractor().extract(BRIEF)
    return brief, brand, fmt, KCTPlanner().plan_candidates(brief, brand, fmt)


def test_candidate_search_returns_multiple_layouts():
    _, _, _, candidates = _plan()
    assert len(candidates) >= 3
    assert len({c.candidate_id for c in candidates}) == len(candidates)


def test_planner_keeps_supplied_optional_copy():
    brief, brand, fmt, candidates = _plan()
    best = candidates[0]
    roles = {block.role for block in best.text_blocks}
    assert "headline" in roles
    assert "tagline" in roles
    assert "closing" in roles
    assert best.qr is not None
    assert best.qr.payload.startswith("https://")


def test_planner_is_deterministic():
    _, _, _, first = _plan()
    _, _, _, second = _plan()
    assert [c.candidate_id for c in first] == [c.candidate_id for c in second]
    assert [c.seed for c in first] == [c.seed for c in second]
    assert [b.text for b in first[0].text_blocks] == [b.text for b in second[0].text_blocks]


def test_logo_box_is_top_right_and_inside_clear_space():
    _, brand, fmt, candidates = _plan()
    spec = candidates[0]
    logo = spec.logo_slots[0]
    x, y, w, h = logo.box.to_px(fmt.width, fmt.height)
    clear = brand.clear_space_px(fmt)
    assert x + w == pytest.approx(fmt.width - clear, abs=0.5)
    assert y == pytest.approx(clear, abs=0.5)


def test_rescale_logo_preserves_intrinsic_aspect():
    _, brand, fmt, candidates = _plan()
    spec = candidates[0]
    updated = rescale_logo_to_asset(spec, brand, asset_width=600, asset_height=150)
    x, y, w, h = updated.logo_slots[0].box.to_px(fmt.width, fmt.height)
    assert w / h == pytest.approx(600 / 150, abs=0.01)


@pytest.mark.parametrize("format_name", ["fourfive", "square", "A3", "A4"])
def test_logo_stays_inside_safe_margin_on_every_format(format_name):
    brand = get_brand("KCT")
    fmt = resolve_format(brand, format_name)
    brief = BriefExtractor().extract(BRIEF)
    spec = KCTPlanner().plan_candidates(brief, brand, fmt)[0]

    x, y, w, h = spec.logo_slots[0].box.to_px(fmt.width, fmt.height)
    inset = max(brand.clear_space_px(fmt), brand.safe_margin_px(fmt))
    assert x >= inset - 0.5
    assert y >= inset - 0.5
    assert x + w <= fmt.width - inset + 0.5
    assert y + h <= fmt.height - inset + 0.5
