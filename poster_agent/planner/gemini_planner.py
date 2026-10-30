"""Stage 2: Gemini-powered Layout Planner and Art Director.

Instructs Gemini to design posters using Depth-Layered Blending (Method 3 / Depth Stacking):
- Circuit Infill Mask / Generative Texture Integration for typography.
- Multi-layer Z-stacking with intentional 3D overlap (hero shield locks into headline lower base).
- Atmospheric gradient scrims and glowing HUD connectors (NO isolated rectangular floating cards).
- Ambient film grain and radial color grading for unified compositing.
"""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.gemini_client import GeminiClient
from poster_agent.ingestion.extractor import ExtractedBrief


class GeminiLayoutPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    archetype: str
    canvas_w: int = 1258
    canvas_h: int = 1772
    headline_font: str = "Syne"
    headline_pt: int = 104
    headline_blend_mode: str = "path3_infill"  # "path3_infill" or "path2_3d"
    date_font: str = "Space Grotesk"
    date_pt: int = 38
    accent_color: str = "#00FF66"
    highlight_color: str = "#00F3FF"
    background_color: str = "#050811"
    hero_target_size_px: int = 580
    hero_top_px: int = 290
    title_overlap_px: int = 45  # Depth overlap where hero shield overlaps lower title
    light_spill_radius_px: int = 950
    scrim_height_px: int = 760
    tracks_belt_visible: bool = True
    metadata_bottom_px: int = 65
    art_prompts: dict[str, str] = Field(default_factory=dict)
    planning_reasoning: str = ""


class GeminiPlanner:
    """Plans layout hierarchy, archetype, color tokens, and asset direction using Gemini."""

    def __init__(self, client: GeminiClient | None = None):
        self.client = client or GeminiClient()

    def plan(self, brief: ExtractedBrief, context_text: str = "") -> GeminiLayoutPlan:
        """Generate structured layout plan using Gemini with Method 3 Depth-Blending directives."""
        prompt = f"""You are an elite graphic designer, 3D visual compositor, and art director planning an A2 event poster.

EVENT BRIEF:
{chr(10).join(f"- {k}: {v.text}" for k, v in brief.fields.items())}

ADDITIONAL CONTEXT:
{context_text}

CRITICAL DESIGN PHILOSOPHY:
You MUST plan using "Depth-Layered Compositing" (Method 3 - Generative Texture Infill & 3D Layer Stacking):
1. NO SEPARATE FLOATING CARDS: The poster must NOT look like a flat web dashboard with isolated boxes. The scene art, typography, and atmospheric lighting must be organically blended into a unified canvas.
2. TITLE-HERO DEPTH INTERACTION: The massive headline (Syne 100+ pt) sits at Layer 2 (z-index: 5), while the Hero Cutout (Shield/Emblem) sits at Layer 3 (z-index: 10), with its upper crown physically overlapping the lower base of the title letters by 40-55px for cinematic 3D depth.
3. METHOD 3 TEXT BLENDING: The headline uses background circuit texture infill (-webkit-background-clip: text), dual-tone glowing neon green/cyan vector strokes, and specular lighting.
4. ATMOSPHERIC SCRIM: In the bottom 40-45% of the poster, use a soft vertical gradient scrim fading from transparent to midnight navy (rgba(5, 8, 17, 0.95)) so text sits directly on the atmosphere, accented by glowing tactical HUD gridlines.
5. COLOR HARMONY: Electric Emerald (#00FF66), Cyber Cyan (#00F3FF), Solar Gold (#FFB703), and Deep Obsidian (#050811).

Output strictly valid JSON conforming to this schema:
{{
  "archetype": "cyber_ctf",
  "canvas_w": 1258,
  "canvas_h": 1772,
  "headline_font": "Syne",
  "headline_pt": 104,
  "headline_blend_mode": "path3_infill",
  "date_font": "Space Grotesk",
  "date_pt": 38,
  "accent_color": "#00FF66",
  "highlight_color": "#00F3FF",
  "background_color": "#050811",
  "hero_target_size_px": 580,
  "hero_top_px": 290,
  "title_overlap_px": 50,
  "light_spill_radius_px": 950,
  "scrim_height_px": 760,
  "tracks_belt_visible": true,
  "metadata_bottom_px": 65,
  "art_prompts": {{
    "background": "dark futuristic server room with glowing green and cyan fiber optic circuit lines, dark obsidian tones, clean negative space, 8k render, no text",
    "hero_cutout": "imposing holographic security shield emblem, electric neon emerald glowing edges, crisp silhouette, transparent black background, no text"
  }},
  "planning_reasoning": "brief explanation of depth-layering and compositing choices"
}}
"""
        res = self.client.generate_json(prompt=prompt, temperature=0.2)
        return GeminiLayoutPlan.model_validate(res)
