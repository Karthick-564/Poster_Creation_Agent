"""Single Model-Neutral Art Direction Specification and Deterministic Adapters.

Enforces:
1. One model-neutral art-direction spec produced by LLM or offline archetype engine.
2. Single source of truth for spatial zones across Ideogram, Qwen, and VectorCraft.
3. Zero conflict between background and hero: hero zone in background is a soft glow / light pool,
   never a competing dense graphic object.
4. Deterministic adapters convert the spec to Ideogram 4.0 JSON, Flux 3 Klein prose,
   and Qwen-Image 2.1 positive/negative prompts.
"""
from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaletteTokens(BaseModel):
    model_config = ConfigDict(extra="ignore")
    base: str = Field(..., description="Canvas/deep substrate background hex")
    primary: str = Field(..., description="Primary brand accent hex")
    secondary: str = Field(..., description="Secondary brand accent hex")
    accent: str = Field(..., description="Vibrant highlight hex")
    text: str = Field("#F0F6FC", description="High-contrast text hex")

    @field_validator("base", "primary", "secondary", "accent", "text")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        clean = v.strip().upper()
        if not re.match(r"^#[0-9A-F]{6}$", clean):
            raise ValueError(f"Invalid hex color: {v}")
        return clean


class LightingSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    key_direction: str = Field("upper-left", description="upper-left, top, or upper-right")
    key_color: str = Field("#00F5D4", description="Color of primary directional key light")
    rim: str = Field("cyan", description="Color/hue of rim edge light")


class SpatialZones(BaseModel):
    """Normalized bounding boxes in [ymin, xmin, ymax, xmax] on 0..1000 scale."""
    model_config = ConfigDict(extra="ignore")
    title: list[int] = Field(default_factory=lambda: [0, 0, 250, 1000])
    hero: list[int] = Field(default_factory=lambda: [250, 150, 750, 850])
    details: list[int] = Field(default_factory=lambda: [750, 0, 1000, 1000])

    @field_validator("title", "hero", "details")
    @classmethod
    def validate_bbox(cls, v: list[int]) -> list[int]:
        if len(v) != 4:
            raise ValueError(f"BBox must have 4 integers [ymin, xmin, ymax, xmax], got {v}")
        ymin, xmin, ymax, xmax = v
        if not (0 <= ymin < ymax <= 1000 and 0 <= xmin < xmax <= 1000):
            raise ValueError(f"BBox coordinates out of bounds or inverted: {v}")
        return v


class HeroSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    object: str = Field(..., description="Concrete physical/sculptural object description")
    materials: list[str] = Field(default_factory=list, description="Physical material textures")
    perspective: str = Field("front three-quarter", description="Viewing angle/camera perspective")
    width_pct: float = Field(45.0, description="Target width percentage of canvas (15-70)")


class ArtDirectionSpec(BaseModel):
    """Single model-neutral art direction contract."""
    model_config = ConfigDict(extra="ignore")
    archetype: str = Field(..., description="e.g. tech_hackathon, cultural_night, academic_symposium, sports_meet, recruitment")
    motif: str = Field("faint perspective grid, fine ambient particles", description="Subtle background textures/geometry")
    palette: PaletteTokens
    light: LightingSpec = Field(default_factory=LightingSpec)
    zones: SpatialZones = Field(default_factory=SpatialZones)
    hero: HeroSpec


# ==============================================================================
# Curated Offline Archetype Library (Deterministic Fallback)
# ==============================================================================

ARCHETYPE_RECIPES: dict[str, ArtDirectionSpec] = {
    "tech_hackathon": ArtDirectionSpec(
        archetype="tech_hackathon",
        motif="faint digital grid lines and subtle ambient data particles",
        palette=PaletteTokens(
            base="#070B19",
            primary="#00F5D4",
            secondary="#7B2FFF",
            accent="#FF3D68",
            text="#F0F6FC",
        ),
        light=LightingSpec(key_direction="upper-left", key_color="#00F5D4", rim="cyan"),
        zones=SpatialZones(
            title=[0, 0, 250, 1000],
            hero=[250, 150, 750, 850],
            details=[750, 0, 1000, 1000],
        ),
        hero=HeroSpec(
            object="sculptural crystalline microchip core with glowing holographic logic traces",
            materials=["matte dark composite", "translucent cyan acrylic", "brushed titanium"],
            perspective="front three-quarter",
            width_pct=46.0,
        ),
    ),
    "cultural_night": ArtDirectionSpec(
        archetype="cultural_night",
        motif="atmospheric stage haze and soft diagonal laser light ribbons",
        palette=PaletteTokens(
            base="#0A0B14",
            primary="#FF0055",
            secondary="#7928CA",
            accent="#00DFD8",
            text="#FFFFFF",
        ),
        light=LightingSpec(key_direction="upper-left", key_color="#FF0055", rim="magenta"),
        zones=SpatialZones(
            title=[0, 0, 250, 1000],
            hero=[250, 150, 750, 850],
            details=[750, 0, 1000, 1000],
        ),
        hero=HeroSpec(
            object="sculptural modern turntable with glowing acrylic vinyl record and geometric tonearm",
            materials=["matte obsidian polymer", "translucent neon acrylic", "brushed chrome"],
            perspective="front three-quarter isometric",
            width_pct=48.0,
        ),
    ),
    "academic_symposium": ArtDirectionSpec(
        archetype="academic_symposium",
        motif="minimal architectural shadow bands and clean structural grid",
        palette=PaletteTokens(
            base="#0D1B2A",
            primary="#415A77",
            secondary="#778DA9",
            accent="#E0E1DD",
            text="#FFFFFF",
        ),
        light=LightingSpec(key_direction="top-left", key_color="#E0E1DD", rim="soft white"),
        zones=SpatialZones(
            title=[0, 0, 250, 1000],
            hero=[250, 150, 750, 850],
            details=[750, 0, 1000, 1000],
        ),
        hero=HeroSpec(
            object="geometric kinetic gyroscope sculpture with nested brass and matte graphite rings",
            materials=["brushed brass", "matte dark graphite", "optical glass prism"],
            perspective="front three-quarter",
            width_pct=42.0,
        ),
    ),
    "sports_meet": ArtDirectionSpec(
        archetype="sports_meet",
        motif="dynamic kinetic speed lines and subtle stadium beam reflections",
        palette=PaletteTokens(
            base="#0B132B",
            primary="#FF5722",
            secondary="#FFC107",
            accent="#00F5D4",
            text="#FFFFFF",
        ),
        light=LightingSpec(key_direction="upper-right", key_color="#FF5722", rim="warm amber"),
        zones=SpatialZones(
            title=[0, 0, 250, 1000],
            hero=[250, 150, 750, 850],
            details=[750, 0, 1000, 1000],
        ),
        hero=HeroSpec(
            object="sculptural dynamic flame baton with stylized aerodynamic carbon-fiber fins",
            materials=["brushed anodized alloy", "matte carbon fiber", "warm radiant core"],
            perspective="front diagonal",
            width_pct=44.0,
        ),
    ),
    "recruitment": ArtDirectionSpec(
        archetype="recruitment",
        motif="layered structural architectural panels with subtle soft ambient gradients",
        palette=PaletteTokens(
            base="#070B19",
            primary="#00F5D4",
            secondary="#3A86FF",
            accent="#FFBE0B",
            text="#FFFFFF",
        ),
        light=LightingSpec(key_direction="upper-left", key_color="#00F5D4", rim="electric blue"),
        zones=SpatialZones(
            title=[0, 0, 250, 1000],
            hero=[250, 150, 750, 850],
            details=[750, 0, 1000, 1000],
        ),
        hero=HeroSpec(
            object="interlocking geometric dimensional badge symbol with illuminated circuit facets",
            materials=["matte dark composite", "translucent polymer", "brushed aluminum"],
            perspective="front three-quarter",
            width_pct=45.0,
        ),
    ),
}


def resolve_archetype_spec(
    brief_title: str = "",
    brief_category: str = "",
    school_palette: list[str] | None = None,
) -> ArtDirectionSpec:
    """Resolve base ArtDirectionSpec from archetype keywords with school palette override."""
    combined = f"{brief_title} {brief_category}".lower()
    
    if any(k in combined for k in ("hack", "code", "cyber", "ai", "robot", "tech", "dev", "data")):
        spec = ARCHETYPE_RECIPES["tech_hackathon"].model_copy(deep=True)
    elif any(k in combined for k in ("music", "night", "beat", "cultur", "dance", "fest", "dj", "concert")):
        spec = ARCHETYPE_RECIPES["cultural_night"].model_copy(deep=True)
    elif any(k in combined for k in ("symposium", "confer", "paper", "summit", "academ", "forum", "research")):
        spec = ARCHETYPE_RECIPES["academic_symposium"].model_copy(deep=True)
    elif any(k in combined for k in ("sport", "marathon", "athlet", "badminton", "cricket", "tournament", "game")):
        spec = ARCHETYPE_RECIPES["sports_meet"].model_copy(deep=True)
    else:
        spec = ARCHETYPE_RECIPES["recruitment"].model_copy(deep=True)

    # Inject school palette if provided
    if school_palette and len(school_palette) >= 3:
        p_clean = [c.upper() for c in school_palette if re.match(r"^#[0-9A-F]{6}$", c.strip().upper())]
        if len(p_clean) >= 3:
            spec.palette.base = p_clean[0]
            spec.palette.primary = p_clean[1]
            spec.palette.secondary = p_clean[2]
            if len(p_clean) > 3:
                spec.palette.accent = p_clean[3]
    return spec


# ==============================================================================
# Deterministic Model Adapters
# ==============================================================================

def spec_to_ideogram_payload(
    spec: ArtDirectionSpec,
    canvas_w: float = 1080.0,
    canvas_h: float = 1920.0,
) -> dict[str, Any]:
    """Convert ArtDirectionSpec to canonical Ideogram 4.0 JSON payload.
    
    Guarantees:
    - Bbox format [ymin, xmin, ymax, xmax] on 0..1000 scale.
    - Title and Details zones are calm and flat.
    - Central hero zone is a soft ambient light pool / glow, NEVER a competing dense object.
    - Thematic motif is positioned subtly near edges or at low contrast.
    """
    palette_hexes = [
        spec.palette.base,
        spec.palette.primary,
        spec.palette.secondary,
        spec.palette.accent,
        spec.palette.text,
    ]

    hld = (
        f"A contemporary poster background key visual featuring deep volumetric atmosphere, "
        f"{spec.motif}, and directional illumination from the {spec.light.key_direction}. "
        f"Engineered with calm negative space reserved at the upper and lower zones, smooth matte surfaces, quiet unbroken texture."
    )

    style_description = {
        "aesthetics": f"Contemporary institutional poster art, abstract atmospheric field with {spec.motif}, smooth matte gradients.",
        "lighting": f"Directional key light spill from the {spec.light.key_direction} in tones of {spec.light.key_color}, subtle {spec.light.rim} ambient rim falloff.",
        "photo": "Clean architectural digital capture, smooth matte finish, zero grain noise, quiet unbroken surfaces.",
        "medium": "Mixed-media digital art",
        "color_palette": palette_hexes,
    }

    comp_bg = (
        f"Deep ambient textured background in tones of {spec.palette.base} with soft atmospheric light spill from the {spec.light.key_direction}, "
        f"spacious calm negative space across the upper and lower canvas."
    )

    # Single source of truth from spec.zones
    # Point 3: Hero zone is a soft light pool / glow, not a competing object!
    hz = spec.zones.hero
    tz = spec.zones.title
    dz = spec.zones.details

    elements = [
        # 1. Soft central ambient light pool behind where the hero cutout will sit
        {
            "type": "obj",
            "bbox": hz,
            "desc": (
                f"A soft, diffused ambient light pool and atmospheric glow in tones of {spec.palette.primary} and {spec.palette.secondary}, "
                f"gentle radial falloff, no hard edges, smooth matte center serving as an illuminated backdrop."
            ),
            "color_palette": [spec.palette.primary, spec.palette.secondary, spec.palette.base],
        },
        # 2. Title Zone: Flat unbroken calm negative space
        {
            "type": "obj",
            "bbox": tz,
            "desc": (
                f"Completely calm, dark unbroken negative space in tone {spec.palette.base}, "
                f"flat matte finish with minimal ambient falloff, quiet unbroken surface."
            ),
            "color_palette": [spec.palette.base],
        },
        # 3. Details/Logistics Zone: Smooth dark lower band
        {
            "type": "obj",
            "bbox": dz,
            "desc": (
                f"Calm flat {spec.palette.base} lower zone with barely varied tone, smooth matte finish, blank unbroken surface."
            ),
            "color_palette": [spec.palette.base],
        },
    ]

    return {
        "high_level_description": hld,
        "style_description": style_description,
        "compositional_deconstruction": {
            "background": comp_bg,
            "elements": elements,
        },
    }


def spec_to_flux_prompt(spec: ArtDirectionSpec) -> str:
    """Convert ArtDirectionSpec to continuous photographic prose for Flux 3 Klein."""
    materials_str = ", ".join(spec.hero.materials) if spec.hero.materials else "matte composite and acrylic"
    return (
        f"A cinematic promotional poster background visual featuring deep volumetric atmosphere and {spec.motif}. "
        f"The upper third ({spec.zones.title[0]} to {spec.zones.title[2]} units) is an expansive, calm dark field in tone {spec.palette.base} with quiet surfaces. "
        f"The central midground contains a soft diffused ambient light glow in tones of {spec.palette.primary} and {spec.palette.secondary}. "
        f"The lower section is a clean, flat dark matte floor zone. "
        f"Illuminated with directional key lighting from the {spec.light.key_direction} in {spec.light.key_color} and subtle {spec.light.rim} rim falloff. "
        f"High optical clarity, smooth matte finish, vast calm negative space, pure visual artwork with zero text, no letters, no typography, no watermarks."
    )


def spec_to_qwen_hero_prompts(spec: ArtDirectionSpec) -> tuple[str, str]:
    """Convert ArtDirectionSpec to positive and negative prompts for Qwen-Image 2.1 native alpha.
    
    Guarantees:
    - Concrete physical subject with materials.
    - Matching lighting direction to the background.
    - Positive phrasing for alpha isolation (no negative trigger backfire in positive prompt).
    - True negative_prompt string cleanly separated for ComfyUI KSampler negative conditioning.
    """
    materials_str = ", ".join(spec.hero.materials) if spec.hero.materials else "matte composite polymers, brushed alloy"
    
    positive_prompt = (
        f"A single iconic 3D {spec.hero.object}, crafted from {materials_str}, "
        f"{spec.hero.perspective} perspective, centered in frame with comfortable outer margins, "
        f"directional key lighting from {spec.light.key_direction} in {spec.light.key_color} with {spec.light.rim} edge highlights, "
        f"floating, fully isolated, clean sticker cutout, transparent background, empty alpha channel, 3D render, sharp edges, no cutoff edges"
    )

    negative_prompt = (
        "blurry, low quality, noise, solid background, white background, black background, "
        "text, watermark, hands, stand, base, pedestal, ground plane, floor shadow, cast shadow, "
        "floating cards, app icons, web buttons, UI widgets, dashboard panels, frames, borders, cropped, cutoff edges"
    )

    return positive_prompt, negative_prompt

