"""Groq-powered planner creating PosterSpec from requirements and context."""
import json
import os
from typing import Any
from groq import Groq

from poster_agent.config.settings import AppConfig, get_config
from poster_agent.context.loader import ContextBundle
from poster_agent.spec.models import (
    PosterSpec,
    get_groq_strict_json_schema,
)
from .templates import TemplateLibrary, get_template_library
from .verifier import verify_spec


PLANNER_SYSTEM_PROMPT = """You are a World-Class Graphic Design Art Director and Layout Planner.
Your task is to transform event briefs into an exact, production-ready `PosterSpec` JSON object.

### CRITICAL RULES & INSTRUCTIONS:

1. EXHAUSTIVE TEXT FIDELITY (ZERO DROPPED FIELDS):
   - You MUST extract and represent EVERY single piece of text declared in the brief (Title, Subtitle, Tagline, Date, Time, Venue, Prize, Tracks, Team Size, CTA, Organizer, etc.).
   - NEVER drop, truncate, or combine required fields.
   - STRICT VERBATIM: Copy strings verbatim from the user brief. Preserve symbols exactly (e.g. '₹', '|', ':'). Do not rephrase or invent words!
   - If and only if a vital field is completely absent from the brief, record it in `missing_fields`. Never invent missing info.

2. SOVEREIGN BRIEF VS CONTEXT (ZERO UNWANTED INVENTIONS):
   - The user's brief is sovereign. If the brief states "add nothing else", "no logos", or specifies its own organizer, do NOT inject institutional context names or logos.
   - Only place logos in `logos` if explicitly instructed by the brief. If "no logos" is requested, `logos` MUST be strictly an empty list `[]`.
   - Never generate a QR element unless `qr_code` contains a valid URL string or QR payload.

3. CANVAS DIMENSIONS & DPI:
   - Extract the canvas dimensions from the brief if specified (e.g., 1024 x 1536).
   - Set `canvas_width_px` and `canvas_height_px` to match the brief (defaulting to 2480 x 3508 if unspecified).
   - Set `dpi` to 300.

4. PALETTE & COLOR HARMONY:
   - Extract the exact hex colors from the brief if provided; otherwise compose a cohesive 4-to-6 color palette.
   - Every text element's `color` MUST be an exact match from the `palette` array. Never invent off-palette hex colors.
   - Contrast: Ensure light text (#FFFFFF, bright neon) is placed against dark background tones, meeting WCAG AAA contrast.

5. TYPOGRAPHIC HIERARCHY & SIZING (Tied to Canvas Width):
   - Strictly obey the hierarchy order specified in the brief. For example:
     * Tier 1 (Title): Massive display size (70-90pt), weight 800-900, geometric display sans (e.g. "Outfit", "Montserrat").
     * Tier 2 (Date, Venue): Prominent readable size (28-36pt), weight 700.
     * Tier 3 (Subtitle, Prize): High-impact secondary size (24-30pt), weight 600-700.
     * Tier 4 (Tagline): Editorial size (20-24pt), weight 500-600 (strictly scaled below Date/Venue if brief ranks it lower).
     * Tier 5 (Tracks, Time, Team Size): Structured data size (18-22pt), weight 500-600. Use monospace (e.g. "JetBrains Mono", "Courier Prime", "monospace") when requested for technical tracks or terminal style.
     * Tier 6 (CTA, Organizer): Clean badge or footer size (18-22pt), weight 700-800.
   - MINIMUM SIZE FLOOR: No text element should be smaller than 16pt so all text remains crisp at thumbnail glance.

6. NORMALIZED COORDINATES (0-1000) & THREE-TIER VERTICAL ZONING:
   - Coordinates `[y_min, x_min, y_max, x_max]` are strictly normalized integers from 0 to 1000.
   - Margins: 6% margin means content stays within x: 60..940 and y: 60..940.
   - You MUST distribute the elements across the full canvas height according to the brief's zones:
     * TOP ~20% (y: 60 to 200): Title area. Title, Subtitle, or Tagline.
     * MIDDLE ~35% (y: 210 to 540): Visual motif (`art_slots`). NO TEXT ELEMENTS ALLOWED IN y: 210 to 540! Text must NOT overlap the central art slot.
     * LOWER ~45% (y: 550 to 940): All informational blocks distributed evenly on a clean grid, extending all the way down to y: 940 so the bottom is balanced and never left empty.
   - Consistent Grid: Left-align info blocks on consistent x coordinates (e.g. x_min: 60).
   - Side-by-side blocks: Partition x coordinates cleanly (e.g. Date at x: 60..480, Venue at x: 510..940).
   - ABSOLUTE OVERLAP PROHIBITION: Every text bounding box must be completely non-overlapping with other text and non-overlapping with the art slot.

7. ART PROMPT SPECIFICATION (`art_slots`):
   - Keep the prompt concise, evocative, and under 50 words.
   - Describe positive visual details: focal subject, 3D materials (obsidian, iridescent glass, glowing laser vectors), lighting (rim lights, volumetric glow), and a calm dark backdrop (#0A0E17).
   - NEVER write negative enumerations (e.g. do NOT output 'no people, no faces, no shoes, no animals...'). Simply state: 'Minimalist centered 3D motif on dark atmospheric background.'

### INSTITUTIONAL CONTEXT (Use only if brief requests or belongs to institution):
{context_markdown}

### TEMPLATE LIBRARY REFERENCE:
{template_library_text}
"""


class PosterPlanner:
    """Calls Groq strict JSON output to generate verified PosterSpec."""

    def __init__(
        self,
        config: AppConfig | None = None,
        template_library: TemplateLibrary | None = None,
        client: Any | None = None,
    ):
        self.config = config or get_config()
        self.templates = template_library or get_template_library()
        self.client = client

    def _get_client(self) -> Groq:
        if self.client is not None:
            return self.client
        api_key = self.config.groq.api_key
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY environment variable is not set. "
                "Please set GROQ_API_KEY to run the planner."
            )
        return Groq(api_key=api_key, timeout=self.config.groq.timeout_seconds)

    def plan(
        self,
        requirements_text: str,
        context: ContextBundle,
        model_override: str | None = None,
        skip_verification: bool = False,
    ) -> PosterSpec:
        """Call Groq API to produce PosterSpec and verify verbatim compliance."""
        system_content = PLANNER_SYSTEM_PROMPT.format(
            context_markdown=context.raw_markdown,
            template_library_text=self.templates.format_for_prompt(),
        )

        model_name = model_override or self.config.groq.model
        client = self._get_client()

        # Strict JSON Schema format for Groq
        schema = get_groq_strict_json_schema()

        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": f"Create a promotional poster spec for this event:\n\n{requirements_text}",
            },
        ]

        try:
            chat_completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "poster_spec",
                        "schema": schema,
                        "strict": True,
                    },
                },
                temperature=self.config.groq.temperature,
                max_tokens=self.config.groq.max_tokens,
            )
        except Exception:
            # Fallback to json_object mode if model does not support json_schema
            chat_completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                response_format={
                    "type": "json_object",
                },
                temperature=self.config.groq.temperature,
                max_tokens=self.config.groq.max_tokens,
            )

        raw_json_str = chat_completion.choices[0].message.content or "{}"
        data = json.loads(raw_json_str)

        spec = PosterSpec.model_validate(data)

        # Deduplicate any text elements that overlap directly with official logos in the header band
        if spec.logos:
            clean_elements = []
            for elem in spec.elements:
                is_logo_collision = False
                for logo in spec.logos:
                    if (
                        elem.role in ("label", "body", "headline")
                        and abs(elem.box.y_min - logo.box.y_min) < 50
                        and abs(elem.box.x_min - logo.box.x_min) < 80
                    ):
                        is_logo_collision = True
                        break
                if not is_logo_collision:
                    clean_elements.append(elem)
            spec.elements = clean_elements

        if not skip_verification:
            verify_spec(spec=spec, brief_text=requirements_text, context=context)

        return spec

