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
Your task is to transform plain-language event requirements into an exact, production-ready `PosterSpec` JSON object.

### CRITICAL DESIGN & VERBATIM RULES:
1. STRICT VERBATIM RULE:
   - For every text element with `source: "brief"`, you MUST copy the exact string from the user's brief. Do NOT rephrase, abbreviate, or invent words!
   - For every text element with `source: "context"`, the string MUST appear verbatim in the Institutional Brand & Event Context.
2. MISSING FIELDS RULE:
   - Never invent event dates, venues, or speakers.
   - If a crucial event detail (such as date or venue) is missing from the brief, add it to `missing_fields: ["date", ...]` and leave elements list focused only on given text.
3. PRESTIGIOUS COLOR PALETTE:
   - Provide 4 to 6 harmonious hex colors in `palette` in uppercase #RRGGBB format.
   - Index 0 MUST be the deep dark background base (e.g. #0B132B, #0F172A).
   - Index 1 MUST be the primary glowing neon accent (e.g. #00F5D4 cyan, #38BDF8 sky).
   - Index 2 MUST be the secondary warm/vibrant accent (e.g. #F72585 magenta, #F59E0B amber).
   - Index 3 MUST be crisp white for headlines (#FFFFFF).
4. TYPOGRAPHIC HIERARCHY & SIZING:
   - Headline: font "Outfit" or "Montserrat", size 64-88pt, weight 900, color "#FFFFFF", role "headline".
   - Subheadline/Tagline: font "Inter", size 22-30pt, weight 600, color "#F1F5F9", role "subheadline".
   - Event Date: font "Inter", size 20-26pt, weight 700, color "#00F5D4", role "date".
   - Venue/Location: font "Inter", size 18-24pt, weight 700, color "#FFFFFF", role "venue".
   - Highlights/Tracks: font "Inter", size 14-18pt, weight 500, color "#E2E8F0", role "body".
   - CTA Badge: font "Outfit", size 14-18pt, weight 800, color "#00F5D4", role "label".
5. NON-OVERLAPPING COORDINATES (0-1000 Normalized scale: [y_min, x_min, y_max, x_max]):
   - Institutional Header band: y: 20 to 80 (Logo placed on left or right, e.g. x_min: 60, x_max: 280)
   - Headline zone: y: 110 to 230, x: 60 to 940
   - Subheadline zone: y: 240 to 300, x: 60 to 940
   - Art Hero Centerpiece: y: 315 to 715, x: 60 to 940 (Leave this dedicated central rectangle for visual artwork)
   - Date Card (left): y: 730 to 800, x: 60 to 480
   - Venue Card (right): y: 730 to 800, x: 510 to 940
   - Highlights/Tracks: y: 815 to 875, x: 60 to 940
   - Registration CTA Badge (left): y: 895 to 955, x: 60 to 460
   - QR Code container (right): y: 885 to 965, x: 840 to 940
   - Ensure strictly: 0 <= y_min < y_max <= 1000 and 0 <= x_min < x_max <= 1000 with clean padding.
6. CINEMATIC ART SPECIFICATION (`art_slots`):
   - You MUST generate an exquisitely detailed 3D or graphic concept prompt for the hero art slot.
   - Describe focal materials (e.g. polished obsidian, iridescent glass, glowing quantum cyber matrix, crystalline neural structures).
   - Specify dynamic studio lighting (rim lights, volumetric glow, deep atmospheric ambient shadows).
   - Tailor the concept directly to the theme of the event.
   - STRICT CONSTRAINT: You MUST include "Pure visual illustration with strictly NO text, NO words, NO letters, NO numbers, and NO logos." at the end of the prompt.

### INSTITUTIONAL CONTEXT:
{context_markdown}

### TEMPLATE LIBRARY:
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

        if not skip_verification:
            verify_spec(spec=spec, brief_text=requirements_text, context=context)

        return spec

