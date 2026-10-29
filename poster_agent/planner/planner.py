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

### CRITICAL RULES:
1. STRICT VERBATIM RULE:
   - For every text element with `source: "brief"`, you MUST copy the exact string from the user's brief. Do NOT rephrase, abbreviate, or invent words!
   - For every text element with `source: "context"`, the string MUST appear verbatim in the Institutional Brand & Event Context.
2. MISSING FIELDS RULE:
   - Never invent event dates, venues, or speakers.
   - If a crucial event detail (such as date or venue) is missing from the brief, add it to `missing_fields: ["date", ...]` and leave elements list focused only on given text.
3. TEMPLATE & COORDINATES:
   - Pick the best template from the template library below that matches content density and desired orientation.
   - Coordinates are normalized 0-1000 scale: [y_min, x_min, y_max, x_max].
   - Ensure strictly: 0 <= y_min < y_max <= 1000 and 0 <= x_min < x_max <= 1000.
4. BRAND ASSETS:
   - Always place the required institutional logo from context (e.g. `college_logo.png`) in a clean top or bottom slot.
   - Use the official brand palette hex codes provided in the context document.
5. ART GENERATION PROMPT:
   - Craft a high-quality visual art prompt for `art_slots` that fits the theme of the event without including embedded text.

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

