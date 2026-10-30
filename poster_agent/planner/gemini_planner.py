"""Stage 2: Gemini-powered Layout Planner and Art Director."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.gemini_client import GeminiClient
from poster_agent.ingestion.extractor import ExtractedBrief


class GeminiLayoutPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    archetype: str
    canvas_w: int = 1258
    canvas_h: int = 1772
    headline_font: str = "Space Grotesk"
    headline_pt: int = 92
    date_font: str = "Space Grotesk"
    date_pt: int = 34
    accent_color: str = "#00FF66"
    highlight_color: str = "#00F3FF"
    background_color: str = "#050811"
    card_bg: str = "rgba(7, 11, 24, 0.85)"
    hero_target_size_px: int = 560
    hero_top_px: int = 285
    tracks_belt_visible: bool = True
    metadata_bottom_px: int = 75
    art_prompts: dict[str, str] = Field(default_factory=dict)
    planning_reasoning: str = ""


class GeminiPlanner:
    """Plans layout hierarchy, archetype, color tokens, and asset direction using Gemini."""

    def __init__(self, client: GeminiClient | None = None):
        self.client = client or GeminiClient()

    def plan(self, brief: ExtractedBrief, context_text: str = "") -> GeminiLayoutPlan:
        """Generate structured layout plan using Gemini."""
        prompt = f"""You are an elite graphic designer and art director planning an A2 event poster.

EVENT BRIEF:
{chr(10).join(f"- {k}: {v.text}" for k, v in brief.fields.items())}

ADDITIONAL CONTEXT:
{context_text}

Design a layout that ensures:
1. Sovereign hierarchy: Title and Date are most prominent.
2. Centered commanding hero asset: Shield/Hero takes central focus (at least 520px-580px wide).
3. No dead voids: If category tracks exist (e.g. Web, Crypto, Forensics), place a tracks belt between hero and metadata.
4. Cohesive cyber aesthetic: Electric Emerald (#00FF66) + Cyber Cyan (#00F3FF) against Deep Obsidian (#050811).

Output strictly valid JSON conforming to this schema:
{{
  "archetype": "cyber_ctf",
  "canvas_w": 1258,
  "canvas_h": 1772,
  "headline_font": "Space Grotesk",
  "headline_pt": 92,
  "date_font": "Space Grotesk",
  "date_pt": 34,
  "accent_color": "#00FF66",
  "highlight_color": "#00F3FF",
  "background_color": "#050811",
  "card_bg": "rgba(7, 11, 24, 0.85)",
  "hero_target_size_px": 560,
  "hero_top_px": 285,
  "tracks_belt_visible": true,
  "metadata_bottom_px": 75,
  "art_prompts": {{
    "background": "dark futuristic server room with glowing green and cyan fiber optic circuit lines, dark obsidian tones, clean negative space, 8k render, no text",
    "hero_cutout": "imposing holographic security shield emblem, electric neon emerald glowing edges, crisp silhouette, transparent black background, no text"
  }},
  "planning_reasoning": "brief explanation of layout choices"
}}
"""
        res = self.client.generate_json(prompt=prompt, temperature=0.2)
        return GeminiLayoutPlan.model_validate(res)
