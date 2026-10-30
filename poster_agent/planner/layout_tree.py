"""Hierarchical Layout Tree and Modular Typographic Scale (PosterO CVPR 2025).

Organizes graphic elements into Gestalt Semantic Clusters:
1. HeroTitleCluster: Title, Tagline, Hero Asset, Foreground Accents
2. ContextCluster: Date, Venue, Time, Entry (Temporal and Spatial anchors)
3. MotivationCluster: Subtitle, Prize Badge, Keynote Tracks
4. ConversionCluster: CTA, Register URL, Contact, Hashtag, Organizer

Enforces:
- Perfect Fourth (1.333x) Modular Typographic Scale.
- 8px Vertical Baseline Rhythm (all gaps and paddings are multiples of 8).
"""
import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ModularTypographicScale(BaseModel):
    """Mathematically harmonized font sizes based on Perfect Fourth (1.333) ratio."""
    model_config = ConfigDict(extra="forbid")
    step_0_microcopy: int = 16    # 16px (Microcopy / allowlist labels)
    step_1_body: int = 21         # 16 * 1.333 ~ 21px (Venue, Time, Entry, Contact)
    step_2_subhead: int = 28      # 21 * 1.333 ~ 28px (Subtitle, Prize Badge, CTA)
    step_3_anchor: int = 38       # 28 * 1.333 ~ 38px (Date Primary Anchor)
    step_4_display: int = 104     # 38 * 1.333^3 ~ 104px (Hero Display Headline)


class BaseGridRhythm(BaseModel):
    """8px Vertical Baseline Grid units."""
    model_config = ConfigDict(extra="forbid")
    grid_unit: int = 8
    gap_xs: int = 8
    gap_sm: int = 16
    gap_md: int = 24
    gap_lg: int = 32
    gap_xl: int = 48
    gap_2xl: int = 64
    margin_canvas: int = 64


class SemanticCluster(BaseModel):
    """A Gestalt grouping of related visual elements."""
    model_config = ConfigDict(extra="forbid")
    name: str
    elements: list[str]
    z_index: int
    vertical_zone: Literal["top", "mid", "lower_scrim", "footer"]


class LayoutTreePlan(BaseModel):
    """Hierarchical layout blueprint structuring elements into harmonious clusters."""
    model_config = ConfigDict(extra="forbid")
    canvas_w: int = 1080
    canvas_h: int = 1350
    scale: ModularTypographicScale = Field(default_factory=ModularTypographicScale)
    grid: BaseGridRhythm = Field(default_factory=BaseGridRhythm)
    clusters: list[SemanticCluster] = Field(default_factory=list)


def build_semantic_layout_tree(canvas_w: int = 1080, canvas_h: int = 1350) -> LayoutTreePlan:
    """Construct the hierarchical layout tree with semantic clustering."""
    clusters = [
        SemanticCluster(
            name="HeroTitleCluster",
            elements=["title", "tagline", "hero_orb", "floating_lanterns"],
            z_index=10,
            vertical_zone="top",
        ),
        SemanticCluster(
            name="OrbitalEventsCluster",
            elements=["events_curved_path", "events_microcopy"],
            z_index=20,
            vertical_zone="mid",
        ),
        SemanticCluster(
            name="ContextCluster",
            elements=["date", "venue", "time", "entry"],
            z_index=22,
            vertical_zone="lower_scrim",
        ),
        SemanticCluster(
            name="MotivationCluster",
            elements=["subtitle", "prize_badge"],
            z_index=22,
            vertical_zone="lower_scrim",
        ),
        SemanticCluster(
            name="ConversionCluster",
            elements=["cta_button", "contact_email", "hashtag", "organizer"],
            z_index=24,
            vertical_zone="footer",
        ),
    ]

    return LayoutTreePlan(
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        scale=ModularTypographicScale(),
        grid=BaseGridRhythm(),
        clusters=clusters,
    )

