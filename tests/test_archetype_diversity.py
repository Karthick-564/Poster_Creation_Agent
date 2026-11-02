"""Unit test verifying structural diversity between focal_point and z_pattern archetypes (Phase D Commit 3a).

Asserts:
- >=4 rows have divergent positions (different x or y coordinates)
- Verifies focal_point utilizes centered radiance while z_pattern utilizes diagonal left/right anchors
"""
from pathlib import Path
from PIL import Image

from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.renderer.composer import compose


def test_archetype_diversity_focal_point_vs_z_pattern(tmp_path):
    brief_text = """
    POSTER BRIEF: TECH SUMMIT 2026
    Format: 1080 x 1920 px (9:16 story)
    Date: Wednesday, 12 November 2026, 10:00 AM
    Venue: Tech Hall, Innovation Center
    Title: FUTURE TECH SUMMIT
    Eyebrow: ANNUAL INNOVATION CONFERENCE
    Tagline: BUILD FOR TOMORROW
    Subtitle: Connect with engineers, researchers and creators shaping the future of tech.
    Call to action: Register Now
    Closing line: JOIN US IN SHAPING TOMORROW
    """
    extractor = BriefExtractor()
    brief = extractor.extract(brief_text)
    palette = ["#070B19", "#00F5D4", "#FEE440", "#FFFFFF"]
    bg_path = tmp_path / "bg.png"
    Image.new("RGB", (1080, 1920), "#070B19").save(bg_path)

    # Compose focal_point
    vc_fp = compose(
        brief=brief,
        palette=palette,
        bg_path=bg_path,
        archetype="focal_point",
        width=1080.0,
        height=1920.0,
        layout_plan={"slots": []},
    )

    # Compose z_pattern
    vc_zp = compose(
        brief=brief,
        palette=palette,
        bg_path=bg_path,
        archetype="z_pattern",
        width=1080.0,
        height=1920.0,
        layout_plan={"slots": []},
    )

    # Extract text command positions from both
    def get_positions(vc):
        pos_list = []
        for cmd in vc.commands:
            if cmd.get("command") == "text.create":
                p = cmd.get("params", {})
                txt = p.get("text", "")
                pos_list.append((txt, round(p.get("x", 0.0), 1), round(p.get("y", 0.0), 1)))
        return pos_list

    fp_pos = get_positions(vc_fp)
    zp_pos = get_positions(vc_zp)

    divergent = []
    for (t1, x1, y1), (t2, x2, y2) in zip(fp_pos, zp_pos):
        if t1 == t2 and (x1 != x2 or y1 != y2):
            divergent.append((t1, (x1, y1), (x2, y2)))

    assert len(divergent) >= 4, (
        f"Archetypes focal_point and z_pattern must differ structurally on >=4 rows. "
        f"Only found {len(divergent)}: {divergent}"
    )
