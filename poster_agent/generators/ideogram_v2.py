"""Ideogram 4.0 Payload Builder v2.

Adheres strictly to the user-verified schema from corrected_ideogram_request.json:
1. high_level_description: 1-2 sentence plain language summary without negative word incantations.
2. style_description: Flat string with inline palette ("Contemporary poster background art, ... Color palette: #0B132B, #505B63, #00F5D4.").
3. compositional_deconstruction:
   - background: scene shell description with calm zones.
   - elements: ALWAYS 1-2 concrete bbox objects (gradient band + calm lower zone), never empty [].
4. aspect_ratio: matched to brief canvas ("9:16", "4:5", etc.).
"""
import re
from typing import Any, Optional


def sanitize_plain_caption(text: str) -> str:
    """Sanitize prompt text into plain descriptive prose without safety-filter trigger phrasing."""
    if not text:
        return "Contemporary architectural background with clean negative space and soft ambient gradients."

    # Strip negative text incantations
    negative_phrases = [
        r"pure non-text background artwork:?",
        r"pure non-text visual illustration:?",
        r"strictly zero text:?",
        r"strictly no text:?",
        r"absolutely no text:?",
        r"no text:?",
        r"no words:?",
        r"no letters:?",
        r"no signage:?",
        r"no labels:?",
        r"no watermarks?:?",
        r"no numbers?:?",
        r"with strictly no text.*",
        r"pure art with no typography.*",
        r"without any text.*",
    ]
    cleaned = text
    for pat in negative_phrases:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

    # Remove individual trigger words when isolated
    cleaned = re.sub(r"\b(watermarks?|typography|signage|words?|letters?)\b", "", cleaned, flags=re.IGNORECASE)

    # Collapse multiple commas, colons, or punctuation runs (preventing orphaned commas like ", , ,")
    cleaned = re.sub(r"[,;:\s]+,", ",", cleaned)
    cleaned = re.sub(r",\s*,+", ",", cleaned)
    cleaned = re.sub(r",\s*\.", ".", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.:;")

    if len(cleaned) < 15:
        cleaned = "A contemporary atmospheric background key visual for an institutional poster with vast clean negative space"

    if not cleaned.endswith("."):
        cleaned += "."
    return cleaned


def resolve_aspect_ratio_and_resolution(
    canvas_w: float,
    canvas_h: float,
) -> tuple[str, str, int, int]:
    """Resolve (aspect_ratio_str, comfy_selector_label, width_px, height_px)."""
    ratio = canvas_w / canvas_h if canvas_h > 0 else 9.0 / 16.0
    if abs(ratio - 9.0 / 16.0) < 0.08 or (int(canvas_w), int(canvas_h)) == (1080, 1920):
        return "9:16", "9:16 (Portrait Widescreen)", 768, 1344
    elif abs(ratio - 4.0 / 5.0) < 0.08 or (int(canvas_w), int(canvas_h)) == (1080, 1350):
        return "4:5", "4:5 (Standard Portrait)", 896, 1120
    elif abs(ratio - 1.0) < 0.08:
        return "1:1", "1:1 (Square)", 1024, 1024
    elif abs(ratio - 16.0 / 9.0) < 0.08:
        return "16:9", "16:9 (Landscape Widescreen)", 1344, 768
    else:
        if ratio < 1.0:
            return "9:16", "9:16 (Portrait Widescreen)", 768, 1344
        return "16:9", "16:9 (Landscape Widescreen)", 1344, 768


def build_ideogram_v2_payload(
    description: str,
    palette: list[str],
    canvas_w: float = 1080.0,
    canvas_h: float = 1920.0,
    light_direction: str = "top_left",
    mood: Optional[str] = None,
) -> dict[str, Any]:
    """Build the single canonical Ideogram v2 structured prompt payload."""
    clean_desc = sanitize_plain_caption(description)
    palette_hexes = [c.upper() for c in palette[:5]] if palette else ["#0B132B", "#505B63", "#00F5D4"]
    bg_color = palette_hexes[0]
    aspect_str, _, _, _ = resolve_aspect_ratio_and_resolution(canvas_w, canvas_h)

    # 1. High level description
    hld = (
        f"{clean_desc} Deep ambient gradient field with soft atmospheric light spill from the {light_direction}, "
        f"calm engineered tone, vast clean negative space reserved at the top and bottom zones, matte finish with quiet surfaces."
    )
    # Ensure no stray punctuation runs or double commas
    hld = re.sub(r"[,;:\s]+,", ",", hld)
    hld = re.sub(r",\s*,+", ",", hld)
    hld = re.sub(r",\s*\.", ".", hld)
    hld = re.sub(r"\s+", " ", hld).strip()

    # 2. Style description: flat string with inline palette
    style_description = (
        f"Contemporary poster background art, architectural photography with smooth matte ambient lighting and subtle "
        f"abstract architectural shadows. Color palette: {', '.join(palette_hexes)}."
    )

    # 3. Compositional deconstruction: background + 1-2 non-empty elements
    # NB: never mention "text"/"typography" ("prepared for a typographic overlay"
    # reads as an instruction to render a wordmark — the failure seen in
    # runs/noir_beats_live, where "Clomailioka" + "2030" were baked into art).
    # Describe silence positively: blank, unbroken, quiet surfaces.
    comp_bg = (
        f"Deep ambient background in tones of {bg_color} with soft atmospheric light spill from the {light_direction}, "
        f"spacious calm negative space, top zone and bottom zone completely dark, flat and matte, quiet unbroken surfaces."
    )

    # Elements: concrete bounding boxes (normalized 0..1000)
    elements = [
        {
            "type": "obj",
            "bbox": [108, 150, 650, 950],
            "desc": f"Soft abstract ambient gradient ribbons of {bg_color} with subtle architectural shadows, smooth matte transitions, quiet surfaces.",
            "color_palette": palette_hexes[:3],
        },
        {
            "type": "obj",
            "bbox": [650, 0, 1000, 1000],
            "desc": f"Calm flat {bg_color} lower band with barely varied tone, smooth matte finish, blank unbroken surfaces.",
            "color_palette": palette_hexes[:2],
        },
    ]

    return {
        "high_level_description": hld,
        "style_description": style_description,
        "compositional_deconstruction": {
            "background": comp_bg,
            "elements": elements,
        },
        "aspect_ratio": aspect_str,
    }

