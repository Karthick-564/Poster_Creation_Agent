"""Typed contracts for the v2 poster pipeline.

The v2 core keeps a single referee: deterministic layout and brand rules.
Generative models supply art and candidate layouts, but every candidate must
satisfy these contracts before it can be rendered or delivered.

Coordinates in layout contracts use a 0-1000 normalized scale so a plan is
resolution independent. Raster and manifest artifacts use pixels.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HEX_COLOR_REGEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

TextRole = Literal[
    "eyebrow",
    "headline",
    "subheadline",
    "tagline",
    "date",
    "time",
    "venue",
    "body",
    "cta",
    "closing",
    "organizer",
    "label",
    "footer",
]
FontRole = Literal["display", "body", "mono", "tamil"]
ImageRole = Literal["background", "hero", "decoration"]
ImageSource = Literal["ideogram", "qwen", "supplied", "native"]
Stage = Literal["brand", "ingest", "plan", "assets", "compose", "review"]
Severity = Literal["blocking", "warning"]


def _validate_hex(value: str) -> str:
    value = value.strip().upper()
    if not HEX_COLOR_REGEX.match(value):
        raise ValueError(f"Expected #RRGGBB color, got {value!r}")
    return value


class Box(BaseModel):
    """Normalized layout rectangle on a 0-1000 coordinate scale."""

    model_config = ConfigDict(extra="forbid")

    x: float = Field(..., ge=0, le=1000)
    y: float = Field(..., ge=0, le=1000)
    w: float = Field(..., gt=0, le=1000)
    h: float = Field(..., gt=0, le=1000)

    @model_validator(mode="after")
    def _inside_canvas(self) -> "Box":
        if self.x + self.w > 1000.001:
            raise ValueError(f"Box right edge {self.x + self.w:.2f} exceeds 1000")
        if self.y + self.h > 1000.001:
            raise ValueError(f"Box bottom edge {self.y + self.h:.2f} exceeds 1000")
        return self

    def to_px(self, width: int, height: int) -> tuple[float, float, float, float]:
        """Return (x, y, w, h) in pixels."""
        return (
            self.x * width / 1000.0,
            self.y * height / 1000.0,
            self.w * width / 1000.0,
            self.h * height / 1000.0,
        )

    def intersects(self, other: "Box") -> bool:
        return not (
            self.x + self.w <= other.x
            or other.x + other.w <= self.x
            or self.y + self.h <= other.y
            or other.y + other.h <= self.y
        )


class FormatSpec(BaseModel):
    """Physical or screen output format."""

    model_config = ConfigDict(extra="forbid")

    width: int = Field(..., ge=320, le=10000)
    height: int = Field(..., ge=320, le=10000)
    dpi: int = Field(default=300, ge=72, le=600)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height


class FontSpec(BaseModel):
    """Brand typeface roles plus explicit fallbacks for render hosts."""

    model_config = ConfigDict(extra="forbid")

    display: str
    body: str
    mono: str = "DejaVu Sans Mono"
    tamil: str = "Noto Sans Tamil"
    fallbacks: list[str] = Field(default_factory=lambda: ["DejaVu Sans", "Liberation Sans"])

    def resolve(self, role: FontRole, host_fonts: set[str] | None = None) -> str:
        """Return the first installed font in the role's preference chain."""
        primary = getattr(self, role)
        if not host_fonts or primary in host_fonts:
            return primary
        for candidate in self.fallbacks:
            if candidate in host_fonts:
                return candidate
        return primary


class LogoContract(BaseModel):
    """Institutional logo rules. These are gates, not suggestions."""

    model_config = ConfigDict(extra="forbid")

    asset: str | None = None
    required: bool = True
    placement: Literal["top-right", "top-left", "bottom-right", "bottom-left"] = "top-right"
    clear_space_mm: float = Field(default=10.0, ge=0.0, le=40.0)
    preserve_aspect: bool = True
    solid_field_only: bool = True
    allow_gradient_behind: bool = False
    max_width_pct: float = Field(default=22.0, gt=0.0, le=50.0)
    min_width_px: int = Field(default=120, ge=24)
    field_color: str = "#FFFFFF"

    @field_validator("field_color")
    @classmethod
    def _hex_field(cls, value: str) -> str:
        return _validate_hex(value)


class QrPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    min_size_px: int = Field(default=180, ge=64)
    quiet_zone_modules: int = Field(default=4, ge=2, le=8)
    label: str = "SCAN TO REGISTER"


class BrandContract(BaseModel):
    """Everything deterministic the pipeline knows about a school's brand."""

    model_config = ConfigDict(extra="forbid")

    school_id: str
    name: str
    palette: dict[str, str]
    fonts: FontSpec
    logo: LogoContract
    formats: dict[str, FormatSpec]
    qr: QrPolicy = Field(default_factory=QrPolicy)
    mandatory_elements: list[str] = Field(default_factory=lambda: ["title", "date", "venue", "logo"])
    safe_margin_pct: float = Field(default=4.0, ge=0.0, le=15.0)
    min_text_contrast: float = Field(default=4.5, ge=1.0, le=21.0)
    background_rules: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    review_threshold: float = Field(default=7.0, ge=0.0, le=10.0)

    @field_validator("palette")
    @classmethod
    def _validate_palette(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("palette must not be empty")
        return {key: _validate_hex(color) for key, color in value.items()}

    def color(self, role: str, fallback: str | None = None) -> str:
        if role in self.palette:
            return self.palette[role]
        if fallback:
            return fallback
        raise KeyError(f"Brand {self.school_id} has no palette role {role!r}")

    def palette_list(self) -> list[str]:
        order = ["primary", "secondary", "tertiary", "neutral", "surface"]
        values = [self.palette[k] for k in order if k in self.palette]
        values.extend(v for k, v in self.palette.items() if k not in order)
        seen: set[str] = set()
        return [c for c in values if not (c in seen or seen.add(c))]

    def safe_margin_px(self, fmt: FormatSpec) -> float:
        return min(fmt.width, fmt.height) * self.safe_margin_pct / 100.0

    def clear_space_px(self, fmt: FormatSpec) -> float:
        return self.logo.clear_space_mm / 25.4 * fmt.dpi


class TextBlock(BaseModel):
    """A single typographic element planned onto the canvas."""

    model_config = ConfigDict(extra="forbid")

    id: str
    role: TextRole
    text: str = Field(..., min_length=1)
    box: Box
    font_role: FontRole = "body"
    size: float = Field(..., gt=0, le=400)
    weight: int = Field(default=400, ge=100, le=900)
    color: str
    align: Literal["left", "center", "right"] = "left"
    tracking: float = Field(default=0.0, ge=-100.0, le=1000.0)
    line_height: float = Field(default=1.12, ge=0.8, le=2.0)
    max_lines: int = Field(default=4, ge=1, le=12)
    required: bool = True

    @field_validator("color")
    @classmethod
    def _hex_color(cls, value: str) -> str:
        return _validate_hex(value)


class ImageSlot(BaseModel):
    """A generative or supplied raster slot in the composition."""

    model_config = ConfigDict(extra="forbid")

    id: str
    role: ImageRole
    source: ImageSource
    prompt: str = ""
    box: Box
    transparent: bool = False
    blend: Literal["normal", "screen", "multiply", "over"] = "normal"
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    required: bool = False


class LogoSlot(BaseModel):
    """Logo placement planned from the brand contract."""

    model_config = ConfigDict(extra="forbid")

    id: str = "brand_logo"
    asset: str | None = None
    box: Box
    placement: Literal["top-right", "top-left", "bottom-right", "bottom-left"] = "top-right"
    clear_space_mm: float = 10.0
    solid_field: str = "#FFFFFF"
    preserve_aspect: bool = True

    @field_validator("solid_field")
    @classmethod
    def _hex_field(cls, value: str) -> str:
        return _validate_hex(value)


class QrSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: str = Field(..., min_length=1)
    box: Box
    label: str = "SCAN TO REGISTER"
    min_size_px: int = 180


class PosterSpec(BaseModel):
    """A complete, renderable candidate plan."""

    model_config = ConfigDict(extra="forbid")

    school_id: str
    candidate_id: str
    format: FormatSpec
    palette: list[str]
    background_color: str
    text_blocks: list[TextBlock]
    image_slots: list[ImageSlot]
    logo_slots: list[LogoSlot]
    qr: QrSlot | None = None
    required_elements: list[str] = Field(default_factory=list)
    design_notes: list[str] = Field(default_factory=list)
    seed: int = 0

    @field_validator("palette")
    @classmethod
    def _palette(cls, value: list[str]) -> list[str]:
        return [_validate_hex(c) for c in value]

    @field_validator("background_color")
    @classmethod
    def _background(cls, value: str) -> str:
        return _validate_hex(value)

    def text(self, role_or_id: str) -> TextBlock | None:
        for block in self.text_blocks:
            if block.id == role_or_id or block.role == role_or_id:
                return block
        return None

    def image(self, role_or_id: str) -> ImageSlot | None:
        for slot in self.image_slots:
            if slot.id == role_or_id or slot.role == role_or_id:
                return slot
        return None


class ResolvedImage(BaseModel):
    """A concrete image file resolved for a slot."""

    model_config = ConfigDict(extra="forbid")

    slot_id: str
    role: ImageRole
    path: str
    source: ImageSource
    width: int
    height: int
    transparent: bool = False
    generator: str = ""
    seed: int = 0
    prompt: str = ""
    placeholder: bool = False


class AssetBundle(BaseModel):
    """All image assets required to render one spec."""

    model_config = ConfigDict(extra="forbid")

    images: dict[str, ResolvedImage] = Field(default_factory=dict)
    logo: ResolvedImage | None = None
    warnings: list[str] = Field(default_factory=list)

    def get(self, slot_id_or_role: str) -> ResolvedImage | None:
        if slot_id_or_role in self.images:
            return self.images[slot_id_or_role]
        for image in self.images.values():
            if image.role == slot_id_or_role:
                return image
        return None


class ManifestRow(BaseModel):
    """Measured text row emitted by a renderer."""

    model_config = ConfigDict(extra="forbid")

    id: str
    role: str
    text: str
    x: float
    y: float
    width: float
    height: float
    size: float
    font: str = ""
    color: str = "#FFFFFF"
    style: str = ""

    def as_gate_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "size": self.size,
            "font": self.font,
            "color": self.color,
            "style": self.style,
        }


class RenderResult(BaseModel):
    """Rendered artifact plus measured geometry."""

    model_config = ConfigDict(extra="forbid")

    output_png: str
    width: int
    height: int
    rows: list[ManifestRow] = Field(default_factory=list)
    hero_rect: tuple[float, float, float, float] | None = None
    logo_rect: tuple[float, float, float, float] | None = None
    image_rects: dict[str, tuple[float, float, float, float]] = Field(default_factory=dict)
    engine: str = "mock"
    warnings: list[str] = Field(default_factory=list)
    commands_path: str | None = None


class GateIssue(BaseModel):
    """A single deterministic gate failure or warning, routed to a stage."""

    model_config = ConfigDict(extra="forbid")

    code: str
    gate: str
    stage: Stage
    severity: Severity
    message: str
    target: str = ""
    fix_hint: str | None = None
    measured: dict[str, Any] = Field(default_factory=dict)


class GateReport(BaseModel):
    """Result of one deterministic gate pass."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    issues: list[GateIssue] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def blocking(self) -> list[GateIssue]:
        return [i for i in self.issues if i.severity == "blocking"]

    @property
    def warnings(self) -> list[GateIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def primary_stage(self) -> Stage | None:
        """Route to the earliest stage that can actually repair the failure."""
        order: list[Stage] = ["brand", "ingest", "assets", "plan", "compose", "review"]
        failing = {i.stage for i in self.blocking}
        for stage in order:
            if stage in failing:
                return stage
        return None


class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    stage: Stage
    severity: Severity = "warning"
    message: str
    fix_hint: str | None = None


class ReviewResult(BaseModel):
    """A VLM or human critique. Never overrides deterministic failures."""

    model_config = ConfigDict(extra="forbid")

    score: float = Field(..., ge=0.0, le=10.0)
    issues: list[ReviewIssue] = Field(default_factory=list)
    summary: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def blocking(self) -> list[ReviewIssue]:
        return [i for i in self.issues if i.severity == "blocking"]


class AttemptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int
    candidate_id: str
    stage: str
    outcome: Literal["passed", "failed", "repaired", "skipped"]
    detail: str = ""


class PipelineResult(BaseModel):
    """Complete audit trail for one poster request."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    school_id: str
    spec: PosterSpec
    assets: AssetBundle
    render: RenderResult
    gates: GateReport
    review: ReviewResult | None = None
    attempts: list[AttemptRecord] = Field(default_factory=list)
    output_path: str = ""
    message: str = ""
