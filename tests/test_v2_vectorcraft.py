"""VectorCraft translation tests that do not execute the Windows binary."""
from pathlib import Path

from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.v2.assets import MockAssetBroker
from poster_agent.v2.brand import get_brand, resolve_format
from poster_agent.v2.composer import VectorCraftComposer
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


def _fixture(tmp_path):
    brand = get_brand("KCT")
    fmt = resolve_format(brand, "story")
    brief = BriefExtractor().extract(BRIEF)
    spec = KCTPlanner().plan_candidates(brief, brand, fmt)[0]
    assets = MockAssetBroker(tmp_path / "assets", allow_placeholder_logo=True).provide(spec, brand)
    spec = rescale_logo_to_asset(spec, brand, assets.logo.width, assets.logo.height)
    return brand, spec, assets


def test_vectorcraft_commands_cover_all_layers(tmp_path):
    brand, spec, assets = _fixture(tmp_path)
    composer = VectorCraftComposer()
    vc = composer.build(spec, assets, brand, tmp_path)

    names = [command["command"] for command in vc.commands]
    assert names[0] == "file.new"
    assert "file.place" in names
    assert names.count("text.create") == len(spec.text_blocks) + (1 if spec.qr else 0)
    assert names.count("shape.rectangle") >= 2  # solid logo field + QR plate

    # Background, hero, QR and logo are placed; the logo is last.
    placements = [c for c in vc.commands if c["command"] == "file.place"]
    assert len(placements) == 4
    assert placements[0]["params"]["rect"] == [0, 0, spec.format.width, spec.format.height]
    assert Path(placements[-1]["params"]["path"]).name == Path(assets.logo.path).name

    # The logo box keeps the asset's intrinsic aspect ratio.
    logo_rect = placements[-1]["params"]["rect"]
    logo_ratio = assets.logo.width / assets.logo.height
    assert abs((logo_rect[2] / logo_rect[3]) - logo_ratio) < 0.02


def test_vectorcraft_dry_run_saves_commands(tmp_path):
    brand, spec, assets = _fixture(tmp_path)
    composer = VectorCraftComposer(dry_run=True)
    result = composer.render(
        spec=spec,
        assets=assets,
        brand=brand,
        output_path=tmp_path / "out.png",
        work_dir=tmp_path,
    )
    assert result.engine == "vectorcraft-dry-run"
    assert result.commands_path is not None
    assert Path(result.commands_path).exists()
    assert len(result.rows) == len(spec.text_blocks)
