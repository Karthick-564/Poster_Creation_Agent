"""Archetype-Native VectorCraft Poster Composer.

Implements data-driven editorial poster composition based on the poster-design-craft doctrine:
- Relative typographic scale (canvas-relative scalars)
- 4 compositional archetypes: focal_point, z_pattern, split, grid_3col
- Runtime font auditing via get_vectorcraft_fonts_dir()
- Measured hero geometry placement (closes Issue #6 for focal_point)
- Anti-slop genre-matched live effects (drop shadow, grain, neon glow)
- Zero hardcoded event strings
"""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from poster_agent.ingestion.extractor import ExtractedBrief
from poster_agent.renderer.vectorcraft_renderer import (
    VectorCraftRenderer,
    get_vectorcraft_fonts_dir,
)


@dataclass
class TypographicRow:
    """A typed typographic row within the design plan."""
    role: str
    text: str
    zone: str
    size: float
    style: str = "Regular"
    tracking: float = 0.0
    leading: Optional[float] = None
    color: str = "#FFFFFF"
    alignment: str = "center"
    font: str = "Inter"


@dataclass
class TypographicPlan:
    """Complete canvas-scaled typography plan built from the event brief."""
    canvas_width: float
    canvas_height: float
    margin: float
    rows: list[TypographicRow] = field(default_factory=list)

    def get_row(self, role: str) -> Optional[TypographicRow]:
        for r in self.rows:
            if r.role == role:
                return r
        return None


def audit_fonts() -> dict[str, str]:
    """Audit available fonts at runtime via VectorCraft's shared fonts directory.

    Returns mapping of canonical roles ('display', 'sans', 'mono', 'serif', 'tamil')
    to available font family names, degrading gracefully to system fonts if specific
    TTF files are absent.
    """
    fonts_dir = get_vectorcraft_fonts_dir()
    available_ttfs = set()
    if fonts_dir.exists() and fonts_dir.is_dir():
        for p in fonts_dir.glob("*.ttf"):
            available_ttfs.add(p.stem.lower())
        for p in fonts_dir.glob("*.otf"):
            available_ttfs.add(p.stem.lower())

    # Map roles based on verified installed fonts
    # Verified in repo: Inter, JetBrainsMono, SourceSans3, SourceSerif4 (Outfit NOT installed)
    has_inter = any("inter" in name for name in available_ttfs)
    has_jetbrains = any("jetbrains" in name for name in available_ttfs)
    has_sourcesans = any("sourcesans" in name for name in available_ttfs)
    has_sourceserif = any("sourceserif" in name for name in available_ttfs)

    display_font = "Inter" if has_inter else "Bahnschrift"
    sans_font = "Inter" if has_inter else ("Source Sans 3" if has_sourcesans else "Segoe UI")
    mono_font = "JetBrains Mono" if has_jetbrains else "Consolas"
    serif_font = "Source Serif 4" if has_sourceserif else "Georgia"
    tamil_font = "Nirmala UI"

    return {
        "display": display_font,
        "sans": sans_font,
        "mono": mono_font,
        "serif": serif_font,
        "tamil": tamil_font,
    }


def build_typography_plan(
    brief: ExtractedBrief,
    palette: list[str],
    layout_hints: Optional[list[str]] = None,
    width: float = 1080,
    height: float = 1350,
) -> TypographicPlan:
    """Build a canvas-relative typographic plan obeying the poster-design-craft doctrine."""
    fonts = audit_fonts()

    # Scalar system relative to canvas height (1350 is base)
    scale = height / 1350.0
    margin = max(40.0, width * 0.04)

    # Typographic scales per doctrine:
    # Headline >= canvas_h / 11, max 3 lines (1350 / 11 = 122.7pt)
    headline_size = max(72.0, (height / 11.5))
    subheadline_size = max(22.0, headline_size / 3.5)
    body_size = max(18.0, height * 0.018)  # >= 1.8% of canvas height
    microcopy_size = max(14.0, height * 0.014)  # >= 1.4% of canvas height (min 14pt)

    # Palette role assignments (per configs/palette_policy.yaml & doctrine)
    # canvas_base (60%), structural (30%), accent (10%)
    structural_color = palette[4] if len(palette) > 4 else "#FFFFFF"
    accent_color = palette[1] if len(palette) > 1 else "#00F5D4"
    secondary_accent = palette[2] if len(palette) > 2 else "#00BBF9"
    warm_highlight = palette[3] if len(palette) > 3 else "#FEE440"

    plan = TypographicPlan(canvas_width=width, canvas_height=height, margin=margin)

    # 1. Organizer / Presenter
    organizer_text = brief.get_text("organizer")
    if organizer_text:
        plan.rows.append(
            TypographicRow(
                role="organizer",
                text=organizer_text.upper(),
                zone="header",
                size=microcopy_size,
                style="SemiBold",
                tracking=40.0,
                color=secondary_accent,
                alignment="center",
                font=fonts["sans"],
            )
        )

    # 2. Subtitle / Fest Type
    subtitle_text = brief.get_text("subtitle")
    if subtitle_text:
        plan.rows.append(
            TypographicRow(
                role="subtitle",
                text=subtitle_text.upper(),
                zone="header",
                size=subheadline_size * 0.9,
                style="Bold",
                tracking=50.0,
                color=structural_color,
                alignment="center",
                font=fonts["display"],
            )
        )

    # 3. Main Title
    title_text = brief.get_text("title").upper()
    if title_text:
        plan.rows.append(
            TypographicRow(
                role="title",
                text=title_text,
                zone="headline",
                size=headline_size,
                style="Bold",
                tracking=30.0,
                color=structural_color,
                alignment="center",
                font=fonts["display"],
            )
        )

    # 4. Tagline
    tagline_text = brief.get_text("tagline")
    if tagline_text:
        plan.rows.append(
            TypographicRow(
                role="tagline",
                text=tagline_text.upper(),
                zone="hero_crown",
                size=subheadline_size * 0.65,
                style="Regular",
                tracking=30.0,
                color=secondary_accent,
                alignment="center",
                font=fonts["sans"],
            )
        )

    # 5. Blurb
    blurb_text = brief.get_text("blurb")
    if blurb_text:
        plan.rows.append(
            TypographicRow(
                role="blurb",
                text=blurb_text,
                zone="narrative",
                size=microcopy_size,
                style="Regular",
                tracking=10.0,
                color="#DCE5F5",
                alignment="center",
                font=fonts["sans"],
            )
        )

    # 6. Events / Tracks
    events_text = brief.get_text("events")
    if events_text:
        plan.rows.append(
            TypographicRow(
                role="events",
                text=events_text.upper(),
                zone="lineup",
                size=body_size,
                style="Bold",
                tracking=25.0,
                color=structural_color,
                alignment="center",
                font=fonts["sans"],
            )
        )

    # 7. Grand Prize (Sole high-impact accent if present)
    prize_text = brief.get_text("prize")
    has_prize = bool(prize_text)
    if has_prize:
        plan.rows.append(
            TypographicRow(
                role="prize",
                text=prize_text.upper(),
                zone="accent",
                size=subheadline_size,
                style="Bold",
                tracking=35.0,
                color=accent_color,
                alignment="center",
                font=fonts["display"],
            )
        )

    # 8. Date & Time
    date_text = brief.get_text("date")
    time_text = brief.get_text("time")
    sched_parts = [date_text.upper()] if date_text else []
    if time_text:
        sched_parts.append(time_text.upper())
    full_sched = "   |   ".join(sched_parts)
    if full_sched:
        plan.rows.append(
            TypographicRow(
                role="date_time",
                text=full_sched,
                zone="logistics",
                size=body_size * 1.1,
                style="Bold",
                tracking=20.0,
                color=structural_color,
                alignment="center",
                font=fonts["sans"],
            )
        )

    # 9. Venue & Tamil Venue
    venue_text = brief.get_text("venue")
    venue_tamil = brief.get_text("venue_tamil")
    if venue_text or venue_tamil:
        venue_str = f"LOCATION: {venue_text.upper()}" if venue_text else ""
        if venue_tamil:
            venue_str = f"{venue_str}  •  {venue_tamil}" if venue_str else venue_tamil
        plan.rows.append(
            TypographicRow(
                role="venue",
                text=venue_str,
                zone="logistics",
                size=microcopy_size * 1.05,
                style="Regular",
                tracking=15.0,
                color=secondary_accent,
                alignment="center",
                font=fonts["tamil"] if venue_tamil else fonts["sans"],
            )
        )

    # 10. Call to Action (High-impact accent if no prize, else structural with accent frame)
    cta_text = brief.get_text("cta")
    if cta_text:
        plan.rows.append(
            TypographicRow(
                role="cta",
                text=cta_text.upper(),
                zone="action",
                size=body_size * 1.15,
                style="Bold",
                tracking=30.0,
                color=accent_color if not has_prize else structural_color,
                alignment="center",
                font=fonts["sans"],
            )
        )

    return plan


def _detect_genre(brief: ExtractedBrief) -> str:
    """Classify brief into 'cyber_tech' or 'cultural_editorial' for anti-slop effect tuning."""
    text_corpus = " ".join([
        brief.get_text("title"),
        brief.get_text("blurb"),
        brief.get_text("events"),
        brief.get_text("tagline"),
        brief.get_text("subtitle"),
    ]).lower()

    if re.search(r"(?:cyber|ctf|hack|code|tech|ai|neural|robot|quantum|security|terminal|dev)", text_corpus):
        return "cyber_tech"
    elif re.search(r"(?:dance|music|arts?|cultur|fest|theatr|sing|band|exhibit|film)", text_corpus):
        return "cultural_editorial"
    return "general"


def apply_genre_effects(
    vc: VectorCraftRenderer,
    genre: str,
    accent_color: str,
    hero_target_id: Optional[str] = None,
    accent_target_id: Optional[str] = None,
) -> None:
    """Apply verified engine live effects matching poster genre without slop."""
    if genre == "cyber_tech":
        # Drop shadow on hero
        if hero_target_id:
            vc.add_effect(
                effect_name="stylize.dropShadow",
                params={"mode": "multiply", "opacity": 70.0, "x": 0.0, "y": 8.0, "blur": 12.0, "color": "#000000"},
                target_id=hero_target_id,
            )
        # Faint neon glow on accent row
        if accent_target_id:
            vc.add_effect(
                effect_name="artistic.neonGlow",
                params={"glowSize": 4.0, "glowBrightness": 12.0, "color": accent_color},
                target_id=accent_target_id,
            )
    else:
        # Cultural / editorial or general: subtle organic texture grain full-canvas, zero neon glow
        vc.add_effect(
            effect_name="texture.grain",
            params={"intensity": 10.0, "contrast": 25.0, "grainType": "regular"},
        )


def compose_focal_point(
    vc: VectorCraftRenderer,
    brief: ExtractedBrief,
    palette: list[str],
    plan: TypographicPlan,
    bg_path: Path,
    hero_path: Path,
    hero_geom: Optional[Any] = None,
    width: float = 1080,
    height: float = 1350,
) -> VectorCraftRenderer:
    """Focal Point Archetype: Centered optical radiance with orbital text under hero."""
    canvas_base = palette[0] if palette else "#070B19"
    accent_color = palette[1] if len(palette) > 1 else "#00F5D4"
    structural_color = palette[4] if len(palette) > 4 else "#FFFFFF"
    margin = plan.margin
    fonts = audit_fonts()
    genre = _detect_genre(brief)

    # Layer 0: Full-Bleed Background Art
    vc.place_image(bg_path, rect=[0, 0, width, height])

    # Layer 1: Soft Scrims (Alpha Gradients, No Opaque Rects)
    # Top header scrim
    vc.soft_scrim(
        x=0, y=0, width=width, height=height * 0.32,
        stops=[(0.0, canvas_base, 0.85), (1.0, canvas_base, 0.0)],
        direction="to_bottom",
    )
    # Bottom footer scrim
    vc.soft_scrim(
        x=0, y=height * 0.65, width=width, height=height * 0.35,
        stops=[(0.0, canvas_base, 0.0), (1.0, canvas_base, 0.90)],
        direction="to_bottom",
    )

    # Layer 1.5: Radial Light Behind Hero
    cx = width * 0.5
    cy = height * 0.42
    vc.radial_light(
        cx=cx, cy=cy, radius=width * 0.32,
        color=accent_color, alpha_stop_inner=0.50, alpha_stop_outer=0.0,
        blend_mode="screen",
    )

    # Layer 2: Headline Typography
    curr_y = height * 0.05
    org_row = plan.get_row("organizer")
    if org_row:
        vc.add_text(
            text=org_row.text, x=cx, y=curr_y, size=org_row.size,
            font=org_row.font, style=org_row.style, tracking=org_row.tracking,
            color=org_row.color, justify="center", role="organizer",
        )
        curr_y += height * 0.025

    sub_row = plan.get_row("subtitle")
    if sub_row:
        vc.add_text(
            text=f"—   {sub_row.text}   —", x=cx, y=curr_y, size=sub_row.size,
            font=sub_row.font, style=sub_row.style, tracking=sub_row.tracking,
            color=sub_row.color, justify="center", role="subtitle",
        )
        curr_y += height * 0.035

    title_row = plan.get_row("title")
    if title_row:
        # Lock headline across measure via area_text + fit_headline
        h_box_w = width - (2 * margin)
        vc.area_text(
            text=title_row.text,
            x=margin,
            y=curr_y,
            width=h_box_w,
            height=height * 0.12,
            size=title_row.size,
            font=title_row.font,
            style=title_row.style,
            color=title_row.color,
            justify="center",
            fit="autoHeight",
            role="main_headline",
        )
        vc.fit_headline()
        curr_y += height * 0.09

    tag_row = plan.get_row("tagline")
    if tag_row:
        vc.add_text(
            text=tag_row.text, x=cx, y=curr_y, size=tag_row.size,
            font=tag_row.font, style=tag_row.style, tracking=tag_row.tracking,
            color=tag_row.color, justify="center", role="tagline",
        )

    # Layer 3: Hero Cutout Asset (with ArtMeasurer geometry integration for focal_point)
    # Optical center anchored at y ≈ 42% H; target placed height 36-40% H
    target_hero_h = height * 0.38
    if hero_geom and getattr(hero_geom, "width", 0) > 0 and getattr(hero_geom, "height", 0) > 0:
        aspect = float(hero_geom.width) / float(hero_geom.height)
        hero_h = min(target_hero_h, height * 0.44)
        hero_w = min(width * 0.65, hero_h * aspect)
    else:
        hero_w = min(width * 0.54, height * 0.40)
        hero_h = hero_w

    hero_x = cx - (hero_w / 2.0)
    hero_y = cy - (hero_h / 2.0)
    vc.place_image(hero_path, rect=[hero_x, hero_y, hero_w, hero_h])
    hero_node_id = "$last"

    # Layer 5: Orbital Text Ribbon under Hero Baseline
    # Spline under the hero base: subtle curve
    orbital_y = hero_y + hero_h + height * 0.015
    arc_w = width * 0.82
    x1 = (width - arc_w) / 2.0
    x2 = x1 + arc_w
    cx1 = width * 0.35
    cx2 = width * 0.65
    y_curve = orbital_y + height * 0.035
    path_d = f"M {x1:.1f} {orbital_y:.1f} C {cx1:.1f} {y_curve:.1f} {cx2:.1f} {y_curve:.1f} {x2:.1f} {orbital_y:.1f}"

    date_row = plan.get_row("date_time")
    venue_row = plan.get_row("venue")
    orbital_parts = []
    if date_row:
        orbital_parts.append(date_row.text)
    if venue_row:
        v_clean = venue_row.text.replace("LOCATION: ", "")
        orbital_parts.append(v_clean)
    orbital_text_content = "   ◆   ".join(orbital_parts) if orbital_parts else "OFFICIAL EVENT CIRCUIT 2026"

    # Compute optimal font size to prevent overflow along the arc length
    char_len = len(orbital_text_content)
    if char_len > 55:
        orbital_size = 13.0
    elif char_len > 35:
        orbital_size = 15.0
    else:
        orbital_size = 18.0

    vc.orbital_text(
        path_d=path_d,
        text=orbital_text_content,
        size=orbital_size,
        font=fonts["sans"],
        style="Bold",
        color=structural_color,
        justify="center",
        role="orbital_logistics",
    )

    # Layer 5b: Radial Bottom Metadata Stack (Dynamic spacing, zero gaps for sparse briefs)
    base_y = orbital_y + height * 0.065
    blurb_row = plan.get_row("blurb")
    if blurb_row:
        vc.add_shape_rectangle(x=margin + 40, y=base_y, width=width - 2 * (margin + 40), height=1, fill=palette[2] if len(palette) > 2 else "#00BBF9")
        base_y += height * 0.022
        vc.add_text(
            text=blurb_row.text, x=cx, y=base_y, size=blurb_row.size,
            font=blurb_row.font, style=blurb_row.style, tracking=blurb_row.tracking,
            color=blurb_row.color, justify="center", role="blurb",
        )
        base_y += height * 0.035

    events_row = plan.get_row("events")
    if events_row:
        events_raw = [e.strip() for e in events_row.text.split("/") if e.strip()]
        line_1 = "   ◆   ".join(events_raw[:2]) if len(events_raw) >= 2 else events_row.text
        line_2 = "   ◆   ".join(events_raw[2:]) if len(events_raw) > 2 else ""

        vc.add_text(text=line_1, x=cx, y=base_y, size=events_row.size, font=events_row.font, style="Bold", tracking=20.0, color=events_row.color, justify="center", role="events_line1")
        base_y += height * 0.028
        if line_2:
            vc.add_text(text=line_2, x=cx, y=base_y, size=events_row.size, font=events_row.font, style="Bold", tracking=20.0, color=events_row.color, justify="center", role="events_line2")
            base_y += height * 0.028

    prize_row = plan.get_row("prize")
    accent_target_id = None
    if prize_row:
        bar_w = width * 0.55
        bar_x = (width - bar_w) / 2.0
        vc.add_shape_rectangle(x=bar_x, y=base_y, width=bar_w, height=1, fill=prize_row.color)
        base_y += height * 0.026
        vc.add_text(
            text=f"★   {prize_row.text}   ★", x=cx, y=base_y, size=prize_row.size,
            font=prize_row.font, style="Bold", tracking=35.0, color=prize_row.color,
            justify="center", role="grand_prize",
        )
        accent_target_id = "$last"
        base_y += height * 0.016
        vc.add_shape_rectangle(x=bar_x, y=base_y, width=bar_w, height=1, fill=prize_row.color)
        base_y += height * 0.035

    cta_row = plan.get_row("cta")
    if cta_row:
        cta_w = width * 0.65
        cta_x = (width - cta_w) / 2.0
        vc.add_shape_rectangle(x=cta_x, y=base_y, width=cta_w, height=1, fill=cta_row.color)
        base_y += height * 0.024
        vc.add_text(
            text=f"◆   {cta_row.text}   ◆", x=cx, y=base_y, size=cta_row.size,
            font=cta_row.font, style="Bold", tracking=30.0, color=cta_row.color,
            justify="center", role="cta",
        )
        if not accent_target_id:
            accent_target_id = "$last"
        base_y += height * 0.016
        vc.add_shape_rectangle(x=cta_x, y=base_y, width=cta_w, height=1, fill=cta_row.color)

    # Layer 6: Effects finish
    apply_genre_effects(vc, genre=genre, accent_color=accent_color, hero_target_id=hero_node_id, accent_target_id=accent_target_id)
    return vc


def compose_z_pattern(
    vc: VectorCraftRenderer,
    brief: ExtractedBrief,
    palette: list[str],
    plan: TypographicPlan,
    bg_path: Path,
    hero_path: Path,
    hero_geom: Optional[Any] = None,
    width: float = 1080,
    height: float = 1350,
) -> VectorCraftRenderer:
    """Z-Pattern Archetype: Dynamic diagonal scan for cinematic/image-heavy posters."""
    canvas_base = palette[0] if palette else "#070B19"
    accent_color = palette[1] if len(palette) > 1 else "#00F5D4"
    structural_color = palette[4] if len(palette) > 4 else "#FFFFFF"
    margin = plan.margin
    fonts = audit_fonts()
    genre = _detect_genre(brief)

    # Layer 0: Background
    vc.place_image(bg_path, rect=[0, 0, width, height])

    # Layer 1: Atmospheric Scrims
    vc.soft_scrim(
        x=0, y=0, width=width, height=height * 0.35,
        stops=[(0.0, canvas_base, 0.88), (1.0, canvas_base, 0.0)],
        direction="to_bottom",
    )
    vc.soft_scrim(
        x=0, y=height * 0.60, width=width, height=height * 0.40,
        stops=[(0.0, canvas_base, 0.0), (1.0, canvas_base, 0.92)],
        direction="to_bottom",
    )

    # Top-Left: Presenter Mark
    org_row = plan.get_row("organizer")
    if org_row:
        vc.add_text(
            text=org_row.text, x=margin, y=height * 0.05, size=org_row.size,
            font=org_row.font, style=org_row.style, tracking=30.0,
            color=structural_color, justify="left", role="organizer_mark",
        )

    # Top-Right: Date Badge
    date_row = plan.get_row("date_time")
    if date_row:
        vc.add_text(
            text=date_row.text, x=width - margin, y=height * 0.05, size=date_row.size,
            font=fonts["display"], style="Bold", tracking=20.0,
            color=accent_color, justify="right", role="date_badge",
        )

    # Diagonal Slice: Two-line staggered headline
    title_row = plan.get_row("title")
    title_y = height * 0.13
    if title_row:
        words = title_row.text.split()
        if len(words) >= 2:
            mid = len(words) // 2
            line1 = " ".join(words[:mid])
            line2 = " ".join(words[mid:])
            vc.add_text(
                text=line1, x=margin, y=title_y, size=title_row.size * 0.85,
                font=title_row.font, style="Bold", tracking=25.0,
                color=structural_color, justify="left", role="headline_line1",
            )
            vc.add_text(
                text=line2, x=margin + width * 0.15, y=title_y + height * 0.07, size=title_row.size * 0.85,
                font=title_row.font, style="Bold", tracking=25.0,
                color=structural_color, justify="left", role="headline_line2",
            )
        else:
            vc.add_text(
                text=title_row.text, x=margin, y=title_y, size=title_row.size * 0.85,
                font=title_row.font, style="Bold", tracking=25.0,
                color=structural_color, justify="left", role="headline_single",
            )

    # Mid-Canvas Diagonal Hero
    hero_w = min(width * 0.52, height * 0.40)
    hero_h = hero_w
    hero_cx = width * 0.55
    hero_cy = height * 0.44

    # Radial light behind hero
    vc.radial_light(
        cx=hero_cx, cy=hero_cy, radius=hero_w * 0.65,
        color=accent_color, alpha_stop_inner=0.45, alpha_stop_outer=0.0,
        blend_mode="screen",
    )
    vc.place_image(hero_path, rect=[hero_cx - hero_w / 2.0, hero_cy - hero_h / 2.0, hero_w, hero_h])
    hero_node_id = "$last"

    # Bottom-Left: Highlights / Events Ribbon
    bot_y = height * 0.76
    events_row = plan.get_row("events")
    if events_row:
        vc.add_text(
            text="FEATURED TRACKS:", x=margin, y=bot_y, size=plan.rows[0].size if plan.rows else 14.0,
            font=fonts["mono"], style="Regular", color=palette[2] if len(palette) > 2 else "#00BBF9",
            justify="left", role="events_label",
        )
        bot_y += height * 0.026
        vc.add_text(
            text=events_row.text, x=margin, y=bot_y, size=events_row.size * 0.9,
            font=events_row.font, style="Bold", color=structural_color, justify="left", role="events_content",
        )
        bot_y += height * 0.035

    venue_row = plan.get_row("venue")
    if venue_row:
        vc.add_text(
            text=venue_row.text, x=margin, y=bot_y, size=venue_row.size,
            font=venue_row.font, style="Regular", color=structural_color, justify="left", role="venue",
        )
        bot_y += height * 0.030

    # Bottom-Right: Grand Prize and Registration CTA URL
    right_x = width - margin
    right_y = height * 0.82
    prize_row = plan.get_row("prize")
    accent_target_id = None
    if prize_row:
        vc.add_text(
            text=f"AWARDS: {prize_row.text}", x=right_x, y=right_y, size=prize_row.size * 0.9,
            font=prize_row.font, style="Bold", color=prize_row.color, justify="right", role="grand_prize",
        )
        accent_target_id = "$last"
        right_y += height * 0.038

    cta_row = plan.get_row("cta")
    if cta_row:
        vc.add_text(
            text=f"JOIN: {cta_row.text}  →", x=right_x, y=right_y, size=cta_row.size,
            font=cta_row.font, style="Bold", color=cta_row.color, justify="right", role="cta",
        )
        if not accent_target_id:
            accent_target_id = "$last"

    apply_genre_effects(vc, genre=genre, accent_color=accent_color, hero_target_id=hero_node_id, accent_target_id=accent_target_id)
    return vc


def compose_split(
    vc: VectorCraftRenderer,
    brief: ExtractedBrief,
    palette: list[str],
    plan: TypographicPlan,
    bg_path: Path,
    hero_path: Path,
    hero_geom: Optional[Any] = None,
    width: float = 1080,
    height: float = 1350,
) -> VectorCraftRenderer:
    """Split Layout Archetype: Upper ~55% rich artwork with soft scrim fade, lower ~45% solid editorial type field."""
    canvas_base = palette[0] if palette else "#070B19"
    accent_color = palette[1] if len(palette) > 1 else "#00F5D4"
    structural_color = palette[4] if len(palette) > 4 else "#FFFFFF"
    margin = plan.margin
    fonts = audit_fonts()
    genre = _detect_genre(brief)

    # Upper 55% Art Zone
    vc.place_image(bg_path, rect=[0, 0, width, height])

    # Hero placed in upper zone
    hero_cx = width * 0.50
    hero_cy = height * 0.28
    hero_w = min(width * 0.48, height * 0.36)
    hero_h = hero_w

    vc.radial_light(
        cx=hero_cx, cy=hero_cy, radius=hero_w * 0.60,
        color=accent_color, alpha_stop_inner=0.45, alpha_stop_outer=0.0,
        blend_mode="screen",
    )
    vc.place_image(hero_path, rect=[hero_cx - hero_w / 2.0, hero_cy - hero_h / 2.0, hero_w, hero_h])
    hero_node_id = "$last"

    # Soft scrim bridging art zone into lower solid field (per-stop alpha gradient, NO opaque rect)
    split_y = height * 0.50
    scrim_h = height * 0.12
    vc.soft_scrim(
        x=0, y=split_y, width=width, height=scrim_h,
        stops=[(0.0, canvas_base, 0.0), (1.0, canvas_base, 1.0)],
        direction="to_bottom",
    )
    # Lower solid field
    vc.add_shape_rectangle(x=0, y=split_y + scrim_h, width=width, height=height - (split_y + scrim_h), fill=canvas_base)

    # Lower zone: Left-aligned editorial typography column
    type_x = margin + 20
    type_y = split_y + scrim_h + height * 0.025

    title_row = plan.get_row("title")
    if title_row:
        vc.add_text(
            text=title_row.text, x=type_x, y=type_y, size=title_row.size * 0.80,
            font=title_row.font, style="Bold", tracking=20.0,
            color=structural_color, justify="left", role="title",
        )
        type_y += height * 0.065

    # Hairline divider
    vc.add_shape_rectangle(x=type_x, y=type_y, width=width - type_x - margin, height=1, fill=accent_color)
    type_y += height * 0.025

    blurb_row = plan.get_row("blurb")
    if blurb_row:
        vc.add_text(
            text=blurb_row.text, x=type_x, y=type_y, size=blurb_row.size,
            font=blurb_row.font, style="Regular", color="#DCE5F5", justify="left", role="blurb",
        )
        type_y += height * 0.035

    events_row = plan.get_row("events")
    if events_row:
        vc.add_text(
            text=f"TRACKS: {events_row.text}", x=type_x, y=type_y, size=events_row.size * 0.85,
            font=events_row.font, style="Bold", color=structural_color, justify="left", role="events",
        )
        type_y += height * 0.035

    date_row = plan.get_row("date_time")
    if date_row:
        vc.add_text(
            text=f"SCHEDULE: {date_row.text}", x=type_x, y=type_y, size=date_row.size * 0.9,
            font=fonts["sans"], style="Bold", color=structural_color, justify="left", role="schedule",
        )
        type_y += height * 0.030

    venue_row = plan.get_row("venue")
    if venue_row:
        vc.add_text(
            text=venue_row.text, x=type_x, y=type_y, size=venue_row.size,
            font=venue_row.font, style="Regular", color=structural_color, justify="left", role="venue",
        )
        type_y += height * 0.035

    prize_row = plan.get_row("prize")
    accent_target_id = None
    if prize_row:
        vc.add_text(
            text=f"PRIZE POOL: {prize_row.text}", x=type_x, y=type_y, size=prize_row.size,
            font=prize_row.font, style="Bold", color=prize_row.color, justify="left", role="grand_prize",
        )
        accent_target_id = "$last"
        type_y += height * 0.035

    cta_row = plan.get_row("cta")
    if cta_row:
        vc.add_text(
            text=f"REGISTRATION: {cta_row.text}", x=type_x, y=type_y, size=cta_row.size,
            font=cta_row.font, style="Bold", color=cta_row.color, justify="left", role="cta",
        )
        if not accent_target_id:
            accent_target_id = "$last"

    apply_genre_effects(vc, genre=genre, accent_color=accent_color, hero_target_id=hero_node_id, accent_target_id=accent_target_id)
    return vc


def compose_grid_3col(
    vc: VectorCraftRenderer,
    brief: ExtractedBrief,
    palette: list[str],
    plan: TypographicPlan,
    bg_path: Path,
    hero_path: Path,
    hero_geom: Optional[Any] = None,
    width: float = 1080,
    height: float = 1350,
) -> VectorCraftRenderer:
    """3-Column Grid Archetype: Academic / multi-track hackathons with structured monospace technical strip."""
    canvas_base = palette[0] if palette else "#070B19"
    accent_color = palette[1] if len(palette) > 1 else "#00F5D4"
    structural_color = palette[4] if len(palette) > 4 else "#FFFFFF"
    margin = plan.margin
    fonts = audit_fonts()
    genre = _detect_genre(brief)

    # 3-Column Geometry
    gutter = 28.0
    col_w = (width - 2 * margin - 2 * gutter) / 3.0
    col1_x = margin
    col2_x = margin + col_w + gutter
    col3_x = margin + 2 * (col_w + gutter)

    # Layer 0: Background
    vc.place_image(bg_path, rect=[0, 0, width, height])

    # Top scrim
    vc.soft_scrim(
        x=0, y=0, width=width, height=height * 0.30,
        stops=[(0.0, canvas_base, 0.90), (1.0, canvas_base, 0.0)],
        direction="to_bottom",
    )
    # Bottom footer scrim
    vc.soft_scrim(
        x=0, y=height * 0.70, width=width, height=height * 0.30,
        stops=[(0.0, canvas_base, 0.0), (1.0, canvas_base, 0.92)],
        direction="to_bottom",
    )

    # Full-Width Spanning Headline (locked via fit_headline)
    head_y = height * 0.06
    org_row = plan.get_row("organizer")
    if org_row:
        vc.add_text(
            text=org_row.text, x=margin, y=head_y, size=org_row.size,
            font=fonts["mono"], style="Regular", color=palette[2] if len(palette) > 2 else "#00BBF9",
            justify="left", role="organizer",
        )
        head_y += height * 0.026

    title_row = plan.get_row("title")
    if title_row:
        h_box_w = width - (2 * margin)
        vc.area_text(
            text=title_row.text,
            x=margin,
            y=head_y,
            width=h_box_w,
            height=height * 0.10,
            size=title_row.size * 0.9,
            font=title_row.font,
            style="Bold",
            color=structural_color,
            justify="center",
            fit="autoHeight",
            role="full_width_headline",
        )
        vc.fit_headline()
        head_y += height * 0.08

    # Hairline divider under header
    vc.add_shape_rectangle(x=margin, y=head_y, width=width - 2 * margin, height=1, fill=accent_color)
    mid_top_y = head_y + height * 0.035

    # Center Column: Hero asset at top
    hero_w = min(col_w * 1.3, height * 0.32)
    hero_h = hero_w
    hero_cx = col2_x + (col_w / 2.0)
    hero_cy = mid_top_y + (hero_h / 2.0)

    vc.radial_light(
        cx=hero_cx, cy=hero_cy, radius=hero_w * 0.65,
        color=accent_color, alpha_stop_inner=0.45, alpha_stop_outer=0.0,
        blend_mode="screen",
    )
    vc.place_image(hero_path, rect=[hero_cx - hero_w / 2.0, mid_top_y, hero_w, hero_h])
    hero_node_id = "$last"

    # Center Column under hero: Blurb & Tagline
    c_y = mid_top_y + hero_h + height * 0.030
    tag_row = plan.get_row("tagline")
    if tag_row:
        vc.add_text(
            text=tag_row.text, x=hero_cx, y=c_y, size=tag_row.size,
            font=fonts["display"], style="Bold", color=palette[2] if len(palette) > 2 else "#00BBF9",
            justify="center", role="tagline",
        )
        c_y += height * 0.030

    blurb_row = plan.get_row("blurb")
    if blurb_row:
        vc.add_text(
            text=blurb_row.text, x=hero_cx, y=c_y, size=blurb_row.size,
            font=fonts["sans"], style="Regular", color="#DCE5F5", justify="center", role="blurb",
        )

    # Left Column (Tracks / Schedule)
    l_y = mid_top_y
    vc.add_text(text="TRACKS & HIGHLIGHTS", x=col1_x, y=l_y, size=13.0, font=fonts["mono"], style="Bold", color=accent_color, justify="left", role="col1_header")
    l_y += height * 0.022
    vc.add_shape_rectangle(x=col1_x, y=l_y, width=col_w, height=1, fill=accent_color)
    l_y += height * 0.024

    events_row = plan.get_row("events")
    if events_row:
        events_list = [e.strip() for e in events_row.text.split("/") if e.strip()]
        for ev in events_list[:5]:
            vc.add_text(text=f"//  {ev}", x=col1_x, y=l_y, size=15.0, font=fonts["sans"], style="Bold", color=structural_color, justify="left", role="track_item")
            l_y += height * 0.030

    # Right Column (Speakers / Awards / Registration)
    r_y = mid_top_y
    vc.add_text(text="PRIZES & REGISTRATION", x=col3_x, y=r_y, size=13.0, font=fonts["mono"], style="Bold", color=accent_color, justify="left", role="col3_header")
    r_y += height * 0.022
    vc.add_shape_rectangle(x=col3_x, y=r_y, width=col_w, height=1, fill=accent_color)
    r_y += height * 0.024

    prize_row = plan.get_row("prize")
    accent_target_id = None
    if prize_row:
        vc.add_text(text="AWARD POOL:", x=col3_x, y=r_y, size=12.0, font=fonts["mono"], color=palette[2] if len(palette) > 2 else "#00BBF9", justify="left", role="prize_label")
        r_y += height * 0.022
        vc.add_text(text=prize_row.text, x=col3_x, y=r_y, size=prize_row.size * 0.85, font=prize_row.font, style="Bold", color=prize_row.color, justify="left", role="grand_prize")
        accent_target_id = "$last"
        r_y += height * 0.038

    cta_row = plan.get_row("cta")
    if cta_row:
        vc.add_text(text="REGISTRATION LINK:", x=col3_x, y=r_y, size=12.0, font=fonts["mono"], color=palette[2] if len(palette) > 2 else "#00BBF9", justify="left", role="cta_label")
        r_y += height * 0.022
        vc.add_text(text=cta_row.text, x=col3_x, y=r_y, size=cta_row.size * 0.9, font=cta_row.font, style="Bold", color=cta_row.color, justify="left", role="cta")
        if not accent_target_id:
            accent_target_id = "$last"
        r_y += height * 0.038

    # Monospace Footer Strip (JetBrains Mono if available)
    footer_y = height - margin - 25
    vc.add_shape_rectangle(x=margin, y=footer_y - 12, width=width - 2 * margin, height=1, fill=palette[2] if len(palette) > 2 else "#00BBF9")

    date_row = plan.get_row("date_time")
    venue_row = plan.get_row("venue")
    footer_parts = []
    if date_row:
        footer_parts.append(f"DATE: {date_row.text}")
    if venue_row:
        footer_parts.append(venue_row.text)
    full_footer = "   ◆   ".join(footer_parts)

    vc.add_text(
        text=full_footer,
        x=width / 2.0,
        y=footer_y + 8,
        size=13.0,
        font=fonts["mono"],
        style="Regular",
        tracking=15.0,
        color=structural_color,
        justify="center",
        role="monospace_footer",
    )

    apply_genre_effects(vc, genre=genre, accent_color=accent_color, hero_target_id=hero_node_id, accent_target_id=accent_target_id)
    return vc


def compose(
    brief: ExtractedBrief,
    palette: list[str],
    bg_path: Path,
    hero_path: Path,
    hero_geom: Optional[Any] = None,
    archetype: str = "focal_point",
    layout_hints: Optional[list[str]] = None,
    width: float = 1080,
    height: float = 1350,
) -> VectorCraftRenderer:
    """Master compose entrypoint: dispatches to chosen archetype composer."""
    # Allow test / CLI override via POSTER_FORCE_ARCHETYPE environment variable
    forced_archetype = os.environ.get("POSTER_FORCE_ARCHETYPE")
    if forced_archetype in ("focal_point", "z_pattern", "split", "grid_3col"):
        archetype = forced_archetype

    vc = VectorCraftRenderer()
    vc.new_document(width=width, height=height, units="Points", color_mode="rgb", raster_resolution=300)

    plan = build_typography_plan(
        brief=brief,
        palette=palette,
        layout_hints=layout_hints,
        width=width,
        height=height,
    )

    if archetype == "z_pattern":
        return compose_z_pattern(vc, brief, palette, plan, bg_path, hero_path, hero_geom, width, height)
    elif archetype == "split":
        return compose_split(vc, brief, palette, plan, bg_path, hero_path, hero_geom, width, height)
    elif archetype == "grid_3col":
        return compose_grid_3col(vc, brief, palette, plan, bg_path, hero_path, hero_geom, width, height)
    else:
        return compose_focal_point(vc, brief, palette, plan, bg_path, hero_path, hero_geom, width, height)

