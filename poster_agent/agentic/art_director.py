"""Stage 2.5: Art Director Module.

Orchestrates:
1. LLM synthesis of a single model-neutral ArtDirectionSpec.
2. Pydantic validation of the spec (rejects inconsistencies).
3. Deterministic conversion via adapters to Ideogram 4.0 JSON, Flux 3 Klein prose,
   and Qwen-Image 2.1 positive/negative prompts.
4. Seamless fallback to curated archetype recipes when offline or on validation error.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from poster_agent.agentic.art_direction_spec import (
    ArtDirectionSpec,
    resolve_archetype_spec,
    spec_to_ideogram_payload,
    spec_to_flux_prompt,
    spec_to_qwen_hero_prompts,
)
from poster_agent.agentic.llm_backend import LLMBackend


@dataclass
class ArtDirectionResult:
    spec: ArtDirectionSpec
    ideogram_payload: dict[str, Any]
    flux_prompt: str
    qwen_positive_prompt: str
    qwen_negative_prompt: str
    source: str = "llm"  # "llm" or "offline_archetype"


class ArtDirector:
    """Produces unified model-neutral art direction and generates model payloads."""

    def __init__(self, backend: Optional[LLMBackend] = None):
        self.backend = backend

    def direct(
        self,
        brief_title: str,
        brief_fields: dict[str, Any],
        school_palette: list[str] | None = None,
        canvas_w: float = 1080.0,
        canvas_h: float = 1920.0,
    ) -> ArtDirectionResult:
        """Synthesize unified art direction and derive all model prompts."""
        spec: Optional[ArtDirectionSpec] = None
        source = "offline_archetype"

        # 1. Try LLM synthesis if backend is available
        if self.backend is not None:
            try:
                spec = self._synthesize_with_llm(
                    brief_title=brief_title,
                    brief_fields=brief_fields,
                    school_palette=school_palette,
                )
                source = "llm"
            except Exception:
                spec = None

        # 2. Fallback to deterministic archetype engine
        if spec is None:
            brief_cat = brief_fields.get("category", "") or brief_fields.get("genre", "")
            spec = resolve_archetype_spec(
                brief_title=brief_title,
                brief_category=brief_cat,
                school_palette=school_palette,
            )
            source = "offline_archetype"

        # 3. Derive model-specific payloads through deterministic adapters
        ideogram_payload = spec_to_ideogram_payload(spec, canvas_w=canvas_w, canvas_h=canvas_h)
        flux_prompt = spec_to_flux_prompt(spec)
        qwen_pos, qwen_neg = spec_to_qwen_hero_prompts(spec)

        return ArtDirectionResult(
            spec=spec,
            ideogram_payload=ideogram_payload,
            flux_prompt=flux_prompt,
            qwen_positive_prompt=qwen_pos,
            qwen_negative_prompt=qwen_neg,
            source=source,
        )

    def _synthesize_with_llm(
        self,
        brief_title: str,
        brief_fields: dict[str, Any],
        school_palette: list[str] | None,
    ) -> ArtDirectionSpec:
        """Prompt LLM to output strictly the single model-neutral ArtDirectionSpec JSON."""
        system_prompt = (
            "You are the Art Director for an institutional poster pipeline. "
            "You produce a single model-neutral art-direction specification in JSON format. "
            "Never write tool calls or image model prompts directly. Output valid JSON matching the schema."
        )

        palette_hint = ", ".join(school_palette[:5]) if school_palette else "#070B19, #00F5D4, #7B2FFF, #FF3D68, #F0F6FC"
        user_prompt = f"""Event Title: {brief_title}
Brief Details:
{chr(10).join(f"- {k}: {v}" for k, v in brief_fields.items())}

Brand Palette: {palette_hint}

Produce a single JSON object matching this schema:
{{
  "archetype": "tech_hackathon | cultural_night | academic_symposium | sports_meet | recruitment",
  "motif": "string describing subtle ambient background texture/geometry (e.g. faint perspective grid, fine particles)",
  "palette": {{
    "base": "{school_palette[0] if school_palette else '#070B19'}",
    "primary": "{school_palette[1] if school_palette and len(school_palette)>1 else '#00F5D4'}",
    "secondary": "{school_palette[2] if school_palette and len(school_palette)>2 else '#7B2FFF'}",
    "accent": "{school_palette[3] if school_palette and len(school_palette)>3 else '#FF3D68'}",
    "text": "#F0F6FC"
  }},
  "light": {{
    "key_direction": "upper-left",
    "key_color": "{school_palette[1] if school_palette and len(school_palette)>1 else '#00F5D4'}",
    "rim": "cyan"
  }},
  "zones": {{
    "title": [0, 0, 250, 1000],
    "hero": [250, 150, 750, 850],
    "details": [750, 0, 1000, 1000]
  }},
  "hero": {{
    "object": "string describing a concrete physical sculptural object (e.g. holographic microprocessor with glowing circuit traces)",
    "materials": ["material 1", "material 2"],
    "perspective": "front three-quarter",
    "width_pct": 45.0
  }}
}}
Return ONLY valid JSON.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        resp = self.backend.chat(messages=messages)
        text = resp.content.strip()
        if "```" in text:
            # strip markdown fence
            parts = text.split("```")
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        data = json.loads(text)
        return ArtDirectionSpec.model_validate(data)
