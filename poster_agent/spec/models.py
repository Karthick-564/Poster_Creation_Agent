"""Pydantic models and JSON Schema for PosterSpec.

Designed for Groq strict structured outputs:
- All fields required in schema (optional values are type-or-null)
- additionalProperties: false at every nested object
- Coordinates in 0-1000 scale
"""
import copy
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HEX_COLOR_REGEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class BBox(BaseModel):
    """Normalized bounding box on a 0-1000 coordinate scale.
    Format corresponds to [y_min, x_min, y_max, x_max].
    """
    model_config = ConfigDict(extra="forbid")

    y_min: int = Field(..., ge=0, le=1000, description="Top coordinate (0-1000)")
    x_min: int = Field(..., ge=0, le=1000, description="Left coordinate (0-1000)")
    y_max: int = Field(..., ge=0, le=1000, description="Bottom coordinate (0-1000)")
    x_max: int = Field(..., ge=0, le=1000, description="Right coordinate (0-1000)")

    @model_validator(mode="after")
    def validate_bounds(self) -> "BBox":
        if self.y_min >= self.y_max:
            raise ValueError(f"y_min ({self.y_min}) must be strictly less than y_max ({self.y_max})")
        if self.x_min >= self.x_max:
            raise ValueError(f"x_min ({self.x_min}) must be strictly less than x_max ({self.x_max})")
        return self

    def to_list(self) -> list[int]:
        """Return [y_min, x_min, y_max, x_max]."""
        return [self.y_min, self.x_min, self.y_max, self.x_max]

    @classmethod
    def from_list(cls, coords: list[int] | tuple[int, int, int, int]) -> "BBox":
        if len(coords) != 4:
            raise ValueError("BBox requires exactly 4 coordinates [y_min, x_min, y_max, x_max]")
        return cls(y_min=coords[0], x_min=coords[1], y_max=coords[2], x_max=coords[3])

    def to_pixels(self, canvas_w: int, canvas_h: int) -> tuple[int, int, int, int]:
        """Convert to (left, top, right, bottom) pixel coordinates."""
        left = int(round(self.x_min * canvas_w / 1000.0))
        top = int(round(self.y_min * canvas_h / 1000.0))
        right = int(round(self.x_max * canvas_w / 1000.0))
        bottom = int(round(self.y_max * canvas_h / 1000.0))
        return (left, top, right, bottom)

    def width_px(self, canvas_w: int) -> int:
        return int(round((self.x_max - self.x_min) * canvas_w / 1000.0))

    def height_px(self, canvas_h: int) -> int:
        return int(round((self.y_max - self.y_min) * canvas_h / 1000.0))


TextRole = Literal[
    "headline",
    "subheadline",
    "date",
    "venue",
    "body",
    "label",
    "footer",
]

TextSource = Literal["brief", "context"]


class TextElement(BaseModel):
    """Text element in the poster spec."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Unique element identifier (e.g. headline_1)")
    role: TextRole = Field(..., description="Semantic hierarchy role")
    text: str = Field(..., min_length=1, description="Verbatim text string")
    source: TextSource = Field(..., description="Origin of text: brief or context")
    font: str = Field(..., description="CSS font family name")
    size: int = Field(..., ge=6, le=300, description="Font size in pt")
    weight: int = Field(..., ge=100, le=900, description="Font weight (e.g. 400, 600, 700, 800)")
    color: str = Field(..., description="Hex color in #RRGGBB format")
    box: BBox = Field(..., description="Bounding box in 0-1000 coordinates")

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        v = v.strip().upper()
        if not HEX_COLOR_REGEX.match(v):
            raise ValueError(f"Color must be in #RRGGBB format, got {v}")
        return v


class LogoPlacement(BaseModel):
    """Logo placement instruction."""
    model_config = ConfigDict(extra="forbid")

    file: str = Field(..., description="Filename in assets/ directory")
    box: BBox = Field(..., description="Bounding box in 0-1000 coordinates")
    clear_space_px: int | None = Field(default=None, description="Required padding around logo in px")


class ArtSlot(BaseModel):
    """Art generator background/element slot."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Unique slot id")
    prompt: str = Field(..., description="Detailed visual prompt for this slot")
    box: BBox = Field(..., description="Bounding box in 0-1000 coordinates")
    transparent: bool = Field(..., description="Whether art requires transparent background")


class PosterSpec(BaseModel):
    """Complete, self-contained specification for a poster."""
    model_config = ConfigDict(extra="forbid")

    canvas_width_px: int = Field(default=2480, ge=500, le=8000, description="Canvas width in pixels")
    canvas_height_px: int = Field(default=3508, ge=500, le=8000, description="Canvas height in pixels")
    dpi: int = Field(default=300, ge=72, le=600, description="Print DPI")
    template_id: str = Field(..., description="Layout template identifier used")
    palette: list[str] = Field(..., max_length=16, description="Color palette as list of #RRGGBB hex strings")
    text_safe_zones: list[BBox] = Field(default_factory=list, description="Calm zones reserved for text")
    elements: list[TextElement] = Field(..., description="All text elements in hierarchical order")
    logos: list[LogoPlacement] = Field(default_factory=list, description="Logo placements")
    art_slots: list[ArtSlot] = Field(default_factory=list, description="Art slots for generator")
    assumptions: list[str] = Field(default_factory=list, description="Stylistic and layout assumptions made")
    missing_fields: list[str] = Field(default_factory=list, description="Required fields missing from brief")
    qr_code: str | None = Field(default=None, description="Optional QR code URL or payload")

    @field_validator("palette")
    @classmethod
    def validate_palette(cls, v: list[str]) -> list[str]:
        cleaned = []
        for c in v:
            c = c.strip().upper()
            if not HEX_COLOR_REGEX.match(c):
                raise ValueError(f"Palette color must be in #RRGGBB format, got {c}")
            cleaned.append(c)
        return cleaned


def enforce_groq_strict_properties(schema_node: dict[str, Any]) -> None:
    """Recursively enforce Groq strict structured output requirements:
    1. Every object must have 'additionalProperties': False
    2. All properties listed in 'properties' must be included in 'required'
    """
    if not isinstance(schema_node, dict):
        return

    # Check if object
    if schema_node.get("type") == "object" or "properties" in schema_node:
        schema_node["type"] = "object"
        schema_node["additionalProperties"] = False
        props = schema_node.get("properties", {})
        schema_node["required"] = list(props.keys())

    # Recurse through properties, items, $defs, anyOf, etc.
    for k, v in schema_node.items():
        if isinstance(v, dict):
            enforce_groq_strict_properties(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    enforce_groq_strict_properties(item)


def get_groq_strict_json_schema() -> dict[str, Any]:
    """Generate a clean JSON schema strictly adhering to Groq's json_schema mode."""
    schema = copy.deepcopy(PosterSpec.model_json_schema())
    enforce_groq_strict_properties(schema)
    return schema
