"""Unified Gemini API client for layout planning and multimodal vision critique."""
import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional, Union
from dotenv import load_dotenv

load_dotenv()

AVAILABLE_BLEND_MODES = [
    "normal", "darken", "multiply", "colorBurn", "lighten", "screen",
    "colorDodge", "overlay", "softLight", "hardLight", "difference",
    "exclusion", "hue", "saturation", "color", "luminosity"
]
AVAILABLE_TREATMENTS = ["dropShadow", "neonGlow", "grain", "none"]
AVAILABLE_ARCHETYPES = ["focal_point", "z_pattern", "split", "grid_3col"]
AVAILABLE_MOVEMENTS = ["static", "diagonal_sweep", "orbital", "convergence"]
AVAILABLE_KEY_DIRECTIONS = [
    "top_left", "top", "top_right", "left", "right",
    "bottom_left", "bottom", "bottom_right"
]
AVAILABLE_ROLES = ["headline", "subhead", "body", "microcopy", "badge", "cta"]
AVAILABLE_JUSTIFY = ["left", "center", "right"]
AVAILABLE_ALIGN = ["top", "middle", "bottom"]
AVAILABLE_SIZE_CLASSES = ["headline", "subhead", "body", "micro"]
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Strict Gemini responseSchema for Concept call (Stage 2a)
CONCEPT_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "thesis": {"type": "STRING", "description": "<= 25 words: what the poster argues"},
        "archetype": {
            "type": "STRING",
            "enum": AVAILABLE_ARCHETYPES,
        },
        "archetype_rationale": {"type": "STRING", "description": "<= 40 words"},
        "movement": {
            "type": "STRING",
            "enum": AVAILABLE_MOVEMENTS,
        },
        "light_plan": {
            "type": "OBJECT",
            "properties": {
                "key_direction": {
                    "type": "STRING",
                    "enum": AVAILABLE_KEY_DIRECTIONS,
                },
                "key_intensity": {"type": "INTEGER"},
                "fill_intensity": {"type": "INTEGER"},
                "rim": {
                    "type": "OBJECT",
                    "properties": {
                        "enabled": {"type": "BOOLEAN"},
                        "color_hex": {"type": "STRING"},
                    },
                    "required": ["enabled", "color_hex"],
                },
                "notes": {"type": "STRING"},
            },
            "required": ["key_direction", "key_intensity", "fill_intensity", "rim", "notes"],
        },
        "palette": {
            "type": "OBJECT",
            "properties": {
                "bg_60": {"type": "STRING"},
                "hero_30": {"type": "STRING"},
                "accent_10": {"type": "STRING"},
                "notes": {"type": "STRING"},
            },
            "required": ["bg_60", "hero_30", "accent_10", "notes"],
        },
        "typography": {
            "type": "OBJECT",
            "properties": {
                "body_stance": {"type": "STRING"},
                "tracking_stance": {"type": "STRING"},
            },
            "required": ["body_stance", "tracking_stance"],
        },
        "accent_row_choice": {"type": "STRING"},
        "assets": {
            "type": "OBJECT",
            "properties": {
                "hero": {
                    "type": "OBJECT",
                    "properties": {
                        "ideogram_caption": {"type": "STRING"},
                        "negative_caption": {"type": "STRING"},
                        "aspect": {"type": "STRING"},
                    },
                    "required": ["ideogram_caption", "negative_caption", "aspect"],
                },
                "background": {
                    "type": "OBJECT",
                    "properties": {
                        "ideogram_caption": {"type": "STRING"},
                    },
                    "required": ["ideogram_caption"],
                },
                "accents": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "id": {"type": "STRING"},
                            "ideogram_caption": {"type": "STRING"},
                        },
                        "required": ["id", "ideogram_caption"],
                    },
                },
            },
            "required": ["hero", "background", "accents"],
        },
        "calm_regions_requested": {
            "type": "ARRAY",
            "items": {
                "type": "ARRAY",
                "items": {"type": "INTEGER"},
            },
        },
        "self_check": {
            "type": "OBJECT",
            "properties": {
                "assumptions": {"type": "STRING"},
                "unsupported_artifacts": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
            },
            "required": ["assumptions", "unsupported_artifacts"],
        },
    },
    "required": [
        "thesis",
        "archetype",
        "archetype_rationale",
        "movement",
        "light_plan",
        "palette",
        "typography",
        "accent_row_choice",
        "assets",
        "calm_regions_requested",
        "self_check",
    ],
}

# Strict Gemini responseSchema for Layout call (Stage 4.5)
LAYOUT_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "slots": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "row_id": {"type": "STRING"},
                    "role": {
                        "type": "STRING",
                        "enum": AVAILABLE_ROLES,
                    },
                    "zone": {
                        "type": "ARRAY",
                        "items": {"type": "INTEGER"},
                    },
                    "justify": {
                        "type": "STRING",
                        "enum": AVAILABLE_JUSTIFY,
                    },
                    "align": {
                        "type": "STRING",
                        "enum": AVAILABLE_ALIGN,
                    },
                    "size_class": {
                        "type": "STRING",
                        "enum": AVAILABLE_SIZE_CLASSES,
                    },
                    "font": {"type": "STRING"},
                    "treatment": {
                        "type": "STRING",
                        "enum": AVAILABLE_TREATMENTS,
                    },
                    "max_lines": {"type": "INTEGER"},
                },
                "required": [
                    "row_id", "role", "zone", "justify", "align",
                    "size_class", "font", "treatment", "max_lines"
                ],
            },
        },
        "layer_plan": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "asset": {"type": "STRING"},
                    "z": {"type": "INTEGER"},
                    "blend": {
                        "type": "STRING",
                        "enum": AVAILABLE_BLEND_MODES,
                    },
                    "opacity": {"type": "INTEGER"},
                },
                "required": ["asset", "z", "blend", "opacity"],
            },
        },
        "scrims": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "zone": {
                        "type": "ARRAY",
                        "items": {"type": "INTEGER"},
                    },
                    "direction": {
                        "type": "STRING",
                        "enum": ["to_top", "to_bottom", "to_left", "to_right", "radial"],
                    },
                    "opacity_start": {"type": "NUMBER"},
                    "opacity_end": {"type": "NUMBER"},
                },
                "required": ["zone", "direction", "opacity_start", "opacity_end"],
            },
        },
        "checks": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "assertion": {"type": "STRING"},
                },
                "required": ["id", "assertion"],
            },
        },
        "calm_regions_used": {
            "type": "ARRAY",
            "items": {
                "type": "ARRAY",
                "items": {"type": "INTEGER"},
            },
        },
        "rationale": {"type": "STRING"},
    },
    "required": ["slots", "layer_plan", "scrims", "checks", "calm_regions_used", "rationale"],
}

# Repair schema (defined for Phase D 3b executor contract)
REPAIR_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "operations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "op": {
                        "type": "STRING",
                        "enum": [
                            "resize", "reflow", "restyle", "rescrim",
                            "move_layer", "rerender_asset", "fallback_title"
                        ],
                    },
                    "target_id": {"type": "STRING"},
                    "params": {"type": "OBJECT"},
                    "reason": {"type": "STRING"},
                },
                "required": ["op", "target_id", "params", "reason"],
            },
        },
        "notes": {"type": "STRING"},
    },
    "required": ["operations", "notes"],
}


def validate_concept_plan(plan: dict[str, Any]) -> tuple[bool, str]:
    """Validate concept plan against strict doctrine schema and bounds."""
    if not isinstance(plan, dict):
        return False, "Concept plan must be a JSON dictionary."

    required_keys = [
        "thesis", "archetype", "archetype_rationale", "movement",
        "light_plan", "palette", "typography", "accent_row_choice",
        "assets", "calm_regions_requested", "self_check",
    ]
    for k in required_keys:
        if k not in plan:
            return False, f"Missing required concept field: '{k}'"

    if plan["archetype"] not in AVAILABLE_ARCHETYPES:
        return False, f"Invalid archetype: {plan['archetype']}. Must be one of {AVAILABLE_ARCHETYPES}"

    if plan["movement"] not in AVAILABLE_MOVEMENTS:
        return False, f"Invalid movement: {plan['movement']}. Must be one of {AVAILABLE_MOVEMENTS}"

    lp = plan["light_plan"]
    if not isinstance(lp, dict):
        return False, "light_plan must be an object."
    if lp.get("key_direction") not in AVAILABLE_KEY_DIRECTIONS:
        return False, f"Invalid key_direction: {lp.get('key_direction')}"
    if not (0 <= lp.get("key_intensity", -1) <= 100):
        return False, f"key_intensity out of bounds [0, 100]: {lp.get('key_intensity')}"
    if not (0 <= lp.get("fill_intensity", -1) <= 100):
        return False, f"fill_intensity out of bounds [0, 100]: {lp.get('fill_intensity')}"
    rim = lp.get("rim")
    if not isinstance(rim, dict) or "enabled" not in rim or "color_hex" not in rim:
        return False, "light_plan.rim must have 'enabled' and 'color_hex'"
    if not HEX_COLOR_RE.match(str(rim.get("color_hex"))):
        return False, f"Invalid rim color_hex format: {rim.get('color_hex')}"

    pal = plan["palette"]
    if not isinstance(pal, dict):
        return False, "palette must be an object."
    for col_key in ["bg_60", "hero_30", "accent_10"]:
        c = str(pal.get(col_key, ""))
        if not HEX_COLOR_RE.match(c):
            return False, f"Invalid palette hex format for '{col_key}': {c}"

    calm_req = plan.get("calm_regions_requested")
    if not isinstance(calm_req, list):
        return False, "calm_regions_requested must be an array."
    if len(calm_req) > 4:
        return False, f"calm_regions_requested has {len(calm_req)} regions (max 4 allowed)."
    for reg in calm_req:
        if not isinstance(reg, (list, tuple)) or len(reg) != 4:
            return False, f"Calm region must be 4 coordinates [y0, x0, y1, x1]: {reg}"
        y0, x0, y1, x1 = reg
        if not (0 <= y0 < y1 <= 1000 and 0 <= x0 < x1 <= 1000):
            return False, f"Calm region coordinates invalid or inverted [0-1000]: {reg}"

    assets = plan.get("assets")
    if not isinstance(assets, dict):
        return False, "assets must be an object."
    if "hero" not in assets or "background" not in assets:
        return False, "assets must define 'hero' and 'background'"

    self_check = plan.get("self_check")
    if not isinstance(self_check, dict) or "assumptions" not in self_check:
        return False, "self_check must contain 'assumptions'"

    return True, ""


def validate_layout_plan(
    plan: dict[str, Any],
    available_fonts: Optional[list[str]] = None,
) -> tuple[bool, str]:
    """Validate layout plan slots, layer plan, scrims, and coordinate bounds."""
    if not isinstance(plan, dict):
        return False, "Layout plan must be a JSON dictionary."

    required_keys = ["slots", "layer_plan", "scrims", "checks", "calm_regions_used", "rationale"]
    for k in required_keys:
        if k not in plan:
            return False, f"Missing required layout field: '{k}'"

    slots = plan.get("slots")
    if not isinstance(slots, list) or len(slots) == 0:
        return False, "slots must be a non-empty array."

    seen_row_ids = set()
    for s in slots:
        if not isinstance(s, dict):
            return False, "Each slot must be an object."
        rid = s.get("row_id")
        if not rid:
            return False, "Slot missing 'row_id'"
        if rid in seen_row_ids:
            return False, f"Duplicate row_id in slots: '{rid}'"
        seen_row_ids.add(rid)

        if s.get("role") not in AVAILABLE_ROLES:
            return False, f"Invalid slot role '{s.get('role')}'. Must be in {AVAILABLE_ROLES}"
        if s.get("justify") not in AVAILABLE_JUSTIFY:
            return False, f"Invalid slot justify '{s.get('justify')}'. Must be in {AVAILABLE_JUSTIFY}"
        if s.get("align") not in AVAILABLE_ALIGN:
            return False, f"Invalid slot align '{s.get('align')}'. Must be in {AVAILABLE_ALIGN}"
        if s.get("size_class") not in AVAILABLE_SIZE_CLASSES:
            return False, f"Invalid slot size_class '{s.get('size_class')}'. Must be in {AVAILABLE_SIZE_CLASSES}"
        if s.get("treatment") not in AVAILABLE_TREATMENTS:
            return False, f"Invalid slot treatment '{s.get('treatment')}'. Must be in {AVAILABLE_TREATMENTS}"

        zone = s.get("zone")
        if not isinstance(zone, (list, tuple)) or len(zone) != 4:
            return False, f"Slot '{rid}' zone must be 4 coordinates [y0, x0, y1, x1]: {zone}"
        y0, x0, y1, x1 = zone
        if not (0 <= y0 < y1 <= 1000 and 0 <= x0 < x1 <= 1000):
            return False, f"Slot '{rid}' zone coordinates out of bounds [0-1000]: {zone}"

        if available_fonts is not None:
            font = s.get("font")
            if font and font not in available_fonts:
                return False, f"Slot '{rid}' font '{font}' not in available_fonts: {available_fonts}"

    layer_plan = plan.get("layer_plan")
    if not isinstance(layer_plan, list):
        return False, "layer_plan must be an array."
    for lp in layer_plan:
        if not isinstance(lp, dict):
            return False, "layer_plan entry must be an object."
        blend = lp.get("blend")
        if blend not in AVAILABLE_BLEND_MODES:
            return False, f"Invalid layer blend mode: '{blend}'. Must be in {AVAILABLE_BLEND_MODES}"
        op = lp.get("opacity")
        if not (0 <= op <= 100):
            return False, f"Invalid layer opacity: {op}. Must be in [0, 100]"

    scrims = plan.get("scrims")
    if not isinstance(scrims, list):
        return False, "scrims must be an array."
    for sc in scrims:
        if not isinstance(sc, dict):
            return False, "scrim entry must be an object."
        direction = sc.get("direction")
        if direction not in ("to_top", "to_bottom", "to_left", "to_right", "radial"):
            return False, f"Invalid scrim direction: '{direction}'"
        szone = sc.get("zone")
        if not isinstance(szone, (list, tuple)) or len(szone) != 4:
            return False, f"Scrim zone must be 4 coordinates: {szone}"
        y0, x0, y1, x1 = szone
        if not (0 <= y0 < y1 <= 1000 and 0 <= x0 < x1 <= 1000):
            return False, f"Scrim zone out of bounds [0-1000]: {szone}"
        op_start = sc.get("opacity_start", 0.0)
        op_end = sc.get("opacity_end", 1.0)
        if not (0.0 <= op_start <= 1.0 and 0.0 <= op_end <= 1.0):
            return False, f"Scrim opacity out of bounds [0.0, 1.0]: {op_start} -> {op_end}"

    return True, ""


def validate_repair_plan(plan: dict[str, Any]) -> tuple[bool, str]:
    """Validate repair plan operation schema (Phase D contract)."""
    if not isinstance(plan, dict):
        return False, "Repair plan must be a JSON dictionary."
    if "operations" not in plan or "notes" not in plan:
        return False, "Repair plan must contain 'operations' and 'notes'"

    valid_ops = {
        "resize", "reflow", "restyle", "rescrim",
        "move_layer", "rerender_asset", "fallback_title"
    }
    for op_item in plan.get("operations", []):
        if not isinstance(op_item, dict):
            return False, "Repair operation must be an object."
        op_name = op_item.get("op")
        if op_name not in valid_ops:
            return False, f"Invalid repair op: '{op_name}'. Must be one of {valid_ops}"
        if "target_id" not in op_item or "params" not in op_item or "reason" not in op_item:
            return False, "Repair operation must define target_id, params, and reason"

    return True, ""


class GeminiClient:
    """Client for Google Generative Language API with automatic model fallback."""

    FALLBACK_MODELS = [
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
    ]

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment or .env file.")

    def _call_api(self, model: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def generate_json(
        self,
        prompt: str,
        schema: Optional[dict[str, Any]] = None,
        system_instruction: str = "",
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        timeout: int = 30,
        validator: Optional[Callable[[dict[str, Any]], tuple[bool, str]]] = None,
    ) -> dict[str, Any]:
        """Generate structured JSON using Gemini text reasoning with schema enforcement and bounded retry.
        
        Attempts the generation, validating output structure against schema and validator.
        On failure, performs exactly ONE bounded retry. If both fail, returns an explicit failure
        object {'error': ...} without inventing data.
        """
        models_to_try = [model_name] if model_name else self.FALLBACK_MODELS

        gen_config: dict[str, Any] = {
            "responseMimeType": "application/json",
            "temperature": temperature,
        }
        if schema:
            gen_config["responseSchema"] = schema

        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": gen_config,
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        last_error = None
        # Max 2 attempts total (initial attempt + 1 bounded retry)
        for attempt in range(2):
            for m in models_to_try:
                try:
                    data = self._call_api(m, payload, timeout=timeout)
                except Exception as e:
                    # Model API level failure (503/404/timeout) -> fallback to next model
                    last_error = e
                    continue

                try:
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    parsed = json.loads(text)
                    if validator:
                        ok, err_msg = validator(parsed)
                        if not ok:
                            raise ValueError(f"Schema validation failed: {err_msg}")
                    return parsed
                except Exception as e:
                    # Schema or JSON parsing failure -> break model loop to retry next attempt
                    last_error = e
                    break

        return {"error": f"Gemini generate_json failed after retry: {last_error}"}

    def critique_image(
        self,
        image_input: str | Path | bytes,
        prompt: str,
        system_instruction: str = "",
        model_name: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Critique an image using Gemini multimodal vision reasoning."""
        import io
        from PIL import Image

        if isinstance(image_input, (str, Path)):
            img = Image.open(image_input)
        else:
            img = Image.open(io.BytesIO(image_input))

        # Downscale to fast preview resolution to prevent 503/timeout payload limits
        if max(img.size) > 1024:
            img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=85)
        img_bytes = buf.getvalue()
        mime_type = "image/jpeg"

        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        models_to_try = [model_name] if model_name else self.FALLBACK_MODELS

        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [
                        {"inlineData": {"mimeType": mime_type, "data": img_b64}},
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": temperature,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        last_error = None
        for attempt in range(1):
            for m in models_to_try:
                try:
                    data = self._call_api(m, payload, timeout=6)
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return json.loads(text)
                except Exception as e:
                    last_error = e
                    continue

        raise RuntimeError(f"Gemini API rate-limited or unavailable: {last_error}")
