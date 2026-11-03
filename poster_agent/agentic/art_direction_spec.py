"""Single Model-Neutral Art Direction Specification and Deterministic Adapters.

Enforces:
1. One model-neutral art-direction spec produced by LLM or offline archetype engine.
2. Single source of truth for spatial zones across Ideogram, Qwen, and VectorCraft.
3. Zero conflict between background and hero: hero zone in background is a subtle architectural
   backdrop plane with natural studio shadows, never a competing dense graphic object or neon glow.
4. Professional academic & institutional tone: attractive, textured, and graphic (architectural
   lines, isometric grids, tactile paper grain), strictly avoiding cheesy neon party glows.
5. Deterministic adapters convert the spec to Ideogram 4.0 JSON, Flux 3 Klein prose,
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
    key_color: str = Field("#85CEBD", description="Color of natural directional studio key light")
    rim: str = Field("soft white", description="Color/hue of subtle rim edge light")


class SpatialZones(BaseModel):
    """Normalized bounding boxes in [ymin, xmin, ymax, xmax] on 0..1000 scale."""
    model_config = ConfigDict(extra="ignore")
    title: list[int] = Field(default_factory=lambda: [60, 50, 420, 520])
    hero: list[int] = Field(default_factory=lambda: [180, 480, 780, 960])
    details: list[int] = Field(default_factory=lambda: [780, 50, 980, 950])

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
    """Single model-neutral art direction contract planned by the LLM or archetype engine."""
    model_config = ConfigDict(extra="ignore")
    archetype: str = Field(..., description="e.g. tech_hackathon, cultural_night, academic_symposium, sports_meet, recruitment")
    composition_pattern: str = Field("asymmetric_right", description="asymmetric_right, diagonal_dynamic, split_columns, or centered_focal")
    motif: str = Field("subtle architectural grid lines and tactile fine paper grain", description="Attractive non-plain background textures/geometry")
    palette: PaletteTokens
    light: LightingSpec = Field(default_factory=LightingSpec)
    zones: SpatialZones = Field(default_factory=SpatialZones)
    hero: HeroSpec


# ==============================================================================
# Curated Offline Archetype Library (Deterministic Fallback with Asymmetric Layouts)
# ==============================================================================

ARCHETYPE_RECIPES: dict[str, ArtDirectionSpec] = {
    "tech_hackathon": ArtDirectionSpec(
        archetype="tech_hackathon",
        composition_pattern="asymmetric_right",
        motif="clean isometric blueprint grid with hairline circuit traces and tactile paper grain",
        palette=PaletteTokens(
            base="#070B19",
            primary="#00F5D4",
            secondary="#7B2FFF",
            accent="#FF3D68",
            text="#F0F6FC",
        ),
        light=LightingSpec(key_direction="upper-left", key_color="#00F5D4", rim="soft cyan"),
        zones=SpatialZones(
            title=[60, 50, 420, 520],
            hero=[180, 480, 780, 960],
            details=[780, 50, 980, 950],
        ),
        hero=HeroSpec(
            object="sculptural geometric microprocessor core with brushed alloy heatsinks and discrete logic elements",
            materials=["matte dark composite", "translucent polymer", "brushed titanium"],
            perspective="front three-quarter",
            width_pct=46.0,
        ),
    ),
    "cultural_night": ArtDirectionSpec(
        archetype="cultural_night",
        composition_pattern="diagonal_dynamic",
        motif="layered architectural paper-cut acoustic contours with subtle studio shadows",
        palette=PaletteTokens(
            base="#1E2842",
            primary="#85CEBD",
            secondary="#705355",
            accent="#C8C7CC",
            text="#FFFFFF",
        ),
        light=LightingSpec(key_direction="upper-left", key_color="#85CEBD", rim="warm daylight"),
        zones=SpatialZones(
            title=[60, 50, 320, 950],
            hero=[260, 280, 800, 960],
            details=[800, 50, 980, 950],
        ),
        hero=HeroSpec(
            object="sculptural modern turntable with matte dark vinyl record and geometric chrome tonearm",
            materials=["matte obsidian polymer", "brushed chrome", "subtle satin accents"],
            perspective="front three-quarter isometric",
            width_pct=48.0,
        ),
    ),
    "academic_symposium": ArtDirectionSpec(
        archetype="academic_symposium",
        composition_pattern="split_columns",
        motif="refined architectural perspective lines, clean constructivist geometry, and museum paper texture",
        palette=PaletteTokens(
            base="#0D1B2A",
            primary="#415A77",
            secondary="#778DA9",
            accent="#E0E1DD",
            text="#FFFFFF",
        ),
        light=LightingSpec(key_direction="top-left", key_color="#E0E1DD", rim="soft white"),
        zones=SpatialZones(
            title=[80, 50, 500, 520],
            hero=[160, 520, 760, 960],
            details=[760, 50, 980, 950],
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
        composition_pattern="diagonal_dynamic",
        motif="dynamic architectural diagonal rules and crisp stadium relief grid",
        palette=PaletteTokens(
            base="#0B132B",
            primary="#FF5722",
            secondary="#FFC107",
            accent="#00F5D4",
            text="#FFFFFF",
        ),
        light=LightingSpec(key_direction="upper-right", key_color="#FF5722", rim="soft daylight"),
        zones=SpatialZones(
            title=[60, 50, 300, 900],
            hero=[250, 320, 780, 960],
            details=[780, 50, 980, 950],
        ),
        hero=HeroSpec(
            object="sculptural dynamic flame baton with stylized aerodynamic carbon-fiber fins",
            materials=["brushed anodized alloy", "matte carbon fiber", "warm metal core"],
            perspective="front diagonal",
            width_pct=44.0,
        ),
    ),
    "recruitment": ArtDirectionSpec(
        archetype="recruitment",
        composition_pattern="asymmetric_right",
        motif="dimensional layered geometric panels with subtle institutional embossing and fine paper grain",
        palette=PaletteTokens(
            base="#070B19",
            primary="#00F5D4",
            secondary="#3A86FF",
            accent="#FFBE0B",
            text="#FFFFFF",
        ),
        light=LightingSpec(key_direction="upper-left", key_color="#00F5D4", rim="soft daylight"),
        zones=SpatialZones(
            title=[80, 50, 450, 520],
            hero=[180, 480, 760, 960],
            details=[780, 50, 980, 950],
        ),
        hero=HeroSpec(
            object="interlocking geometric dimensional badge symbol with clean architectural facets",
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
    - Academic, dignified, attractive textures (architectural geometry, tactile paper grain).
    - ZERO cheesy neon glows, zero high-intensity laser party lighting.
    - Hero zone is a subtle architectural backdrop plane with natural soft studio shadows.
    """
    palette_hexes = [
        spec.palette.base,
        spec.palette.primary,
        spec.palette.secondary,
        spec.palette.accent,
        spec.palette.text,
    ]

    hld = (
        f"A sophisticated academic institutional poster background visual featuring clean architectural geometry, "
        f"{spec.motif}, and refined natural ambient lighting from the {spec.light.key_direction}. "
        f"Designed with elegant spatial balance, fine tactile paper texture, and structured negative space for high typographic contrast."
    )

    style_description = {
        "aesthetics": f"Contemporary institutional graphic design, Swiss-style architectural geometry with {spec.motif}, clean tactile paper texture, dignified academic tone.",
        "lighting": f"Soft natural studio daylight from the {spec.light.key_direction}, gentle diffuse shadows, natural ambient illumination without neon glows.",
        "photo": "Clean architectural capture with fine tactile paper texture, subtle geometric depth, quiet matte finish, zero digital noise.",
        "medium": "Mixed-media institutional design",
        "color_palette": palette_hexes,
    }

    comp_bg = (
        f"A deep, refined background in tones of {spec.palette.base} layered with subtle architectural geometric line work and fine paper texture, "
        f"soft natural illumination from the {spec.light.key_direction}, clean and balanced."
    )

    # Single source of truth from spec.zones
    hz = spec.zones.hero
    tz = spec.zones.title
    dz = spec.zones.details

    elements = [
        # 1. Hero Zone backdrop: subtle architectural geometric structure / paper-cut relief plane
        {
            "type": "obj",
            "bbox": hz,
            "desc": (
                f"A refined architectural backdrop plane with subtle geometric depth in tones of {spec.palette.base} and {spec.palette.primary}, "
                f"gentle natural studio shadows, fine matte texture, serving as an attractive institutional setting for the hero."
            ),
            "color_palette": [spec.palette.base, spec.palette.primary, spec.palette.secondary],
        },
        # 2. Title Zone: Structured calm space with subtle hairline grid
        {
            "type": "obj",
            "bbox": tz,
            "desc": (
                f"Clean, calm high-contrast negative space in tone {spec.palette.base} accented with faint hairline architectural grid lines, "
                f"flat matte finish ensuring effortless typographic legibility."
            ),
            "color_palette": [spec.palette.base],
        },
        # 3. Details/Logistics Zone: Clean lower margin band
        {
            "type": "obj",
            "bbox": dz,
            "desc": (
                f"Clean, grounded {spec.palette.base} lower band with subtle geometric border rule, smooth matte finish."
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
    return (
        f"A sophisticated academic promotional poster background visual featuring clean architectural geometry, "
        f"subtle isometric grid structures, and {spec.motif}. "
        f"The layout is structured with clear spatial zones for institutional typography. "
        f"Illuminated with soft natural studio daylight from the {spec.light.key_direction} with gentle diffuse shadows, "
        f"anchored in dignified tones of {spec.palette.base} with subtle accents of {spec.palette.primary} and {spec.palette.secondary}. "
        f"High graphic clarity, tactile fine paper finish, elegant non-plain background with subtle geometric depth, "
        f"pure visual artwork with zero text, no letters, no typography, no watermarks, no neon glows."
    )


def spec_to_qwen_hero_prompts(spec: ArtDirectionSpec) -> tuple[str, str]:
    """Convert ArtDirectionSpec to positive and negative prompts for Qwen-Image 2.1 native alpha.
    
    Guarantees:
    - Concrete physical subject with materials.
    - Soft natural studio lighting (dignified, not glowy).
    - Positive phrasing for alpha isolation (no negative trigger backfire in positive prompt).
    - True negative_prompt string cleanly separated for ComfyUI KSampler negative conditioning.
    """
    materials_str = ", ".join(spec.hero.materials) if spec.hero.materials else "matte composite polymers, brushed alloy"
    
    positive_prompt = (
        f"A single iconic 3D {spec.hero.object}, crafted from {materials_str}, "
        f"{spec.hero.perspective} perspective, centered in frame with comfortable outer margins, "
        f"clean natural studio lighting from {spec.light.key_direction} with subtle {spec.light.rim} edge definition, "
        f"floating, fully isolated, clean sticker cutout, transparent background, empty alpha channel, 3D render, sharp edges, no cutoff edges"
    )

    negative_prompt = (
        "blurry, low quality, noise, solid background, white background, black background, "
        "text, watermark, hands, stand, base, pedestal, ground plane, floor shadow, cast shadow, "
        "floating cards, app icons, web buttons, UI widgets, dashboard panels, frames, borders, cropped, cutoff edges, neon glow"
    )

    return positive_prompt, negative_prompt
