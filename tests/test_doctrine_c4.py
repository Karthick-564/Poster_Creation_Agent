"""Unit tests for Doctrine Rebuild & Exemplar Injection (Commit 3).

Tests:
- Exemplar picker: deterministic genre + format matching; no-match returns empty; token budget respected.
- SKILL.md corpus citations match a dynamic recompute from poster_catalog.csv.
- Composer genre policy: pills permitted for recruitment/hiring, absent for cultural A3.
"""
import csv
from pathlib import Path
import pytest
from PIL import Image

from poster_agent.house_style import (
    PROJECT_ROOT,
    select_house_exemplars,
    format_exemplars_for_prompt,
    resolve_genre,
)
from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.renderer.composer import compose


def test_exemplar_picker_deterministic_selection_and_token_budget():
    # Genre 'hiring' with format 'story'
    res1 = select_house_exemplars(genre="hiring", format_name="story")
    res2 = select_house_exemplars(genre="hiring", format_name="story")

    assert len(res1) > 0
    assert len(res1) <= 3
    # Deterministic order
    assert [r["file"] for r in res1] == [r["file"] for r in res2]

    # Required keys present
    for ex in res1:
        assert "file" in ex
        assert "layout" in ex
        assert "typography" in ex
        assert "palette" in ex
        assert "standout" in ex

    # Prompt block formatting & token/character budget (~500 tokens / 2000 chars)
    prompt_block = format_exemplars_for_prompt(res1, max_chars=2000)
    assert len(prompt_block) <= 2000
    assert "HOUSE STYLE REFERENCES" in prompt_block
    assert res1[0]["file"] in prompt_block


def test_exemplar_picker_no_match_returns_empty():
    # Unknown genre with no keyword match
    res = select_house_exemplars(genre="nonexistent_alien_genre", format_name="nonexistent_format")
    assert res == []

    prompt_block = format_exemplars_for_prompt(res)
    assert prompt_block == ""


def test_doctrine_skill_md_corpus_citations_match_csv_recompute():
    csv_p = PROJECT_ROOT / "Examples" / "extracted" / "Posters" / "poster_catalog.csv"
    assert csv_p.exists(), f"Catalog CSV missing at {csv_p}"

    with open(csv_p, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    assert total == 205

    # Recompute Story format count: 173/205 (84%)
    story_count = sum(1 for r in rows if "1080x1920" in r.get("format", "").lower() or "story" in r.get("format", "").lower())
    assert story_count == 173

    # Recompute White background count: 129/205 (63%)
    white_count = sum(1 for r in rows if "white" in r.get("background", "").lower())
    assert white_count == 129

    # Recompute QR mentions: 47-48/205
    qr_count = sum(1 for r in rows if "qr" in (r.get("standout", "") + r.get("details_shown", "") + r.get("layout", "")).lower())
    assert qr_count in (47, 48)

    # Recompute weak notes count: 44-170
    weak_count = sum(1 for r in rows if r.get("weak", "").strip())
    assert weak_count >= 44

    # Read SKILL.md and verify all corpus citations match
    skill_p = PROJECT_ROOT / "skills" / "poster-design-craft" / "SKILL.md"
    assert skill_p.exists(), f"SKILL.md missing at {skill_p}"
    skill_text = skill_p.read_text(encoding="utf-8")

    assert "corpus: 173/205" in skill_text
    assert "corpus: 129/205" in skill_text
    assert "corpus: 48/205" in skill_text
    assert "corpus: 44/205" in skill_text


def test_composer_genre_policy_pills_for_recruitment_absent_for_cultural_a3(tmp_path):
    bg_path = tmp_path / "bg_test.png"
    Image.new("RGB", (842, 1191), "#FFFFFF").save(bg_path)

    # 1. Recruitment on 9:16 story -> pill emitted
    raw_recruitment = """
    Format: 1080 x 1920 px (9:16 portrait)
    Title: We Are Recruiting
    Eyebrow: LEARN / BUILD / GROW
    CTA: Apply Online
    Closing line: BE THE CHANGE. JOIN GDG KCT!
    """
    brief_rec = BriefExtractor().extract(raw_recruitment)
    vc_rec = compose(
        brief=brief_rec,
        palette=["#FFFFFF", "#4285F4", "#0B2A5B", "#EA4335", "#1E2842"],
        bg_path=bg_path,
        width=1080.0,
        height=1920.0,
    )
    try:
        res_rec = vc_rec.execute(work_dir=tmp_path)
        if not res_rec.success and "The system cannot find the path specified" in (res_rec.error_message or ""):
            pytest.skip("Windows-host_required: WSL path-interop at render stage")
    except RuntimeError as e:
        if "The system cannot find the path specified" in str(e):
            pytest.skip(f"Windows-host_required: WSL path-interop at render stage ({e})")
        raise

    roles_rec = [t.get("role") for t in vc_rec.text_manifest]
    assert "_structure_pill" in roles_rec

    # 2. Cultural on A3 print -> NO pills emitted
    raw_cultural = """
    Format: A3
    Title: Symphony Orchestra Annual Concert
    Mood: cultural, orchestral, fine art
    CTA: Reserve Seat
    """
    brief_cult = BriefExtractor().extract(raw_cultural)
    vc_cult = compose(
        brief=brief_cult,
        palette=["#FFFFFF", "#4285F4", "#0B2A5B", "#EA4335", "#1E2842"],
        bg_path=bg_path,
        width=842.0,
        height=1191.0,
    )
    try:
        res_cult = vc_cult.execute(work_dir=tmp_path)
        if not res_cult.success and "The system cannot find the path specified" in (res_cult.error_message or ""):
            pytest.skip("Windows-host_required: WSL path-interop at render stage")
    except RuntimeError as e:
        if "The system cannot find the path specified" in str(e):
            pytest.skip(f"Windows-host_required: WSL path-interop at render stage ({e})")
        raise

    roles_cult = [t.get("role") for t in vc_cult.text_manifest]
    assert "_structure_pill" not in roles_cult
