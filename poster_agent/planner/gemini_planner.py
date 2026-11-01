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
    model_config = ConfigDict(extra="ignore")
    archetype: str = "editorial"
    composition_pattern: str = "focal_point"  # "focal_point", "z_pattern", "split_layout", "three_column_grid"
    design_movement: str = "Swiss Style"      # e.g., "Swiss Style", "Bauhaus", "Risograph", "Warm Paper-Cut", "Editorial"
    lighting_direction: str = "top-left"
    canvas_w: int = 1258
    canvas_h: int = 1772
    headline_font: str = "OFL-Display"
    headline_pt: int = 104
    headline_blend_mode: str = "path3_infill"  # "path3_infill" or "path2_3d"
    date_font: str = "OFL-Sans"
    date_pt: int = 34
    accent_color: str = ""
    highlight_color: str = ""
    background_color: str = ""
    hero_target_size_px: int = 580
    hero_top_px: int = 290
    title_overlap_px: int = 40  # Depth overlap where hero shield/subject overlaps lower title
    light_spill_radius_px: int = 950
    scrim_height_px: int = 760
    tracks_belt_visible: bool = True
    metadata_bottom_px: int = 65
    title_treatment: str = "css_gradient_glow"  # "generative_3d", "css_gradient_glow", "flat"
    art_prompts: dict[str, Any] = Field(default_factory=dict)
    planning_reasoning: str = ""


class GeminiPlanner:
    """Plans layout hierarchy, archetype, color tokens, and asset direction using Gemini."""

    def __init__(self, client: GeminiClient | None = None):
        self.client = client or GeminiClient()

    def plan(self, brief: ExtractedBrief, context_text: str = "") -> GeminiLayoutPlan:
        """Generate structured layout plan using Gemini guided by DESIGN.md principles."""
        prompt = f"""You are an elite Graphic Design Director, Typography Master, and Visual Compositor planning a professional event poster.

EVENT BRIEF:
{chr(10).join(f"- {k}: {v.text}" for k, v in brief.fields.items())}

ADDITIONAL CONTEXT:
{context_text}

MANDATORY DESIGN PRINCIPLES (DESIGN.md / PosterGen / PosterMELD):
1. HIERARCHY BEFORE DECORATION: Every element must communicate information. No decorative clutter.
2. NO WEB DASHBOARDS: NEVER wrap text in floating rounded rectangle cards or HTML button pills. Text sits directly on atmospheric negative space.
3. AUTHENTIC MOVEMENT ANCHORS (NO AI SLOP): Never use vague buzzwords ("modern, sleek, professional"). Instead, anchor the visual direction in a recognized discipline suited to this event:
   - "Swiss / International Typographic Style" (bold grotesque type, asymmetric geometry, clean whitespace)
   - "Bauhaus / Constructivism" (primary geometric forms, diagonal dynamism, structural framing)
   - "Risograph / Screenprint" (tactile grain, spot-color duotones, subtle ink texture)
   - "Warm Paper-Cut / Organic Relief" (multi-layered dimensional paper cuts, soft drop shadows, warm daylight)
   - "Editorial / Contemporary Culture" (refined serif display type, generous calm margins, museum restraint)
   - "Technical Monospace / Terminal" (precision hairline grids, monospace belts — for cybersecurity/code events only)
4. SELECT 1 COMPOSITION PATTERN:
   - "focal_point": Centered subject with radial hierarchy (best for bold graphic icons, music gigs)
   - "z_pattern": Eye scan top-left -> top-right -> diagonal hero -> bottom highlights -> bottom CTA
   - "split_layout": 50/50 or 60/40 image vs text divide (best for exhibitions, conferences)
   - "three_column_grid": Multi-track hackathons, academic symposiums, content-dense schedules
5. TYPOGRAPHY HARD CONSTRAINTS:
   - Headline: 72pt - 110pt (maximum 3 lines, never shrink below 60pt).
   - Subheadline: ~1/3 to 1/4 of headline size (24pt - 32pt).
   - Body & Logistics: Minimum 14pt - 18pt for print legibility.
   - Max 2 Typeface Families: Display family + Neutral Grotesque/Monospace family.
   - Body text must pass WCAG 4.5:1 contrast against its direct background.
6. DUAL-MODEL PROMPT ENGINEERING:
   - Ideogram (Layer 0 Background):
     Generate pure atmospheric background art with a dedicated CALM NEGATIVE SPACE for typography.
     MUST INCLUDE NEGATIVE DIRECTIVE: "PURE NON-TEXT BACKGROUND ARTWORK: ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO SIGNAGE, NO LABELS, NO WATERMARKS."
     Must specify "elements": [] so Ideogram does not bake in labeled sub-objects.
   - Qwen-Image 2.1 (Layer 3 Foreground Hero):
     Generate a single isolated 3D subject on a pure black background for clean alpha cutout.
     Must have matching lighting direction to the background (e.g. "warm daylight from top-left").
   - Seamless Blending:
     Background and Hero must share lighting direction and palette hue families.
     Title typography sits at Layer 2, behind the top crest of the Layer 3 Hero (30-50px overlap for 3D depth).
     A soft gradient scrim (Layer 1) guarantees WCAG contrast without boxy cards.

Output strictly valid JSON conforming to this schema:
{{
  "archetype": "string (e.g. editorial, green_loop, aurora, cyber_ctf, jazz_ecm)",
  "composition_pattern": "focal_point | z_pattern | split_layout | three_column_grid",
  "design_movement": "string (e.g. Swiss Typographic Style, Warm Paper-Cut, Bauhaus)",
  "lighting_direction": "string (e.g. warm daylight from top-left)",
  "canvas_w": 1258,
  "canvas_h": 1772,
  "headline_font": "OFL-Display",
  "headline_pt": 96,
  "headline_blend_mode": "path3_infill",
  "date_font": "OFL-Sans",
  "date_pt": 32,
  "accent_color": "#HEX",
  "highlight_color": "#HEX",
  "background_color": "#HEX",
  "hero_target_size_px": 540,
  "hero_top_px": 280,
  "title_overlap_px": 40,
  "light_spill_radius_px": 900,
  "scrim_height_px": 720,
  "tracks_belt_visible": true,
  "metadata_bottom_px": 65,
  "title_treatment": "generative_3d | css_gradient_glow | flat",
  "art_prompts": {{
    "ideogram_background": "concise Ideogram prompt with calm negative space and explicit NO TEXT negative constraint",
    "qwen_hero_cutout": "isolated 3D subject on pure black background with matching lighting direction, no text"
  }},
  "planning_reasoning": "brief 2-sentence explanation of chosen composition pattern and movement anchor"
}}
"""
        res = self.client.generate_json(prompt=prompt, temperature=0.2)
        return GeminiLayoutPlan.model_validate(res)
