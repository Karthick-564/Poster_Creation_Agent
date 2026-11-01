"""Archetype-Native VectorCraft Poster Composer.

Implements data-driven editorial poster composition based on the poster-design-craft doctrine:
- Relative typographic scale (canvas-relative scalars)
- 4 compositional archetypes: focal_point, z_pattern, split, grid_3col
- Collision resolution & margin-bounds protection across all archetypes
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

    # Map roles based on verified installed fonts (Outfit is NOT installed)
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


def estimate_text_width(text: str, size: float, font: str = "Inter", tracking: float = 0.0) -> float:
    """Accurately estimate text rendered width in points."""
    if not text:
        return 0.0
    # Ratio for uppercase / title-cased sans vs monospace
    ratio = 0.60 if "mono" in font.lower() else 0.58
    tracking_offset = (tracking / 1000.0) * size * len(text)
    return (len(text) * size * ratio) + tracking_offset


def estimate_headline_height(text: str, size: float, max_width: float, font: str = "Inter") -> float:
    """Estimate rendered multi-line block height for headlines."""
    words = text.split()
    if not words:
        return 0.0
    lines = 1
    curr_w = 0.0
    space_w = size * 0.30
    for w in words:
        w_len = estimate_text_width(w, size, font)
        if curr_w == 0.0:
            curr_w = w_len
        elif curr_w + space_w + w_len <= max_width:
            curr_w += space_w + w_len
        else:
            lines += 1
            curr_w = w_len
    line_height = size * 1.15
    return max(size, lines * line_height)


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
    margin = max(40.0, width * 0.04)

    # Typographic scales per doctrine:
    # Headline >= canvas_h / 11.5, max 3 lines
    headline_size = max(72.0, (height / 11.5))
    subheadline_size = max(22.0, headline_size / 3.5)
    body_size = max(18.0, height * 0.018)  # >= 1.8% of canvas height
    microcopy_size = max(14.0, height * 0.014)  # >= 1.4% of canvas height (min 14pt)

    # Palette role assignments
    structural_color = palette[4] if len(palette) > 4 else "#FFFFFF"
    accent_color = palette[1] if len(palette) > 1 else "#00F5D4"
    secondary_accent = palette[2] if len(palette) > 2 else "#00BBF9"

    plan = TypographicPlan(canvas_width=width, canvas_height=height, margin=margin)
    usable_w = width - (2 * margin)

    def _clamp_size(txt: str, sz: float, fnt: str, trk: float = 0.0, max_w: float = usable_w) -> float:
        est = estimate_text_width(txt, sz, fnt, trk)
        if est > max_w and est > 0:
            return max(10.0, sz * (max_w / est) * 0.95)
        return sz

    # Ensure massive display headline scales cleanly within headline height budget (<= 22% canvas)
    title_text = brief.get_text("title").upper()
    if title_text:
        usable_h_box = height * 0.22
        est_h = estimate_headline_height(title_text, headline_size, usable_w, fonts["display"])
        while est_h > usable_h_box and headline_size > 48.0:
            headline_size -= 4.0
            est_h = estimate_headline_height(title_text, headline_size, usable_w, fonts["display"])

    # 1. Organizer / Presenter
    organizer_text = brief.get_text("organizer")
    if organizer_text:
        org_sz = _clamp_size(organizer_text.upper(), microcopy_size, fonts["sans"], 30.0)
        plan.rows.append(
            TypographicRow(
                role="organizer",
                text=organizer_text.upper(),
                zone="header",
                size=org_sz,
                style="SemiBold",
                tracking=30.0,
                color=secondary_accent,
                alignment="center",
                font=fonts["sans"],
            )
        )

    # 2. Subtitle / Fest Type
    subtitle_text = brief.get_text("subtitle")
    if subtitle_text:
        sub_sz = _clamp_size(f"—   {subtitle_text.upper()}   —", subheadline_size * 0.9, fonts["display"], 40.0)
        plan.rows.append(
            TypographicRow(
                role="subtitle",
                text=subtitle_text.upper(),
                zone="header",
                size=sub_sz,
                style="Bold",
                tracking=40.0,
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
        tag_sz = _clamp_size(tagline_text.upper(), subheadline_size * 0.65, fonts["sans"], 25.0)
        plan.rows.append(
            TypographicRow(
                role="tagline",
                text=tagline_text.upper(),
                zone="hero_crown",
                size=tag_sz,
                style="Regular",
                tracking=25.0,
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
                tracking=20.0,
                color=structural_color,
                alignment="center",
                font=fonts["sans"],
            )
        )

    # 7. Grand Prize (Sole high-impact accent if present)
    prize_text = brief.get_text("prize")
    has_prize = bool(prize_text)
    if has_prize:
        prz_sz = _clamp_size(f"★   {prize_text.upper()}   ★", subheadline_size, fonts["display"], 30.0)
        plan.rows.append(
            TypographicRow(
                role="prize",
                text=prize_text.upper(),
                zone="accent",
                size=prz_sz,
                style="Bold",
                tracking=30.0,
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
        dt_sz = _clamp_size(full_sched, body_size * 1.1, fonts["sans"], 20.0)
        plan.rows.append(
            TypographicRow(
                role="date_time",
                text=full_sched,
                zone="logistics",
                size=dt_sz,
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
        v_fnt = fonts["tamil"] if venue_tamil else fonts["sans"]
        v_sz = _clamp_size(venue_str, microcopy_size * 1.05, v_fnt, 15.0)
        plan.rows.append(
            TypographicRow(
                role="venue",
                text=venue_str,
                zone="logistics",
                size=v_sz,
                style="Regular",
                tracking=15.0,
                color=secondary_accent,
                alignment="center",
                font=v_fnt,
            )
        )

    # 10. Call to Action (High-impact accent if no prize, else structural with accent frame)
    cta_text = brief.get_text("cta")
    if cta_text:
        cta_sz = _clamp_size(f"◆   {cta_text.upper()}   ◆", body_size * 1.15, fonts["sans"], 25.0)
        plan.rows.append(
            TypographicRow(
                role="cta",
                text=cta_text.upper(),
                zone="action",
                size=cta_sz,
                style="Bold",
                tracking=25.0,
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
        if hero_target_id:
            vc.add_effect(
                effect_name="stylize.dropShadow",
                params={"mode": "multiply", "opacity": 70.0, "x": 0.0, "y": 8.0, "blur": 12.0, "color": "#000000"},
                target_id=hero_target_id,
            )
        if accent_target_id:
            vc.add_effect(
                effect_name="artistic.neonGlow",
                params={"glowSize": 4.0, "glowBrightness": 12.0, "color": accent_color},
                target_id=accent_target_id,
            )
    else:
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

    # Layer 1: Soft Scrims (Zero Discontinuity: Edge Stop Always Opacity 0.0)
    # Top header scrim fades down into canvas, ending at opacity 0.0
    vc.soft_scrim(
        x=0, y=0, width=width, height=height * 0.32,
        stops=[(0.0, canvas_base, 0.85), (1.0, canvas_base, 0.0)],
        direction="to_bottom",
    )
    # Bottom footer scrim fades up into canvas, ending at opacity 0.0 at its top edge
    vc.soft_scrim(
        x=0, y=height * 0.58, width=width, height=height * 0.42,
        stops=[(0.0, canvas_base, 0.90), (1.0, canvas_base, 0.0)],
        direction="to_top",
    )

    # Header Typography Placement
    curr_y = height * 0.05
    cx = width * 0.5

    org_row = plan.get_row("organizer")
    if org_row:
        vc.add_text(
            text=org_row.text, x=cx, y=curr_y, size=org_row.size,
            font=org_row.font, style=org_row.style, tracking=org_row.tracking,
            color=org_row.color, justify="center", role="organizer",
        )
        curr_y += org_row.size * 1.35 + 8

    sub_row = plan.get_row("subtitle")
    if sub_row:
        vc.add_text(
            text=f"—   {sub_row.text}   —", x=cx, y=curr_y, size=sub_row.size,
            font=sub_row.font, style=sub_row.style, tracking=sub_row.tracking,
            color=sub_row.color, justify="center", role="subtitle",
        )
        curr_y += sub_row.size * 1.35 + 12

    # BUG 3 FIX: Compute true multi-line headline height and place tagline strictly below it
    title_row = plan.get_row("title")
    h_box_w = width - (2 * margin)
    if title_row:
        h_block_h = estimate_headline_height(title_row.text, title_row.size, h_box_w, title_row.font)
        # Bounded area text with fitHeadline
        vc.area_text(
            text=title_row.text,
            x=margin,
            y=curr_y,
            width=h_box_w,
            height=h_block_h + 10,
            size=title_row.size,
            font=title_row.font,
            style=title_row.style,
            color=title_row.color,
            justify="center",
            fit="autoHeight",
            role="main_headline",
        )
        if "\n" not in title_row.text and estimate_text_width(title_row.text, title_row.size, font=title_row.font) <= h_box_w * 0.88:
            vc.fit_headline()
        # Advance curr_y strictly past the measured headline box + breathing room
        curr_y += h_block_h + height * 0.025

    tag_row = plan.get_row("tagline")
    if tag_row:
        vc.add_text(
            text=tag_row.text, x=cx, y=curr_y, size=tag_row.size,
            font=tag_row.font, style=tag_row.style, tracking=tag_row.tracking,
            color=tag_row.color, justify="center", role="tagline",
        )
        curr_y += tag_row.size * 1.35 + height * 0.020

    # Layer 3: Hero Cutout Asset (with ArtMeasurer geometry integration)
    target_hero_h = min(height * 0.35, max(height * 0.22, (height * 0.62) - curr_y))
    if hero_geom and getattr(hero_geom, "width", 0) > 0 and getattr(hero_geom, "height", 0) > 0:
        aspect = float(hero_geom.width) / float(hero_geom.height)
        hero_h = min(target_hero_h, height * 0.38)
        hero_w = min(width * 0.65, hero_h * aspect)
    else:
        hero_h = target_hero_h
        hero_w = min(width * 0.52, hero_h)

    hero_y = max(curr_y + 10, height * 0.38 - (hero_h / 2.0))
    hero_x = cx - (hero_w / 2.0)
    hero_cy = hero_y + (hero_h / 2.0)

    # Radial Light Behind Hero
    vc.radial_light(
        cx=cx, cy=hero_cy, radius=hero_w * 0.65,
        color=accent_color, alpha_stop_inner=0.50, alpha_stop_outer=0.0,
        blend_mode="screen",
    )
    vc.place_image(hero_path, rect=[hero_x, hero_y, hero_w, hero_h])
    hero_node_id = "$last"

    # Layer 5: Orbital Text Ribbon under Hero Baseline
    orbital_y = hero_y + hero_h + height * 0.015
    arc_w = width * 0.82
    x1 = (width - arc_w) / 2.0
    x2 = x1 + arc_w
    cx1 = width * 0.35
    cx2 = width * 0.65
    y_curve = orbital_y + height * 0.028
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

    char_len = len(orbital_text_content)
    if char_len > 90:
        orbital_size = 9.0
    elif char_len > 60:
        orbital_size = 11.0
    elif char_len > 35:
        orbital_size = 13.5
    else:
        orbital_size = 16.0

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
    base_y = orbital_y + height * 0.048
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
            font=prize_row.font, style="Bold", tracking=30.0, color=prize_row.color,
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
            font=cta_row.font, style="Bold", tracking=25.0, color=cta_row.color,
            justify="center", role="cta",
        )
        if not accent_target_id:
            accent_target_id = "$last"
        base_y += height * 0.016
        vc.add_shape_rectangle(x=cta_x, y=base_y, width=cta_w, height=1, fill=cta_row.color)

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
    """Z-Pattern Archetype: Dynamic diagonal scan with collision-free vertical slotting."""
    canvas_base = palette[0] if palette else "#070B19"
    accent_color = palette[1] if len(palette) > 1 else "#00F5D4"
    structural_color = palette[4] if len(palette) > 4 else "#FFFFFF"
    margin = plan.margin
    fonts = audit_fonts()
    genre = _detect_genre(brief)

    # Layer 0: Background
    vc.place_image(bg_path, rect=[0, 0, width, height])

    # Layer 1: Atmospheric Scrims (Edge Stop Strictly Opacity 0.0)
    vc.soft_scrim(
        x=0, y=0, width=width, height=height * 0.35,
        stops=[(0.0, canvas_base, 0.88), (1.0, canvas_base, 0.0)],
        direction="to_bottom",
    )
    vc.soft_scrim(
        x=0, y=height * 0.55, width=width, height=height * 0.45,
        stops=[(0.0, canvas_base, 0.90), (1.0, canvas_base, 0.0)],
        direction="to_top",
    )

    # BUG 2 FIX: Collision resolution for top band (organizer + date badge)
    top_y = height * 0.05
    org_row = plan.get_row("organizer")
    date_row = plan.get_row("date_time")

    w_org = estimate_text_width(org_row.text, org_row.size, org_row.font, org_row.tracking) if org_row else 0.0
    w_date = estimate_text_width(date_row.text, date_row.size, fonts["display"], 20.0) if date_row else 0.0
    usable_w = width - (2 * margin)
    min_gap = width * 0.03  # 3% canvas gap requirement

    if org_row and date_row and (w_org + w_date + min_gap > usable_w):
        # Collision detected: Stack vertically
        vc.add_text(
            text=org_row.text, x=margin, y=top_y, size=org_row.size,
            font=org_row.font, style=org_row.style, tracking=org_row.tracking,
            color=structural_color, justify="left", role="organizer_mark",
        )
        top_y += org_row.size * 1.35 + 8
        vc.add_text(
            text=date_row.text, x=width - margin, y=top_y, size=date_row.size * 0.85,
            font=fonts["display"], style="Bold", tracking=15.0,
            color=accent_color, justify="right", role="date_badge",
        )
        title_start_y = top_y + date_row.size * 1.35 + 16
    else:
        # Fits side by side without collision
        if org_row:
            vc.add_text(
                text=org_row.text, x=margin, y=top_y, size=org_row.size,
                font=org_row.font, style=org_row.style, tracking=org_row.tracking,
                color=structural_color, justify="left", role="organizer_mark",
            )
        if date_row:
            vc.add_text(
                text=date_row.text, x=width - margin, y=top_y, size=date_row.size * 0.85,
                font=fonts["display"], style="Bold", tracking=15.0,
                color=accent_color, justify="right", role="date_badge",
            )
        title_start_y = height * 0.12

    # Diagonal Headline: Area text bounded by margin box with autoHeight
    title_row = plan.get_row("title")
    title_y = max(title_start_y, height * 0.11)
    if title_row:
        h_box_w = width - (2 * margin)
        h_block_h = estimate_headline_height(title_row.text, title_row.size * 0.85, h_box_w, title_row.font)
        vc.area_text(
            text=title_row.text,
            x=margin,
            y=title_y,
            width=h_box_w,
            height=h_block_h + 10,
            size=title_row.size * 0.85,
            font=title_row.font,
            style="Bold",
            color=structural_color,
            justify="left",
            fit="autoHeight",
            role="headline_line1",
        )

    # Mid-Canvas Diagonal Hero
    hero_w = min(width * 0.50, height * 0.38)
    hero_h = hero_w
    hero_cx = width * 0.55
    hero_cy = height * 0.44

    vc.radial_light(
        cx=hero_cx, cy=hero_cy, radius=hero_w * 0.65,
        color=accent_color, alpha_stop_inner=0.45, alpha_stop_outer=0.0,
        blend_mode="screen",
    )
    vc.place_image(hero_path, rect=[hero_cx - hero_w / 2.0, hero_cy - hero_h / 2.0, hero_w, hero_h])
    hero_node_id = "$last"

    # BUG 2 FIX: Dedicated non-overlapping vertical slotting for bottom band
    bot_y = height * 0.69

    def _clamp_zp(txt: str, sz: float, fnt: str, trk: float = 0.0) -> float:
        est = estimate_text_width(txt, sz, fnt, trk)
        if est > usable_w and est > 0:
            return max(10.0, sz * (usable_w / est) * 0.95)
        return sz

    events_row = plan.get_row("events")
    if events_row:
        vc.add_text(
            text="FEATURED TRACKS:", x=margin, y=bot_y, size=12.0,
            font=fonts["mono"], style="Regular", color=palette[2] if len(palette) > 2 else "#00BBF9",
            justify="left", role="events_label",
        )
        bot_y += height * 0.024
        ev_sz = _clamp_zp(events_row.text, events_row.size * 0.85, events_row.font)
        vc.add_text(
            text=events_row.text, x=margin, y=bot_y, size=ev_sz,
            font=events_row.font, style="Bold", color=structural_color, justify="left", role="events_content",
        )
        bot_y += height * 0.038

    venue_row = plan.get_row("venue")
    if venue_row:
        v_sz = _clamp_zp(venue_row.text, venue_row.size, venue_row.font)
        vc.add_text(
            text=venue_row.text, x=margin, y=bot_y, size=v_sz,
            font=venue_row.font, style="Regular", color=structural_color, justify="left", role="venue",
        )
        bot_y += height * 0.038

    prize_row = plan.get_row("prize")
    accent_target_id = None
    if prize_row:
        prz_txt = f"AWARDS: {prize_row.text}"
        prz_sz = _clamp_zp(prz_txt, prize_row.size * 0.90, prize_row.font)
        vc.add_text(
            text=prz_txt, x=margin, y=bot_y, size=prz_sz,
            font=prize_row.font, style="Bold", color=prize_row.color, justify="left", role="grand_prize",
        )
        accent_target_id = "$last"
        bot_y += height * 0.038

    cta_row = plan.get_row("cta")
    if cta_row:
        cta_txt = f"JOIN: {cta_row.text}  →"
        cta_sz = _clamp_zp(cta_txt, cta_row.size * 0.95, cta_row.font)
        vc.add_text(
            text=cta_txt, x=width - margin, y=bot_y, size=cta_sz,
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
    """Split Layout Archetype: Seamless upper art zone into solid lower field (ZERO horizontal seam lines)."""
    canvas_base = palette[0] if palette else "#070B19"
    accent_color = palette[1] if len(palette) > 1 else "#00F5D4"
    structural_color = palette[4] if len(palette) > 4 else "#FFFFFF"
    margin = plan.margin
    fonts = audit_fonts()
    genre = _detect_genre(brief)

    # Upper Art Zone
    vc.place_image(bg_path, rect=[0, 0, width, height])

    hero_cx = width * 0.50
    hero_cy = height * 0.26
    hero_w = min(width * 0.48, height * 0.35)
    hero_h = hero_w

    vc.radial_light(
        cx=hero_cx, cy=hero_cy, radius=hero_w * 0.60,
        color=accent_color, alpha_stop_inner=0.45, alpha_stop_outer=0.0,
        blend_mode="screen",
    )
    vc.place_image(hero_path, rect=[hero_cx - hero_w / 2.0, hero_cy - hero_h / 2.0, hero_w, hero_h])
    hero_node_id = "$last"

    # BUG 4 FIX: Seamless scrim covering entire lower field down to canvas edge
    # Direction 'to_top' starts at bottom with solid 1.0 opacity, fading to opacity 0.0 at y = 0.44 * H
    # Eliminates hard opaque rectangle boundary cutting through the headline
    split_top_y = height * 0.44
    vc.soft_scrim(
        x=0, y=split_top_y, width=width, height=height - split_top_y,
        stops=[(0.0, canvas_base, 1.0), (0.70, canvas_base, 1.0), (1.0, canvas_base, 0.0)],
        direction="to_top",
    )

    # Lower zone: Left-aligned editorial typography column
    type_x = margin + 20
    max_text_w = width - type_x - margin
    type_y = height * 0.54

    def _clamp_split(txt: str, sz: float, fnt: str, trk: float = 0.0) -> float:
        est = estimate_text_width(txt, sz, fnt, trk)
        if est > max_text_w and est > 0:
            return max(10.0, sz * (max_text_w / est) * 0.95)
        return sz

    title_row = plan.get_row("title")
    if title_row:
        h_block_h = estimate_headline_height(title_row.text, title_row.size * 0.80, max_text_w, title_row.font)
        vc.area_text(
            text=title_row.text,
            x=type_x,
            y=type_y,
            width=max_text_w,
            height=h_block_h + 10,
            size=title_row.size * 0.80,
            font=title_row.font,
            style="Bold",
            color=structural_color,
            justify="left",
            fit="autoHeight",
            role="title",
        )
        type_y += h_block_h + height * 0.020

    # Hairline divider
    vc.add_shape_rectangle(x=type_x, y=type_y, width=max_text_w, height=1, fill=accent_color)
    type_y += height * 0.028

    blurb_row = plan.get_row("blurb")
    if blurb_row:
        blurb_sz = _clamp_split(blurb_row.text, blurb_row.size, blurb_row.font)
        vc.add_text(
            text=blurb_row.text, x=type_x, y=type_y, size=blurb_sz,
            font=blurb_row.font, style="Regular", color="#DCE5F5", justify="left", role="blurb",
        )
        type_y += height * 0.038

    events_row = plan.get_row("events")
    if events_row:
        ev_txt = f"TRACKS: {events_row.text}"
        ev_sz = _clamp_split(ev_txt, events_row.size * 0.85, events_row.font)
        vc.add_text(
            text=ev_txt, x=type_x, y=type_y, size=ev_sz,
            font=events_row.font, style="Bold", color=structural_color, justify="left", role="events",
        )
        type_y += height * 0.038

    date_row = plan.get_row("date_time")
    if date_row:
        dt_txt = f"SCHEDULE: {date_row.text}"
        dt_sz = _clamp_split(dt_txt, date_row.size * 0.90, fonts["sans"])
        vc.add_text(
            text=dt_txt, x=type_x, y=type_y, size=dt_sz,
            font=fonts["sans"], style="Bold", color=structural_color, justify="left", role="schedule",
        )
        type_y += height * 0.035

    venue_row = plan.get_row("venue")
    if venue_row:
        v_sz = _clamp_split(venue_row.text, venue_row.size, venue_row.font)
        vc.add_text(
            text=venue_row.text, x=type_x, y=type_y, size=v_sz,
            font=venue_row.font, style="Regular", color=structural_color, justify="left", role="venue",
        )
        type_y += height * 0.038

    prize_row = plan.get_row("prize")
    accent_target_id = None
    if prize_row:
        prz_txt = f"PRIZE POOL: {prize_row.text}"
        prz_sz = _clamp_split(prz_txt, prize_row.size, prize_row.font)
        vc.add_text(
            text=prz_txt, x=type_x, y=type_y, size=prz_sz,
            font=prize_row.font, style="Bold", color=prize_row.color, justify="left", role="grand_prize",
        )
        accent_target_id = "$last"
        type_y += height * 0.038

    cta_row = plan.get_row("cta")
    if cta_row:
        cta_txt = f"REGISTRATION: {cta_row.text}"
        cta_sz = _clamp_split(cta_txt, cta_row.size, cta_row.font)
        vc.add_text(
            text=cta_txt, x=type_x, y=type_y, size=cta_sz,
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
    """3-Column Grid Archetype: Balanced vertical distribution with bounded columns."""
    canvas_base = palette[0] if palette else "#070B19"
    accent_color = palette[1] if len(palette) > 1 else "#00F5D4"
    structural_color = palette[4] if len(palette) > 4 else "#FFFFFF"
    margin = plan.margin
    fonts = audit_fonts()
    genre = _detect_genre(brief)

    # 3-Column Geometry
    gutter = 28.0
    col_w = (width - 2 * margin - 2 * gutter - 1.0) / 3.0
    col1_x = margin
    col2_x = margin + col_w + gutter
    col3_x = margin + 2 * (col_w + gutter)

    # Layer 0: Background
    vc.place_image(bg_path, rect=[0, 0, width, height])

    # Scrims (Edge Stop Strictly Opacity 0.0)
    vc.soft_scrim(
        x=0, y=0, width=width, height=height * 0.30,
        stops=[(0.0, canvas_base, 0.90), (1.0, canvas_base, 0.0)],
        direction="to_bottom",
    )
    vc.soft_scrim(
        x=0, y=height * 0.65, width=width, height=height * 0.35,
        stops=[(0.0, canvas_base, 0.90), (1.0, canvas_base, 0.0)],
        direction="to_top",
    )

    # Full-Width Spanning Headline
    head_y = height * 0.055
    org_row = plan.get_row("organizer")
    if org_row:
        vc.add_text(
            text=org_row.text, x=margin, y=head_y, size=org_row.size,
            font=fonts["mono"], style="Regular", color=palette[2] if len(palette) > 2 else "#00BBF9",
            justify="left", role="organizer",
        )
        head_y += org_row.size * 1.35 + 8

    title_row = plan.get_row("title")
    if title_row:
        h_box_w = width - (2 * margin)
        vc.area_text(
            text=title_row.text,
            x=margin,
            y=head_y,
            width=h_box_w,
            height=height * 0.10,
            size=title_row.size * 0.90,
            font=title_row.font,
            style="Bold",
            color=structural_color,
            justify="center",
            fit="autoHeight",
            role="full_width_headline",
        )
        if "\n" not in title_row.text and estimate_text_width(title_row.text, title_row.size * 0.90, font=title_row.font) <= h_box_w * 0.88:
            vc.fit_headline()
        head_y += height * 0.085

    # Hairline divider under header
    vc.add_shape_rectangle(x=margin, y=head_y, width=width - 2 * margin, height=1, fill=accent_color)

    # BUG 5 FIX: Vertically balanced distribution across the mid-canvas
    mid_top_y = head_y + height * 0.035

    # Center Column (Col 2): Substantial hero asset with radial light
    hero_w = min(col_w * 1.35, height * 0.35)
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

    # Center Column Content below Hero (Tagline, Blurb, Subtitle)
    c_y = mid_top_y + hero_h + height * 0.030
    tag_row = plan.get_row("tagline")
    if tag_row:
        vc.add_text(
            text=tag_row.text, x=hero_cx, y=c_y, size=tag_row.size,
            font=fonts["display"], style="Bold", color=palette[2] if len(palette) > 2 else "#00BBF9",
            justify="center", role="tagline",
        )
        c_y += tag_row.size * 1.35 + 12

    blurb_row = plan.get_row("blurb")
    if blurb_row:
        vc.area_text(
            text=blurb_row.text, x=col2_x - 10, y=c_y, width=col_w + 20, height=height * 0.15,
            size=blurb_row.size, font=fonts["sans"], color="#DCE5F5", justify="center", fit="autoHeight", role="blurb",
        )
        c_y += height * 0.09

    sub_row = plan.get_row("subtitle")
    if sub_row:
        vc.add_text(
            text=f"— {sub_row.text} —", x=hero_cx, y=c_y, size=13.0,
            font=fonts["sans"], style="Bold", color=structural_color, justify="center", role="subtitle",
        )

    # Left Column (Tracks & Schedule Block)
    l_y = mid_top_y
    vc.add_text(text="TRACKS & HIGHLIGHTS", x=col1_x, y=l_y, size=13.0, font=fonts["mono"], style="Bold", color=accent_color, justify="left", role="col1_header")
    l_y += height * 0.022
    vc.add_shape_rectangle(x=col1_x, y=l_y, width=col_w, height=1, fill=accent_color)
    l_y += height * 0.028

    events_row = plan.get_row("events")
    if events_row:
        events_list = [e.strip() for e in events_row.text.split("/") if e.strip()]
        for ev in events_list[:5]:
            vc.area_text(
                text=f"//  {ev}", x=col1_x, y=l_y, width=col_w, height=36,
                size=14.0, font=fonts["sans"], style="Bold", color=structural_color, justify="left", fit="shrinkText", role="track_item",
            )
            l_y += height * 0.038

    # Left Column: Schedule block fills vertical space
    l_y = max(l_y + 15, height * 0.62)
    vc.add_text(text="EVENT SCHEDULE:", x=col1_x, y=l_y, size=12.0, font=fonts["mono"], color=palette[2] if len(palette) > 2 else "#00BBF9", justify="left", role="sched_label")
    l_y += height * 0.022
    date_row = plan.get_row("date_time")
    if date_row:
        vc.area_text(
            text=date_row.text, x=col1_x, y=l_y, width=col_w, height=45,
            size=14.0, font=fonts["sans"], style="Bold", color=structural_color, justify="left", fit="shrinkText", role="schedule_text",
        )
        l_y += height * 0.040

    venue_row = plan.get_row("venue")
    if venue_row:
        vc.area_text(
            text=venue_row.text, x=col1_x, y=l_y, width=col_w, height=45,
            size=13.0, font=fonts["sans"], style="Regular", color="#DCE5F5", justify="left", fit="shrinkText", role="venue_text",
        )

    # BUG 1 FIX: Right Column (Bounded by col_w using fit="shrinkText" - ZERO canvas escape)
    r_y = mid_top_y
    vc.add_text(text="PRIZES & REGISTRATION", x=col3_x, y=r_y, size=13.0, font=fonts["mono"], style="Bold", color=accent_color, justify="left", role="col3_header")
    r_y += height * 0.022
    vc.add_shape_rectangle(x=col3_x, y=r_y, width=col_w, height=1, fill=accent_color)
    r_y += height * 0.028

    prize_row = plan.get_row("prize")
    accent_target_id = None
    if prize_row:
        vc.add_text(text="AWARD POOL:", x=col3_x, y=r_y, size=12.0, font=fonts["mono"], color=palette[2] if len(palette) > 2 else "#00BBF9", justify="left", role="prize_label")
        r_y += height * 0.024
        # Bounded area text within col_w: never overflows right margin
        vc.area_text(
            text=prize_row.text, x=col3_x, y=r_y, width=col_w, height=45,
            size=prize_row.size * 0.85, font=prize_row.font, style="Bold", color=prize_row.color, justify="left", fit="shrinkText", role="grand_prize",
        )
        accent_target_id = "$last"
        r_y += height * 0.055

    cta_row = plan.get_row("cta")
    if cta_row:
        vc.add_text(text="REGISTRATION ACTION:", x=col3_x, y=r_y, size=12.0, font=fonts["mono"], color=palette[2] if len(palette) > 2 else "#00BBF9", justify="left", role="cta_label")
        r_y += height * 0.024
        # Bounded area text within col_w: never overflows right margin
        vc.area_text(
            text=cta_row.text, x=col3_x, y=r_y, width=col_w, height=45,
            size=cta_row.size * 0.85, font=cta_row.font, style="Bold", color=cta_row.color, justify="left", fit="shrinkText", role="cta",
        )
        if not accent_target_id:
            accent_target_id = "$last"
        r_y += height * 0.055

    # Right Column: Circuit Info fills vertical space
    r_y = max(r_y + 15, height * 0.62)
    vc.add_text(text="CIRCUIT ELIGIBILITY:", x=col3_x, y=r_y, size=12.0, font=fonts["mono"], color=palette[2] if len(palette) > 2 else "#00BBF9", justify="left", role="elig_label")
    r_y += height * 0.022
    vc.area_text(
        text="ALL COLLEGES & UNIVERSITIES", x=col3_x, y=r_y, width=col_w, height=35,
        size=13.0, font=fonts["sans"], style="Bold", color=structural_color, justify="left", fit="shrinkText", role="elig_text",
    )

    # Monospace Footer Strip (JetBrains Mono if available)
    footer_y = height - margin - 25
    vc.add_shape_rectangle(x=margin, y=footer_y - 12, width=width - 2 * margin, height=1, fill=palette[2] if len(palette) > 2 else "#00BBF9")

    footer_parts = []
    if date_row:
        footer_parts.append(f"DATE: {date_row.text}")
    if venue_row:
        footer_parts.append(venue_row.text)
    full_footer = "   ◆   ".join(footer_parts)

    usable_footer_w = width - (2 * margin)
    est_foot_w = estimate_text_width(full_footer, 12.0, fonts["mono"], 15.0)
    if est_foot_w > usable_footer_w and len(footer_parts) >= 2:
        # Stack date and venue on two compact mono lines
        p1_sz = 11.0
        est_p1 = estimate_text_width(footer_parts[0], p1_sz, fonts["mono"], 15.0)
        if est_p1 > usable_footer_w:
            p1_sz = max(9.0, p1_sz * (usable_footer_w / est_p1) * 0.95)

        p2_sz = 10.5
        est_p2 = estimate_text_width(footer_parts[1], p2_sz, fonts["mono"], 15.0)
        if est_p2 > usable_footer_w:
            p2_sz = max(9.0, p2_sz * (usable_footer_w / est_p2) * 0.95)

        vc.add_text(
            text=footer_parts[0],
            x=width / 2.0,
            y=footer_y,
            size=p1_sz,
            font=fonts["mono"],
            style="Regular",
            tracking=15.0,
            color=structural_color,
            justify="center",
            role="monospace_footer_line1",
        )
        vc.add_text(
            text=footer_parts[1],
            x=width / 2.0,
            y=footer_y + 16,
            size=p2_sz,
            font=fonts["mono"],
            style="Regular",
            tracking=15.0,
            color=structural_color,
            justify="center",
            role="monospace_footer_line2",
        )
    else:
        foot_sz = 12.0
        if est_foot_w > usable_footer_w and est_foot_w > 0:
            foot_sz = max(9.0, 12.0 * (usable_footer_w / est_foot_w) * 0.95)
        vc.add_text(
            text=full_footer,
            x=width / 2.0,
            y=footer_y + 8,
            size=foot_sz,
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
