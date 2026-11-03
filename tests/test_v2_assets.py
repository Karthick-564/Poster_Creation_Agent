"""Asset broker tests that never call a live ComfyUI endpoint."""
from pathlib import Path

from PIL import Image

from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.v2.assets import ComfyUIAssetBroker
from poster_agent.v2.brand import get_brand, resolve_format
from poster_agent.v2.planner import KCTPlanner

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


class DummyComfyClient:
    def __init__(self):
        self.background_calls = 0
        self.hero_calls = 0

    def generate_ideogram_background(self, output_path, **_kwargs):
        self.background_calls += 1
        Image.new("RGB", (64, 96), "#1E2842").save(output_path)
        return Path(output_path)

    def generate_qwen_rgba(self, output_path, **_kwargs):
        self.hero_calls += 1
        Image.new("RGBA", (64, 64), (133, 206, 189, 255)).save(output_path)
        return Path(output_path)


def _spec():
    brand = get_brand("KCT")
    fmt = resolve_format(brand, "story")
    brief = BriefExtractor().extract(BRIEF)
    return brand, KCTPlanner().plan_candidates(brief, brand, fmt)[0]


def test_comfy_broker_caches_until_force(tmp_path):
    brand, spec = _spec()
    client = DummyComfyClient()
    broker = ComfyUIAssetBroker(tmp_path / "assets", client=client)

    first = broker.provide(spec, brand)
    assert first.get("background") is not None
    assert first.get("hero") is not None
    assert client.background_calls == 1
    assert client.hero_calls == 1

    broker.provide(spec, brand)
    assert client.background_calls == 1
    assert client.hero_calls == 1

    broker.provide(spec, brand, force=True)
    assert client.background_calls == 2
    assert client.hero_calls == 2
