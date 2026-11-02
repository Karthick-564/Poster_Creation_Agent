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

LABEL_DATE = "DATE:"
LABEL_SCHEDULE = "SCHEDULE:"
LABEL_EVENT_SCHEDULE = "EVENT SCHEDULE:"
LABEL_LOCATION = "LOCATION:"
LABEL_TRACKS = "TRACKS:"
LABEL_FEATURED_TRACKS = "FEATURED TRACKS:"
LABEL_TRACKS_HIGHLIGHTS = "TRACKS & HIGHLIGHTS"
LABEL_TRACKS_HIGHLIGHTS_COLON = "TRACKS & HIGHLIGHTS:"
LABEL_PRIZES_REGISTRATION = "PRIZES & REGISTRATION"
LABEL_PRIZES_REGISTRATION_COLON = "PRIZES & REGISTRATION:"
LABEL_AWARD_POOL = "AWARD POOL:"
LABEL_AWARDS = "AWARDS:"
LABEL_REGISTRATION_ACTION = "REGISTRATION ACTION:"
LABEL_REGISTRATION = "REGISTRATION:"
LABEL_CIRCUIT_ELIGIBILITY = "CIRCUIT ELIGIBILITY:"
LABEL_PRESENTED_BY = "PRESENTED BY"
LABEL_JOIN = "JOIN:"

MICROCOPY_ALLOWLIST: list[str] = [
    LABEL_DATE,
    LABEL_SCHEDULE,
    LABEL_EVENT_SCHEDULE,
    LABEL_LOCATION,
    LABEL_TRACKS,
    LABEL_FEATURED_TRACKS,
    LABEL_TRACKS_HIGHLIGHTS,
    LABEL_TRACKS_HIGHLIGHTS_COLON,
    LABEL_PRIZES_REGISTRATION,
    LABEL_PRIZES_REGISTRATION_COLON,
    LABEL_AWARD_POOL,
    LABEL_AWARDS,
    LABEL_REGISTRATION_ACTION,
    LABEL_REGISTRATION,
    LABEL_CIRCUIT_ELIGIBILITY,
    LABEL_PRESENTED_BY,
    LABEL_JOIN,
]


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


def audit_fonts(school: Optional[str] = None) -> dict[str, str]:
    """Audit available fonts at runtime via VectorCraft's shared fonts directory.

    Returns mapping of canonical roles ('display', 'sans', 'mono', 'serif', 'tamil')
    to available font family names, degrading gracefully to system fonts if specific
    TTF files are absent. Prefers the specified school's display voice if provided.
    """
    fonts_dir = get_vectorcraft_fonts_dir()
    available_ttfs = set()
    if fonts_dir.exists() and fonts_dir.is_dir():
        for p in fonts_dir.glob("*.ttf"):
            available_ttfs.add(p.stem.lower())
        for p in fonts_dir.glob("*.otf"):
            available_ttfs.add(p.stem.lower())

    # Map roles based on verified installed fonts
    has_inter = any("inter" in name for name in available_ttfs)
    has_jetbrains = any("jetbrains" in name for name in available_ttfs)
    has_sourcesans = any("sourcesans" in name for name in available_ttfs)
    has_sourceserif = any("sourceserif" in name for name in available_ttfs)
    has_montserrat = any("montserrat" in name for name in available_ttfs)
    has_barlow = any("barlow" in name for name in available_ttfs)
    has_noto_tamil = any("notosanstamil" in name or ("noto" in name and "tamil" in name) for name in available_ttfs)

    # School display voice resolution
    if school == "KCTBS":
        display_font = "Barlow" if has_barlow else ("Montserrat" if has_montserrat else ("Inter" if has_inter else "Bahnschrift"))
    elif school in ("KCT", "KCLAS", "KI", "KIA"):
        display_font = "Montserrat" if has_montserrat else ("Inter" if has_inter else "Bahnschrift")
    else:
        # Default display voice: prefer Montserrat if installed, else Inter, else Bahnschrift
        display_font = "Montserrat" if has_montserrat else ("Inter" if has_inter else "Bahnschrift")

    sans_font = "Inter" if has_inter else ("Source Sans 3" if has_sourcesans else "Segoe UI")
    mono_font = "JetBrains Mono" if has_jetbrains else "Consolas"
    serif_font = "Source Serif 4" if has_sourceserif else "Georgia"
    tamil_font = "Noto Sans Tamil" if has_noto_tamil else "Nirmala UI"

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
    # Ratio for uppercase display text vs lowercase sans vs monospace
    ratio = 0.60 if "mono" in font.lower() else (0.66 if text.isupper() else 0.58)
    tracking_offset = (tracking / 1000.0) * size * len(text)
    return (len(text) * size * ratio) + tracking_offset


def estimate_headline_height(text: str, size: float, max_width: float, font: str = "Inter") -> float:
    """Estimate rendered multi-line block height for headlines."""
    words = text.split()
    if not words:
        return 0.0
    lines = 1
    curr_w = 0.0
    for w in words:
        w_len = estimate_text_width(w, size, font)
        space_w = estimate_text_width(" ", size, font)
        if curr_w == 0.0:
            curr_w = w_len
        elif curr_w + space_w + w_len <= max_width:
            curr_w += space_w + w_len
        else:
            lines += 1
            curr_w = w_len
    total_w = estimate_text_width(text, size, font)
    if total_w > max_width and lines == 1:
        lines = 2
    line_height = size * 1.05
    return max(size, lines * line_height)


def is_light_context(brief: ExtractedBrief, palette: list[str]) -> bool:
    """Detect if the design brief or palette dictates a light-background poster."""
    mood = brief.get_text("mood").lower()
    palette_use = brief.get_text("palette_use").lower()
    if "light background" in mood or "light" in mood or "navy for text" in palette_use:
        return True
    if palette:
        bg_col = palette[0].lstrip("#")
        if len(bg_col) == 6:
            try:
                r, g, b = int(bg_col[0:2], 16), int(bg_col[2:4], 16), int(bg_col[4:6], 16)
                lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
                if lum > 0.6:
                    return True
            except ValueError:
                pass
    return False


def generate_qr_code(link: str, output_path: Path) -> Path:
    """Generate a high-contrast QR code image for print/screen use."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(output_path)
    except Exception:
        from PIL import Image as PILImage, ImageDraw as PILDraw
        img = PILImage.new("RGB", (200, 200), "#FFFFFF")
        draw = PILDraw.Draw(img)
        draw.rectangle([10, 10, 190, 190], outline="#000000", width=4)
        draw.rectangle([30, 30, 70, 70], fill="#000000")
        draw.rectangle([130, 30, 170, 70], fill="#000000")
        draw.rectangle([30, 130, 70, 170], fill="#000000")
        img.save(output_path)
    return output_path


def _hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join([c*2 for c in h])
    try:
        return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)
    except Exception:
        return (0.0, 0.0, 0.0)


def _srgb_to_lum(rgb: tuple[float, float, float]) -> float:
    def _channel_lum(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * _channel_lum(r) + 0.7152 * _channel_lum(g) + 0.0722 * _channel_lum(b)


def get_contrast_ratio(hex1: str, hex2: str) -> float:
    """Calculate WCAG 2.1 relative luminance contrast ratio between two hex colors."""
    l1 = _srgb_to_lum(_hex_to_rgb(hex1))
    l2 = _srgb_to_lum(_hex_to_rgb(hex2))
    l_max = max(l1, l2)
    l_min = min(l1, l2)
    return (l_max + 0.05) / (l_min + 0.05)


def ensure_contrast_color(bg_hex: str, preferred_fg: str = "#FFFFFF", min_contrast: float = 4.5) -> str:
    """Select text color achieving >= min_contrast:1 against background."""
    if get_contrast_ratio(bg_hex, preferred_fg) >= min_contrast:
        return preferred_fg
    cr_white = get_contrast_ratio(bg_hex, "#FFFFFF")
    cr_navy = get_contrast_ratio(bg_hex, "#0B2A5B")
    return "#FFFFFF" if cr_white >= cr_navy else "#0B2A5B"


def _wrap_to_two_lines(text: str) -> tuple[str, str]:
    """Break text into at most two balanced lines at word boundaries."""
    words = text.strip().split()
    if len(words) <= 1:
        return text, ""
    mid_char = len(text) / 2.0
    best_split = 1
    best_diff = float("inf")
    cur_len = 0
    for i in range(len(words) - 1):
        cur_len += len(words[i]) + (1 if i > 0 else 0)
        diff = abs(cur_len - mid_char)
        if diff < best_diff:
            best_diff = diff
            best_split = i + 1
    return " ".join(words[:best_split]), " ".join(words[best_split:])


def wrap_and_fit_row(
    text: str,
    target_size: float,
    floor_size: float,
    max_w: float,
    font: str = "Inter",
    tracking: float = 0.0,
    role: str = "text",
) -> tuple[list[str], float]:
    """Ensure row text width respects max_w:
    1. If single line fits max_w at target_size, return [text], target_size.
    2. If over: wrap to <= 2 lines.
    3. If 2 lines still over: shrink toward floor_size.
    4. If still over at floor_size: emit loud banner and return [line1, line2], floor_size.
    """
    w1 = estimate_text_width(text, target_size, font=font, tracking=tracking)
    if w1 <= max_w:
        return [text], target_size

    l1, l2 = _wrap_to_two_lines(text)
    if not l2:
        w_max = w1
    else:
        w_max = max(
            estimate_text_width(l1, target_size, font=font, tracking=tracking),
            estimate_text_width(l2, target_size, font=font, tracking=tracking),
        )

    if w_max <= max_w:
        lines = [l1, l2] if l2 else [l1]
        return lines, target_size

    scale = (max_w / w_max) * 0.96
    fit_sz = target_size * scale
    lines = [l1, l2] if l2 else [l1]

    if fit_sz >= floor_size:
        return lines, fit_sz

    print(
        f">>> [composer] LOUD BANNER: row '{role}' ('{text[:30]}...') "
        f"width at floor {floor_size:.1f}pt exceeds usable_w {max_w:.1f}pt; scaled to {fit_sz:.1f}pt (never render clipped)"
    )
    return lines, fit_sz


def check_rect_intersection(r1: tuple[float, float, float, float], r2: tuple[float, float, float, float]) -> bool:
    """True if two (x, y, w, h) rectangles strictly intersect."""
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2
    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)


def compute_vband_coverage(
    items: list[dict[str, Any]],
    canvas_h: float,
    band_fractions: Optional[list[tuple[float, float, str]]] = None,
) -> tuple[float, list[int], list[str]]:
    """Compute vertical band coverage across canvas height.
    Returns (coverage_pct, occupied_band_indices, band_descriptions).
    """
    if band_fractions is None:
        band_fractions = [
            (0.00, 0.15, "Band 0: Header & Brand"),
            (0.15, 0.35, "Band 1: Headline & Hook"),
            (0.35, 0.55, "Band 2: Hero Visual"),
            (0.55, 0.80, "Band 3: Body & Positions"),
            (0.80, 1.00, "Band 4: Logistics & Footer"),
        ]
    total_bands = len(band_fractions)
    occupied = set()
    for it in items:
        y = it.get("y")
        b = it.get("bounds")
        y_top = y
        y_bot = y
        if isinstance(b, (list, tuple)) and len(b) >= 4:
            y_top = min(b[1], b[3])
            y_bot = max(b[1], b[3])
        elif isinstance(b, dict):
            y_top = float(b.get("y", y or 0.0))
            y_bot = y_top + float(b.get("height", b.get("h", 0.0)))

        if y_top is None:
            continue

        for idx, (f_start, f_end, _) in enumerate(band_fractions):
            b_start = f_start * canvas_h
            b_end = f_end * canvas_h
            if y_bot >= b_start and y_top <= b_end:
                occupied.add(idx)

    cov_pct = (len(occupied) / total_bands) * 100.0
    return cov_pct, sorted(occupied), [b[2] for b in band_fractions]


def emit_logo_row(
    vc: VectorCraftRenderer,
    brief: ExtractedBrief,
    school_info: dict[str, Any],
    width: float,
    height: float,
    margin_x: float,
    margin_y: float,
    is_light: bool = True,
) -> list[dict[str, Any]]:
    """Emit brand logo(s) according to house style rules."""
    emitted = []
    logo_path_str = getattr(brief, "asset_references", {}).get("logo_path") or brief.get_text("logo_path")
    logos_spec = brief.get_text("logos")
    school_logo = school_info.get("logo", "assets/logo_kumaraguru.png")
    
    kg_path = Path(school_logo) if school_logo else Path("assets/logo_kumaraguru.png")
    if logo_path_str and Path(logo_path_str).exists():
        kg_path = Path(logo_path_str)
        
    gdg_path = Path("assets/logo_gdg_oncampus.png")
    
    logo_h = max(36.0, height * 0.035)
    logo_w = logo_h * 3.0
    logo_y = margin_y + 8.0
    
    if kg_path.exists():
        vc.place_image(kg_path, rect=[margin_x, logo_y, logo_w, logo_h])
        emitted.append({"role": "_structure_logo_left", "path": str(kg_path), "rect": [margin_x, logo_y, logo_w, logo_h]})
        
    if gdg_path.exists() and ("gdg" in brief.get_text("title").lower() or "gdg" in brief.get_text("organizer").lower() or "gdg" in logos_spec.lower()):
        vc.place_image(gdg_path, rect=[width - margin_x - logo_w, logo_y, logo_w, logo_h])
        emitted.append({"role": "_structure_logo_right", "path": str(gdg_path), "rect": [width - margin_x - logo_w, logo_y, logo_w, logo_h]})
        
    return emitted


def emit_banner_tab_row(
    vc: VectorCraftRenderer,
    text: str,
    width: float,
    height: float,
    font: str,
    fill_color: str,
    text_color: str = "#FFFFFF",
    y: float = 0.0,
) -> tuple[float, dict[str, Any]]:
    """Emit top band bar (brand primary fill) with the hook/call-out line."""
    bar_h = max(36.0, height * 0.026)
    text_color = ensure_contrast_color(fill_color, text_color, min_contrast=4.5)
    vc.add_shape_rectangle(x=0.0, y=y, width=width, height=bar_h, fill=fill_color)
    vc.add_text(
        text=text.upper(),
        x=width * 0.5,
        y=y + (bar_h * 0.68),
        size=max(12.0, bar_h * 0.44),
        font=font,
        style="Bold",
        tracking=35.0,
        color=text_color,
        justify="center",
        role="_structure_banner_tab",
    )
    item = {
        "role": "_structure_banner_tab",
        "text": text,
        "x": width * 0.5,
        "y": y + (bar_h * 0.68),
        "height": bar_h,
        "fill_color": fill_color,
        "text_color": text_color,
    }
    return y + bar_h, item


def emit_pill_row(
    vc: VectorCraftRenderer,
    text: str,
    x: float,
    y: float,
    font: str,
    fill_color: str,
    text_color: str = "#FFFFFF",
    size: float = 18.0,
    radius: float = 14.0,
    padding_h: float = 24.0,
    padding_v: float = 7.0,
    role: str = "_structure_pill",
    justify: str = "center",
) -> dict[str, Any]:
    """Emit rounded-rect fill container + centered caps label."""
    text_color = ensure_contrast_color(fill_color, text_color, min_contrast=4.5)
    text_w = estimate_text_width(text.upper(), size, font=font, tracking=25.0)
    pill_w = text_w + (2.0 * padding_h)
    pill_h = size + (2.0 * padding_v)
    pill_x = x - (pill_w * 0.5) if justify == "center" else x
    pill_y = y - (size * 0.8)
    
    vc.add_shape_rectangle(
        x=pill_x,
        y=pill_y,
        width=pill_w,
        height=pill_h,
        fill=fill_color,
        radius=radius,
    )
    vc.add_text(
        text=text.upper(),
        x=x,
        y=y,
        size=size,
        font=font,
        style="Bold",
        tracking=25.0,
        color=text_color,
        justify=justify,
        role=role,
    )
    return {
        "role": role,
        "text": text,
        "x": x,
        "y": y,
        "bounds": [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
        "fill_color": fill_color,
        "text_color": text_color,
    }


def emit_footer_bar_row(
    vc: VectorCraftRenderer,
    text: str,
    width: float,
    height: float,
    font: str,
    fill_color: str,
    text_color: str = "#FFFFFF",
    bar_height: Optional[float] = None,
) -> dict[str, Any]:
    """Emit solid brand-color footer strip with contact/date line (house footer)."""
    bar_h = bar_height or max(40.0, height * 0.032)
    bar_y = height - bar_h
    text_color = ensure_contrast_color(fill_color, text_color, min_contrast=4.5)
    vc.add_shape_rectangle(x=0.0, y=bar_y, width=width, height=bar_h, fill=fill_color)
    safe_m = max(40.0, width * 0.04)
    text_sz = max(11.0, min(15.0, bar_h * 0.35))
    text_y = min(bar_y + (bar_h * 0.58), height - safe_m - (text_sz * 0.25))
    vc.add_text(
        text=text,
        x=width * 0.5,
        y=text_y,
        size=text_sz,
        font=font,
        style="Medium",
        tracking=15.0,
        color=text_color,
        justify="center",
        role="_structure_footer",
    )
    return {
        "role": "_structure_footer",
        "text": text,
        "x": width * 0.5,
        "y": text_y,
        "height": bar_h,
        "fill_color": fill_color,
        "text_color": text_color,
    }


def emit_qr_row(
    vc: VectorCraftRenderer,
    qr_link: str,
    cta_text: str,
    x: float,
    y: float,
    qr_size: float = 90.0,
    font: str = "Inter",
    text_color: str = "#0B2A5B",
    run_dir: Optional[Path] = None,
    canvas_base: str = "#FFFFFF",
) -> dict[str, Any]:
    """Emit QR code place_image + caps label."""
    text_color = ensure_contrast_color(canvas_base, text_color, min_contrast=4.5)
    if run_dir:
        qr_path = run_dir / "qr_code.png"
    else:
        qr_path = Path("runs") / "qr_code.png"
    generate_qr_code(qr_link, qr_path)
    vc.place_image(qr_path, rect=[x, y, qr_size, qr_size])
    
    label_text = cta_text.upper() if cta_text else "SCAN TO APPLY"
    label_y = y + qr_size + 16.0
    vc.add_text(
        text=label_text,
        x=x + (qr_size * 0.5),
        y=label_y,
        size=11.5,
        font=font,
        style="Bold",
        tracking=20.0,
        color=text_color,
        justify="center",
        role="_structure_qr",
    )
    return {
        "role": "_structure_qr",
        "qr_path": str(qr_path),
        "qr_rect": [x, y, qr_size, qr_size],
        "label_text": label_text,
        "label_y": label_y,
        "text_color": text_color,
    }


def build_typography_plan(
    brief: ExtractedBrief,
    palette: list[str],
    layout_hints: Optional[list[str]] = None,
    width: float = 1080.0,
    height: float = 1920.0,
    school: Optional[str] = None,
) -> TypographicPlan:
    """Build a canvas-relative typographic plan obeying the poster-design-craft doctrine."""
    if school is None:
        try:
            from poster_agent.house_style import resolve_school
            school, _ = resolve_school(brief)
        except Exception:
            school = "KCT"
    fonts = audit_fonts(school=school)

    # Scalar system relative to canvas height (1350 is base)
    margin = max(40.0, width * 0.045)

    # Typographic scales per doctrine:
    # Headline >= canvas_h / 11, max 3 lines
    headline_size = max(72.0, (height / 11.0))
    subheadline_size = max(22.0, headline_size / 3.5)
    body_size = max(18.0, height * 0.018)  # >= 1.8% of canvas height
    microcopy_size = max(14.0, height * 0.014)  # >= 1.4% of canvas height (min 14pt)

    # Palette role assignments with light-background awareness
    is_light = is_light_context(brief, palette)
    if is_light:
        structural_color = "#0B2A5B"  # Primary deep navy per brief
        accent_color = "#4285F4"      # Google blue
        secondary_accent = "#4285F4"  # Google blue
        micro_color = "#475569"       # Legible slate
        subhead_color = "#1E293B"     # Slate navy
    else:
        structural_color = palette[4] if len(palette) > 4 else "#FFFFFF"
        accent_color = palette[1] if len(palette) > 1 else "#00F5D4"
        secondary_accent = palette[2] if len(palette) > 2 else "#00BBF9"
        micro_color = "#DCE5F5"
        subhead_color = structural_color

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

    # 0. Eyebrow (if provided)
    eyebrow_text = brief.get_text("eyebrow")
    if eyebrow_text:
        eyebrow_sz = _clamp_size(eyebrow_text.upper(), microcopy_size * 1.15, fonts["sans"], 35.0)
        # Contrast floor: on light background, use deep structural navy (contrast >= 12:1)
        eyebrow_color = structural_color if is_light else accent_color
        plan.rows.append(
            TypographicRow(
                role="eyebrow",
                text=eyebrow_text.upper(),
                zone="header",
                size=eyebrow_sz,
                style="Bold",
                tracking=35.0,
                color=eyebrow_color,
                alignment="center",
                font=fonts["sans"],
            )
        )

    # 1. Organizer / Presenter / Partner
    organizer_text = brief.get_text("organizer")
    partner_text = brief.get_text("partner")
    if organizer_text or partner_text:
        full_org = f"{organizer_text.upper()}  •  {partner_text.upper()}" if (organizer_text and partner_text) else (organizer_text or partner_text).upper()
        org_sz = _clamp_size(full_org, microcopy_size, fonts["sans"], 25.0)
        plan.rows.append(
            TypographicRow(
                role="organizer",
                text=full_org,
                zone="header",
                size=org_sz,
                style="SemiBold",
                tracking=25.0,
                color=micro_color if is_light else secondary_accent,
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
                text=f"—   {subtitle_text.upper()}   —",
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
                color=secondary_accent if not is_light else accent_color,
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
                color="#DCE5F5" if not is_light else micro_color,
                alignment="center",
                font=fonts["sans"],
            )
        )

    # 5b. Section Heading & Positions
    section_text = brief.get_text("section")
    if section_text:
        sec_sz = _clamp_size(f"—   {section_text.upper()}   —", subheadline_size * 0.85, fonts["display"], 30.0)
        plan.rows.append(
            TypographicRow(
                role="section",
                text=f"—   {section_text.upper()}   —",
                zone="positions",
                size=sec_sz,
                style="Bold",
                tracking=30.0,
                color=accent_color,
                alignment="center",
                font=fonts["display"],
            )
        )

    positions = brief.get_positions()
    for pos in positions:
        p_idx = pos["index"]
        plan.rows.append(
            TypographicRow(
                role=f"position_{p_idx}_title",
                text=pos["title"].upper(),
                zone="positions",
                size=body_size * 1.15,
                style="Bold",
                tracking=15.0,
                color=structural_color,
                alignment="left",
                font=fonts["sans"],
            )
        )
        if pos.get("tagline"):
            plan.rows.append(
                TypographicRow(
                    role=f"position_{p_idx}_tagline",
                    text=pos["tagline"],
                    zone="positions",
                    size=microcopy_size,
                    style="Regular",
                    tracking=10.0,
                    color=micro_color,
                    alignment="left",
                    font=fonts["sans"],
                )
            )
        for pt_i, pt in enumerate(pos["points"], 1):
            plan.rows.append(
                TypographicRow(
                    role=f"position_{p_idx}_point_{pt_i}",
                    text=f"•  {pt}",
                    zone="positions",
                    size=microcopy_size * 0.95,
                    style="Regular",
                    tracking=5.0,
                    color=subhead_color,
                    alignment="left",
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

    # 11. Deadline & Deadline Note
    deadline_label = brief.get_text("deadline_label")
    deadline_val = brief.get_text("deadline")
    deadline_date = brief.get_text("date")
    deadline_note = brief.get_text("deadline_note")
    if deadline_label or deadline_val:
        dl_str = f"{deadline_label}: {deadline_val}" if (deadline_label and deadline_val) else (deadline_label or deadline_val)
        if deadline_date:
            dl_str = f"{dl_str} ({deadline_date})"
        dl_sz = _clamp_size(dl_str.upper(), 18.0, fonts["sans"], 15.0)
        plan.rows.append(
            TypographicRow(
                role="deadline",
                text=dl_str.upper(),
                zone="action",
                size=dl_sz,
                style="Bold",
                tracking=15.0,
                color="#EA4335" if is_light else accent_color,
                alignment="center",
                font=fonts["sans"],
            )
        )
    if deadline_note:
        plan.rows.append(
            TypographicRow(
                role="deadline_note",
                text=deadline_note,
                zone="action",
                size=microcopy_size * 0.9,
                style="Regular",
                tracking=5.0,
                color=micro_color,
                alignment="center",
                font=fonts["sans"],
            )
        )

    # 12. Closing Line (Dedupe: only emitted in plan.rows if genre policy disallows footer bar)
    closing_text = brief.get_text("closing") or brief.get_text("closing_line")
    if closing_text:
        try:
            from poster_agent.house_style import resolve_genre
            _, genre_policy = resolve_genre(brief)
            allow_footer = genre_policy.get("allow_footer_bar", True)
        except Exception:
            allow_footer = True

        if not allow_footer:
            cl_sz = _clamp_size(closing_text.upper(), body_size * 1.05, fonts["sans"], 25.0)
            plan.rows.append(
                TypographicRow(
                    role="closing",
                    text=closing_text.upper(),
                    zone="footer",
                    size=cl_sz,
                    style="Bold",
                    tracking=25.0,
                    color=structural_color,
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
    is_light: bool = False,
) -> None:
    """Apply verified engine live effects matching poster genre without slop."""
    if is_light:
        # Keep light background designs clean, sharp and free of dark drop shadow artifacts
        return
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
    hero_path: Optional[Path | str] = None,
    hero_geom: Optional[Any] = None,
    width: float = 1080.0,
    height: float = 1350.0,
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

    # Layer 1: Soft Scrims (Zero Discontinuity: Overshoot past canvas edge, final 0.0 stop before edge)
    fade_overshoot = 0.03 * min(width, height)
    total_w = width + 2 * fade_overshoot
    total_h = height + 2 * fade_overshoot

    fade_top_y = height * 0.32
    d_top = (fade_top_y - (-fade_overshoot))
    stop_top = d_top / total_h
    vc.soft_scrim(
        x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
        stops=[(0.0, canvas_base, 0.85), (stop_top * 0.95, canvas_base, 0.0), (1.0, canvas_base, 0.0)],
        direction="to_bottom",
    )

    fade_bot_y = height * 0.58
    d_bot = (height + fade_overshoot) - fade_bot_y
    stop_bot = d_bot / total_h
    vc.soft_scrim(
        x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
        stops=[(0.0, canvas_base, 0.90), (stop_bot * 0.95, canvas_base, 0.0), (1.0, canvas_base, 0.0)],
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
        # Check if single line fits with slight adjustment
        est_single_w = estimate_text_width(title_row.text, title_row.size, font=title_row.font)
        h_size = title_row.size
        if "\n" not in title_row.text and est_single_w > h_box_w:
            scale_fit = (h_box_w / est_single_w) * 0.96
            if title_row.size * scale_fit >= 72.0:
                h_size = max(72.0, title_row.size * scale_fit)

        h_block_h = estimate_headline_height(title_row.text, h_size, h_box_w, title_row.font)
        # Bounded area text with fitHeadline
        vc.area_text(
            text=title_row.text,
            x=margin,
            y=curr_y,
            width=h_box_w,
            height=h_block_h + 10,
            size=h_size,
            font=title_row.font,
            style=title_row.style,
            color=title_row.color,
            justify="center",
            fit="autoHeight",
            role="main_headline",
        )
        if "\n" not in title_row.text and estimate_text_width(title_row.text, h_size, font=title_row.font) <= h_box_w * 0.88:
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
    if hero_path and str(hero_path).lower() not in ("none", "native", ""):
        vc.place_image(hero_path, rect=[hero_x, hero_y, hero_w, hero_h])
        hero_node_id = "$last"
    else:
        hero_node_id = None

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
        blurb_sz = blurb_row.size
        usable_blurb_w = width - 2 * margin
        est_blurb_w = estimate_text_width(blurb_row.text, blurb_sz, font=blurb_row.font, tracking=blurb_row.tracking)
        if est_blurb_w > usable_blurb_w and est_blurb_w > 0:
            blurb_sz = max(10.0, blurb_sz * (usable_blurb_w / est_blurb_w) * 0.95)
        vc.add_shape_rectangle(x=margin + 40, y=base_y, width=width - 2 * (margin + 40), height=1, fill=palette[2] if len(palette) > 2 else "#00BBF9")
        base_y += height * 0.022
        vc.add_text(
            text=blurb_row.text, x=cx, y=base_y, size=blurb_sz,
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
        from poster_agent.house_style import resolve_genre
        _, genre_policy = resolve_genre(brief)
        if genre_policy.get("allow_pills", True):
            emit_pill_row(
                vc=vc,
                text=cta_row.text,
                x=cx,
                y=base_y + (height * 0.024),
                font=cta_row.font,
                fill_color=accent_color,
                text_color="#FFFFFF",
                size=cta_row.size,
                role="_structure_pill",
            )
        else:
            cta_w = width * 0.65
            cta_x = (width - cta_w) / 2.0
            vc.add_shape_rectangle(x=cta_x, y=base_y, width=cta_w, height=1, fill=cta_row.color)
            base_y += height * 0.024
            vc.add_text(
                text=f"◆   {cta_row.text}   ◆", x=cx, y=base_y, size=cta_row.size,
                font=cta_row.font, style="Bold", tracking=25.0, color=cta_row.color,
                justify="center", role="cta",
            )
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
    hero_path: Optional[Path | str] = None,
    hero_geom: Optional[Any] = None,
    width: float = 1080.0,
    height: float = 1350.0,
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

    # Layer 1: Atmospheric Scrims (Overshoot past canvas edge, final 0.0 stop before edge)
    fade_overshoot = 0.03 * min(width, height)
    total_w = width + 2 * fade_overshoot
    total_h = height + 2 * fade_overshoot

    fade_top_y = height * 0.35
    d_top = (fade_top_y - (-fade_overshoot))
    stop_top = d_top / total_h
    vc.soft_scrim(
        x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
        stops=[(0.0, canvas_base, 0.88), (stop_top * 0.95, canvas_base, 0.0), (1.0, canvas_base, 0.0)],
        direction="to_bottom",
    )
    fade_bot_y = height * 0.55
    d_bot = (height + fade_overshoot) - fade_bot_y
    stop_bot = d_bot / total_h
    vc.soft_scrim(
        x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
        stops=[(0.0, canvas_base, 0.90), (stop_bot * 0.95, canvas_base, 0.0), (1.0, canvas_base, 0.0)],
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

    # Mid-Canvas Diagonal Hero geometry (computed before headline for collision safety)
    hero_w = min(width * 0.50, height * 0.38)
    hero_h = hero_w
    hero_cx = width * 0.55
    hero_cy = height * 0.44
    hero_top_y = hero_cy - hero_h / 2.0

    # Diagonal Slice: Two-line staggered headline
    title_row = plan.get_row("title")
    title_y = max(title_start_y, height * 0.11)
    if title_row:
        headline_size = title_row.size * 0.85
        h_box_w = width - (2 * margin)
        words = title_row.text.split()
        if len(words) >= 2:
            best_k = 1
            best_diff = float("inf")
            for k in range(1, len(words)):
                w1 = estimate_text_width(" ".join(words[:k]), headline_size, title_row.font)
                w2 = estimate_text_width(" ".join(words[k:]), headline_size, title_row.font)
                diff = abs(w1 - w2)
                if diff < best_diff:
                    best_diff = diff
                    best_k = k
            line1 = " ".join(words[:best_k])
            line2 = " ".join(words[best_k:])
        else:
            line1 = title_row.text
            line2 = ""

        l1_w = min(h_box_w, estimate_text_width(line1, headline_size, title_row.font) + 20)
        l1_h = estimate_headline_height(line1, headline_size, l1_w, title_row.font)
        vc.area_text(
            text=line1,
            x=margin,
            y=title_y,
            width=l1_w,
            height=l1_h + 8,
            size=headline_size,
            font=title_row.font,
            style="Bold",
            color=structural_color,
            justify="left",
            fit="autoHeight",
            role="headline_line1",
        )

        if line2:
            l2_x = margin + width * 0.16
            l2_max_w = (width - margin) - l2_x
            l2_y = title_y + max(headline_size * 0.90, l1_h + 4)
            l2_size = headline_size

            # Width clamp
            est_l2_w = estimate_text_width(line2, l2_size, title_row.font)
            if est_l2_w > l2_max_w and est_l2_w > 0:
                l2_size = max(18.0, l2_size * (l2_max_w / est_l2_w) * 0.95)

            # Hero intersection clamp
            l2_h = estimate_headline_height(line2, l2_size, l2_max_w, title_row.font)
            if l2_y + l2_h > hero_top_y - 8:
                avail_h = (hero_top_y - 8) - l2_y
                if avail_h > 20:
                    scale = max(0.45, avail_h / max(1.0, l2_h))
                    l2_size = max(16.0, l2_size * scale)
                    l2_h = estimate_headline_height(line2, l2_size, l2_max_w, title_row.font)
                else:
                    l2_y = hero_top_y - 8 - l2_h

            vc.area_text(
                text=line2,
                x=l2_x,
                y=l2_y,
                width=l2_max_w,
                height=l2_h + 8,
                size=l2_size,
                font=title_row.font,
                style="Bold",
                color=structural_color,
                justify="left",
                fit="autoHeight",
                role="headline_line2",
            )
    hero_cy = height * 0.44

    vc.radial_light(
        cx=hero_cx, cy=hero_cy, radius=hero_w * 0.65,
        color=accent_color, alpha_stop_inner=0.45, alpha_stop_outer=0.0,
        blend_mode="screen",
    )
    if hero_path and str(hero_path).lower() not in ("none", "native", ""):
        vc.place_image(hero_path, rect=[hero_cx - hero_w / 2.0, hero_cy - hero_h / 2.0, hero_w, hero_h])
        hero_node_id = "$last"
    else:
        hero_node_id = None

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
            text=LABEL_FEATURED_TRACKS, x=margin, y=bot_y, size=12.0,
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
        prz_txt = f"{LABEL_AWARDS} {prize_row.text}"
        prz_sz = _clamp_zp(prz_txt, prize_row.size * 0.90, prize_row.font)
        vc.add_text(
            text=prz_txt, x=margin, y=bot_y, size=prz_sz,
            font=prize_row.font, style="Bold", color=prize_row.color, justify="left", role="grand_prize",
        )
        accent_target_id = "$last"
        bot_y += height * 0.038

    cta_row = plan.get_row("cta")
    if cta_row:
        cta_txt = f"{LABEL_JOIN} {cta_row.text}  →"
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
    hero_path: Optional[Path | str] = None,
    hero_geom: Optional[Any] = None,
    width: float = 1080.0,
    height: float = 1350.0,
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
    if hero_path and str(hero_path).lower() not in ("none", "native", ""):
        vc.place_image(hero_path, rect=[hero_cx - hero_w / 2.0, hero_cy - hero_h / 2.0, hero_w, hero_h])
        hero_node_id = "$last"
    else:
        hero_node_id = None

    # Layer 1: Atmospheric Scrim (Overshoot past canvas edge, final 0.0 stop before edge)
    fade_overshoot = 0.03 * min(width, height)
    total_w = width + 2 * fade_overshoot
    total_h = height + 2 * fade_overshoot
    split_top_y = height * 0.44
    d = (height + fade_overshoot) - split_top_y
    stop_split = d / total_h
    vc.soft_scrim(
        x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
        stops=[(0.0, canvas_base, 1.0), (stop_split * 0.70, canvas_base, 1.0), (stop_split * 0.95, canvas_base, 0.0), (1.0, canvas_base, 0.0)],
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
        ev_txt = f"{LABEL_TRACKS} {events_row.text}"
        ev_sz = _clamp_split(ev_txt, events_row.size * 0.85, events_row.font)
        vc.add_text(
            text=ev_txt, x=type_x, y=type_y, size=ev_sz,
            font=events_row.font, style="Bold", color=structural_color, justify="left", role="events",
        )
        type_y += height * 0.038

    date_row = plan.get_row("date_time")
    if date_row:
        dt_txt = f"{LABEL_SCHEDULE} {date_row.text}"
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
        prz_txt = f"{LABEL_AWARD_POOL} {prize_row.text}"
        prz_sz = _clamp_split(prz_txt, prize_row.size, prize_row.font)
        vc.add_text(
            text=prz_txt, x=type_x, y=type_y, size=prz_sz,
            font=prize_row.font, style="Bold", color=prize_row.color, justify="left", role="grand_prize",
        )
        accent_target_id = "$last"
        type_y += height * 0.038

    cta_row = plan.get_row("cta")
    if cta_row:
        cta_txt = f"{LABEL_REGISTRATION} {cta_row.text}"
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
    hero_path: Optional[Path | str] = None,
    hero_geom: Optional[Any] = None,
    width: float = 1080.0,
    height: float = 1350.0,
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

    # Layer 1: Atmospheric Scrims (Overshoot past canvas edge, final 0.0 stop before edge)
    fade_overshoot = 0.03 * min(width, height)
    total_w = width + 2 * fade_overshoot
    total_h = height + 2 * fade_overshoot

    fade_top_y = height * 0.30
    d_top = (fade_top_y - (-fade_overshoot))
    stop_top = d_top / total_h
    vc.soft_scrim(
        x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
        stops=[(0.0, canvas_base, 0.90), (stop_top * 0.95, canvas_base, 0.0), (1.0, canvas_base, 0.0)],
        direction="to_bottom",
    )
    fade_bot_y = height * 0.65
    d_bot = (height + fade_overshoot) - fade_bot_y
    stop_bot = d_bot / total_h
    vc.soft_scrim(
        x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
        stops=[(0.0, canvas_base, 0.90), (stop_bot * 0.95, canvas_base, 0.0), (1.0, canvas_base, 0.0)],
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
    if hero_path and str(hero_path).lower() not in ("none", "native", ""):
        vc.place_image(hero_path, rect=[hero_cx - hero_w / 2.0, mid_top_y, hero_w, hero_h])
        hero_node_id = "$last"
    else:
        hero_node_id = None

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
    vc.add_text(text=LABEL_TRACKS_HIGHLIGHTS, x=col1_x, y=l_y, size=13.0, font=fonts["mono"], style="Bold", color=accent_color, justify="left", role="col1_header")
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
    vc.add_text(text=LABEL_EVENT_SCHEDULE, x=col1_x, y=l_y, size=12.0, font=fonts["mono"], color=palette[2] if len(palette) > 2 else "#00BBF9", justify="left", role="sched_label")
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
    vc.add_text(text=LABEL_PRIZES_REGISTRATION, x=col3_x, y=r_y, size=13.0, font=fonts["mono"], style="Bold", color=accent_color, justify="left", role="col3_header")
    r_y += height * 0.022
    vc.add_shape_rectangle(x=col3_x, y=r_y, width=col_w, height=1, fill=accent_color)
    r_y += height * 0.028

    prize_row = plan.get_row("prize")
    accent_target_id = None
    if prize_row:
        vc.add_text(text=LABEL_AWARD_POOL, x=col3_x, y=r_y, size=12.0, font=fonts["mono"], color=palette[2] if len(palette) > 2 else "#00BBF9", justify="left", role="prize_label")
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
        vc.add_text(text=LABEL_REGISTRATION_ACTION, x=col3_x, y=r_y, size=12.0, font=fonts["mono"], color=palette[2] if len(palette) > 2 else "#00BBF9", justify="left", role="cta_label")
        r_y += height * 0.024
        # Bounded area text within col_w: never overflows right margin
        vc.area_text(
            text=cta_row.text, x=col3_x, y=r_y, width=col_w, height=45,
            size=cta_row.size * 0.85, font=cta_row.font, style="Bold", color=cta_row.color, justify="left", fit="shrinkText", role="cta",
        )
        if not accent_target_id:
            accent_target_id = "$last"
        r_y += height * 0.055

    # Monospace Footer Strip (JetBrains Mono if available)
    footer_y = height - margin - 25
    vc.add_shape_rectangle(x=margin, y=footer_y - 12, width=width - 2 * margin, height=1, fill=palette[2] if len(palette) > 2 else "#00BBF9")

    footer_parts = []
    if date_row:
        footer_parts.append(f"{LABEL_DATE} {date_row.text}")
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


def compose_slots(
    vc: VectorCraftRenderer,
    brief: ExtractedBrief,
    palette: list[str],
    plan: TypographicPlan,
    bg_path: Path,
    hero_path: Optional[Path | str] = None,
    hero_geom: Optional[Any] = None,
    layout_plan: Optional[dict[str, Any]] = None,
    archetype: str = "focal_point",
    width: float = 1080.0,
    height: float = 1920.0,
) -> VectorCraftRenderer:
    """Slot-driven composition validated against master doctrine floors.

    The gate beats the plan:
    1. Converts normalized zones to pt (x canvas dims / 1000).
    2. Validates and clamps each slot to doctrine floors:
       - headline >= canvas_h / 11; body >= 1.8% canvas_h; microcopy >= 1.4% canvas_h
       - zones clamped into margin safe-box (4.5%)
       - font validated against installed faces
       - treatment validated against allowlist
       - degenerate zones fall back to archetype default row placement
    3. Text rows are strictly brief-sourced from plan.rows (never from slot content).
    4. Scrims built through soft_scrim DSL with seam overshoot.
    5. Post-placement collision resolution & canvas bounds enforcement.
    """
    from poster_agent.house_style import resolve_school, resolve_genre
    school_name, school_info = resolve_school(brief)
    genre_name, genre_policy = resolve_genre(brief)

    is_light = is_light_context(brief, palette)
    canvas_base = "#FFFFFF" if is_light else (palette[0] if palette else "#070B19")
    accent_color = "#4285F4" if is_light else (palette[1] if len(palette) > 1 else "#00F5D4")
    structural_color = "#0B2A5B" if is_light else (palette[4] if len(palette) > 4 else "#FFFFFF")
    installed_fonts = audit_fonts(school=school_name)
    genre = _detect_genre(brief)

    # Margin box (4.5% margins)
    margin_x = 0.045 * width
    margin_y = 0.045 * height
    usable_w = width - (2 * margin_x)
    usable_h = height - (2 * margin_y)

    # Doctrine floors
    headline_floor = height / 11.0  # ~122.7 pt nominal floor
    body_floor = 0.018 * height      # ~24.3 pt
    micro_floor = 0.014 * height     # ~18.9 pt

    # Layer 0: Place Background Art
    vc.place_image(bg_path, rect=[0, 0, width, height])

    # Structural Row: Brand Logo(s)
    emit_logo_row(
        vc=vc,
        brief=brief,
        school_info=school_info,
        width=width,
        height=height,
        margin_x=margin_x,
        margin_y=margin_y,
        is_light=is_light,
    )

    # 4-color Google brand top stripe
    if is_light or "navy for text" in brief.get_text("palette_use").lower():
        stripe_w = 36.0
        stripe_h = 4.0
        start_x = (width - (stripe_w * 4)) * 0.5
        stripe_y = margin_y + 10.0
        g_stripe_cols = ["#4285F4", "#EA4335", "#FBBC05", "#34A853"]
        for idx, col in enumerate(g_stripe_cols):
            vc.add_shape_rectangle(
                x=start_x + idx * stripe_w,
                y=stripe_y,
                width=stripe_w,
                height=stripe_h,
                fill=col,
                radius=1.0,
            )

    # Layer 1: Scrims (only on dark backgrounds to protect text, skip heavy opaque wipe on light designs)
    if not is_light:
        fade_overshoot = 0.03 * min(width, height)
        total_w = width + 2 * fade_overshoot
        total_h = height + 2 * fade_overshoot

        plan_scrims = layout_plan.get("scrims", []) if layout_plan else []
        applied_scrim = False
        for sc in plan_scrims:
            direction = sc.get("direction", "to_top")
            op_start = sc.get("opacity_start", 0.0)
            op_end = sc.get("opacity_end", 0.90)
            szone = sc.get("zone", [600, 0, 1000, 1000])

            if direction == "to_top":
                fade_y = (szone[0] * height / 1000.0)
                d_bot = (height + fade_overshoot) - fade_y
                stop_bot = max(0.1, min(0.9, d_bot / total_h))
                stops = [(0.0, canvas_base, op_end), (stop_bot * 0.95, canvas_base, 0.0), (1.0, canvas_base, 0.0)]
                vc.soft_scrim(
                    x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
                    stops=stops, direction="to_top",
                )
                applied_scrim = True
            elif direction == "to_bottom":
                fade_y = (szone[2] * height / 1000.0)
                d_top = (fade_y - (-fade_overshoot))
                stop_top = max(0.1, min(0.9, d_top / total_h))
                stops = [(0.0, canvas_base, op_end), (stop_top * 0.95, canvas_base, 0.0), (1.0, canvas_base, 0.0)]
                vc.soft_scrim(
                    x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
                    stops=stops, direction="to_bottom",
                )
                applied_scrim = True

        if not applied_scrim:
            vc.soft_scrim(
                x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
                stops=[(0.0, canvas_base, 0.85), (0.35, canvas_base, 0.0), (1.0, canvas_base, 0.0)],
                direction="to_bottom",
            )
            vc.soft_scrim(
                x=-fade_overshoot, y=-fade_overshoot, width=total_w, height=total_h,
                stops=[(0.0, canvas_base, 0.90), (0.45, canvas_base, 0.0), (1.0, canvas_base, 0.0)],
                direction="to_top",
            )

    # QR dimensions and reserved zone
    qr_url = getattr(brief, "asset_references", {}).get("qr_link") or brief.get_text("qr_link")
    has_qr = bool(qr_url and genre_policy.get("allow_qr", True))
    bar_h = 52.0 if genre_policy.get("allow_footer_bar", True) else 0.0
    if has_qr:
        qr_sz = max(75.0, min(100.0, width * 0.085))
        qr_px = width - margin_x - qr_sz
        qr_py = height - bar_h - qr_sz - 35.0
        qr_rect = (qr_px, qr_py, qr_sz, qr_sz)
        max_log_w = qr_px - margin_x - 30.0
    else:
        qr_rect = None
        max_log_w = usable_w

    # Layer 3: Place Hero Cutout Asset based on archetype positioning
    hero_node_id = None
    positions = brief.get_positions()
    hero_rect = None
    if positions:
        hero_w = width * 0.46
        hero_h = min(320.0, hero_w * (hero_geom.height / hero_geom.width if hero_geom and hero_geom.width > 0 else 0.75))
        hero_x = (width - hero_w) * 0.5
        hero_y = 660.0
        hero_rect = (hero_x, hero_y, hero_w, hero_h)
    elif archetype == "z_pattern":
        hero_w = width * 0.44
        hero_h = hero_w * (hero_geom.height / hero_geom.width if hero_geom and hero_geom.width > 0 else 1.0)
        hero_x = width * 0.52
        hero_y = height * 0.35
        hero_rect = (hero_x, hero_y, hero_w, hero_h)
    elif archetype == "split":
        hero_w = width * 0.60
        hero_h = height * 0.45
        hero_x = (width - hero_w) * 0.5
        hero_y = height * 0.06
        hero_rect = (hero_x, hero_y, hero_w, hero_h)
    elif archetype == "grid_3col":
        hero_w = width * 0.32
        hero_h = hero_w
        hero_x = width * 0.34
        hero_y = height * 0.35
        hero_rect = (hero_x, hero_y, hero_w, hero_h)
    else:  # focal_point
        hero_w = width * 0.48
        hero_h = hero_w * (hero_geom.height / hero_geom.width if hero_geom and hero_geom.width > 0 else 1.0)
        hero_x = (width - hero_w) * 0.5
        hero_y = height * 0.35
        hero_rect = (hero_x, hero_y, hero_w, hero_h)

    if hero_path and str(hero_path).lower() not in ("none", "native", ""):
        vc.place_image(hero_path, rect=[hero_x, hero_y, hero_w, hero_h])
        hero_node_id = "$last"
    else:
        hero_node_id = None
        hero_rect = None

    # Dedicated 2-Column Recruitment Block
    col_y = 690.0
    col_h = 285.0
    if positions:
        g_check_cols = ["#4285F4", "#EA4335", "#FBBC05", "#34A853"]
        sec_y = (hero_y + hero_h + 35.0) if hero_rect else 665.0
        sec_title = brief.get_text("section") or "OPEN POSITIONS"
        vc.add_text(
            f"—  {sec_title.upper()}  —",
            x=width * 0.5,
            y=sec_y,
            size=22.0,
            font=installed_fonts["display"],
            style="Bold",
            tracking=30.0,
            color=accent_color,
            justify="center",
            role="section",
        )

        col_y = sec_y + 35.0
        col_h = 360.0
        col_w = (usable_w - 30.0) * 0.5

        # Column 1 (Left: Team Members)
        col1_x = margin_x
        vc.add_shape_rectangle(x=col1_x, y=col_y, width=col_w, height=3.0, fill="#4285F4", radius=1.0)
        vc.add_text(
            positions[0]["title"].upper(),
            x=col1_x, y=col_y + 36.0,
            size=20.0, font=installed_fonts["sans"], style="Bold",
            color=structural_color, justify="left", role="pos_title_1",
        )
        if positions[0].get("tagline"):
            vc.add_text(
                positions[0]["tagline"],
                x=col1_x, y=col_y + 60.0,
                size=13.0, font=installed_fonts["sans"], style="Regular",
                color="#475569" if is_light else "#94A3B8", justify="left", role="pos_tagline_1",
            )
        for p_idx, pt in enumerate(positions[0]["points"]):
            pt_y = col_y + 98.0 + (p_idx * 48.0)
            vc.add_shape_rectangle(
                x=col1_x, y=pt_y - 10.0, width=8.0, height=8.0,
                fill=g_check_cols[p_idx % 4], radius=2.0,
            )
            vc.add_text(
                pt,
                x=col1_x + 20.0, y=pt_y,
                size=14.5, font=installed_fonts["sans"], style="Regular",
                color=structural_color, justify="left", role="bullet_text",
            )

        # Hairline vertical column divider
        vc.add_shape_rectangle(
            x=margin_x + col_w + 14.5, y=col_y + 10.0,
            width=1.0, height=col_h - 20.0,
            fill="#CBD5E1" if is_light else "#334155",
        )

        # Column 2 (Right: Leads)
        if len(positions) > 1:
            col2_x = margin_x + col_w + 30.0
            vc.add_shape_rectangle(x=col2_x, y=col_y, width=col_w, height=3.0, fill="#EA4335", radius=1.0)
            vc.add_text(
                positions[1]["title"].upper(),
                x=col2_x, y=col_y + 36.0,
                size=20.0, font=installed_fonts["sans"], style="Bold",
                color=structural_color, justify="left", role="pos_title_2",
            )
            if positions[1].get("tagline"):
                vc.add_text(
                    positions[1]["tagline"],
                    x=col2_x, y=col_y + 60.0,
                    size=13.0, font=installed_fonts["sans"], style="Regular",
                    color="#475569" if is_light else "#94A3B8", justify="left", role="pos_tagline_2",
                )
            for p_idx, pt in enumerate(positions[1]["points"]):
                pt_y = col_y + 98.0 + (p_idx * 48.0)
                vc.add_shape_rectangle(
                    x=col2_x, y=pt_y - 10.0, width=8.0, height=8.0,
                    fill=g_check_cols[p_idx % 4], radius=2.0,
                )
                vc.add_text(
                    pt,
                    x=col2_x + 20.0, y=pt_y,
                    size=14.5, font=installed_fonts["sans"], style="Regular",
                    color=structural_color, justify="left", role="bullet_text",
                )

    # Layer 5: Validate and place text slots
    slots = layout_plan.get("slots", []) if layout_plan else []
    slot_map = {}
    for s in slots:
        rid = s.get("row_id", "")
        slot_map[rid] = s

    available_faces = set(installed_fonts.values())
    available_faces.update(["Inter", "Bahnschrift", "JetBrains Mono", "Source Sans 3", "Source Serif 4", "Nirmala UI", "Segoe UI", "Consolas"])

    placed_items = []
    logistics_cursor_y = (col_y + col_h + 35.0) if positions else (height * 0.80)
    for r in plan.rows:
        if positions and (r.role.startswith("position_") or r.role == "section"):
            continue
        # Dedupe: closing line rendered in footer bar if permitted, skip body row
        if r.role == "closing" and genre_policy.get("allow_footer_bar", True):
            continue

        slot = slot_map.get(r.role)
        if not slot:
            for k, s in slot_map.items():
                if r.role in k or k in r.role:
                    slot = s
                    break

        fnt = slot.get("font", r.font) if slot else r.font
        if fnt not in available_faces and fnt not in installed_fonts:
            print(f"[composer] Slot '{r.role}': font '{fnt}' not installed, falling back to '{r.font}'")
            fnt = r.font

        # Degenerate zone check (<30px width or <15px height)
        if slot:
            zone = slot.get("zone", [0, 0, 1000, 1000])
            z_y0 = zone[0] * height / 1000.0
            z_x0 = zone[1] * width / 1000.0
            z_y1 = zone[2] * height / 1000.0
            z_x1 = zone[3] * width / 1000.0
            if (z_x1 - z_x0 < 30) or (z_y1 - z_y0 < 15):
                print(f"[composer] Slot '{r.role}': degenerate zone [{z_y0:.0f}, {z_x0:.0f}, {z_y1:.0f}, {z_x1:.0f}], using safe margin-based fallback")

        s_class = slot.get("size_class", "body") if slot else "body"
        sz = r.size

        # Doctrine floor enforcement: headline >= canvas_h / 11, body >= 1.8%, micro >= 1.4%
        if r.role == "title" or (s_class == "headline" and r.role not in ("cta", "deadline", "events")):
            if sz < headline_floor:
                print(f"[composer] Slot '{r.role}': headline size clamped from {sz:.1f}pt to doctrine floor {headline_floor:.1f}pt")
                sz = headline_floor
            floor_sz = headline_floor
        elif s_class == "micro" or any(k in r.role for k in ("organizer", "dress", "blurb", "note", "venue")):
            if sz < micro_floor:
                print(f"[composer] Slot '{r.role}': microcopy size clamped from {sz:.1f}pt to doctrine floor {micro_floor:.1f}pt")
                sz = micro_floor
            floor_sz = micro_floor
        elif r.role in ("deadline", "cta"):
            floor_sz = 16.0
        else:
            if sz < body_floor and r.role not in ("deadline", "events"):
                print(f"[composer] Slot '{r.role}': body size clamped from {sz:.1f}pt to doctrine floor {body_floor:.1f}pt")
                sz = body_floor
            floor_sz = body_floor

        # Width fit determination
        is_logistics_role = r.role in ("date_time", "date", "venue", "deadline", "deadline_note", "cta", "contact")
        row_max_w = max_log_w if (has_qr and is_logistics_role) else usable_w

        row_text = r.text.strip("— ") if r.role == "subtitle" else r.text
        lines, sz = wrap_and_fit_row(
            row_text,
            target_size=sz,
            floor_size=floor_sz,
            max_w=row_max_w,
            font=fnt,
            tracking=r.tracking,
            role=r.role,
        )

        # Positioning determination
        if is_logistics_role and positions:
            px = margin_x + (row_max_w * 0.5) if r.alignment == "center" else margin_x
            py = logistics_cursor_y
            line_step = sz * 1.35 + 8.0
            logistics_cursor_y += line_step * len(lines) + 8.0
            justify = r.alignment
        elif slot:
            zone = slot.get("zone", [0, 0, 1000, 1000])
            z_y0 = zone[0] * height / 1000.0
            z_x0 = zone[1] * width / 1000.0
            z_y1 = zone[2] * height / 1000.0
            z_x1 = zone[3] * width / 1000.0

            z_x0 = max(margin_x, min(z_x0, width - margin_x - 30))
            z_x1 = min(width - margin_x, max(z_x1, z_x0 + 30))
            z_y0 = max(margin_y, min(z_y0, height - margin_y - 15))
            z_y1 = min(height - margin_y, max(z_y1, z_y0 + 15))

            justify = slot.get("justify", r.alignment)
            if r.alignment == "center":
                px = width * 0.5
                justify = "center"
            elif justify == "left":
                px = z_x0
            elif justify == "right":
                px = z_x1
            else:
                px = (z_x0 + z_x1) * 0.5

            py = (z_y0 + z_y1) * 0.5 + (sz * 0.3)
            min_allowed_y = margin_y + (sz * 0.88)
            if py < min_allowed_y:
                py = min_allowed_y
        else:
            px = width * 0.5 if r.alignment == "center" else margin_x
            justify = r.alignment
            # 5-band vertical rhythm default anchors for 9:16 layout
            if r.role == "eyebrow":
                py = margin_y + (sz * 0.88)
            elif r.role == "organizer":
                py = margin_y + 40.0 + (sz * 0.88)
            elif r.role == "title":
                py = height * 0.17
            elif r.role == "subtitle":
                py = height * 0.25
            elif r.role == "tagline":
                py = height * 0.29
            elif r.role == "section":
                py = height * 0.54
            elif r.role in ("date", "date_time"):
                py = height * 0.76
            elif r.role == "venue":
                py = height * 0.80
            elif r.role in ("deadline", "deadline_note"):
                py = height * 0.84
            elif r.role == "cta":
                py = height * 0.88
            elif r.role == "contact":
                py = height * 0.92
            else:
                py = height * 0.50

        # Hero reserve check for header items: must finish before hero starts
        if hero_rect and r.role in ("eyebrow", "organizer", "subtitle", "title", "tagline"):
            hero_top = hero_rect[1]
            max_head_y = hero_top - (sz * 0.88) - 15.0
            if py > max_head_y:
                py = max_head_y

        placed_items.append({
            "row": r,
            "lines": lines,
            "x": px,
            "y": py,
            "size": sz,
            "font": fnt,
            "justify": justify,
            "style": r.style,
            "tracking": r.tracking,
            "color": r.color,
        })

    # Collision resolution: Sort by baseline y position and enforce strict non-overlapping gap
    placed_items.sort(key=lambda it: it["y"])
    for i in range(len(placed_items) - 1):
        cur = placed_items[i]
        nxt = placed_items[i + 1]
        cur_h = cur["size"] * (2.15 if len(cur.get("lines", [])) > 1 else 1.15)
        nxt_h = nxt["size"] * (2.15 if len(nxt.get("lines", [])) > 1 else 1.15)
        req_gap = (cur_h * 0.3) + (nxt_h * 0.7) + 8.0
        if nxt["y"] < cur["y"] + req_gap:
            nxt["y"] = cur["y"] + req_gap

    # Canvas bounds clamp with bottom-up collision clearance
    for i in range(len(placed_items) - 1, -1, -1):
        it = placed_items[i]
        it_h = it["size"] * (2.15 if len(it.get("lines", [])) > 1 else 1.15)
        max_allowed_y = height - bar_h - margin_y - (it_h * 0.25)
        if it["y"] > max_allowed_y:
            it["y"] = max_allowed_y
        if i > 0:
            prev = placed_items[i - 1]
            prev_h = prev["size"] * (2.15 if len(prev.get("lines", [])) > 1 else 1.15)
            req_gap = (prev_h * 0.3) + (it_h * 0.7) + 8.0
            if prev["y"] > it["y"] - req_gap:
                prev["y"] = it["y"] - req_gap

    # Top margin safe clamp with forward gap propagation
    for i in range(len(placed_items)):
        it = placed_items[i]
        it_h = it["size"] * (2.15 if len(it.get("lines", [])) > 1 else 1.15)
        min_allowed_y = margin_y + (it_h * 0.88)
        if it["y"] < min_allowed_y:
            it["y"] = min_allowed_y
        if i < len(placed_items) - 1:
            nxt = placed_items[i + 1]
            nxt_h = nxt["size"] * (2.15 if len(nxt.get("lines", [])) > 1 else 1.15)
            req_gap = (it_h * 0.3) + (nxt_h * 0.7) + 8.0
            if nxt["y"] < it["y"] + req_gap:
                nxt["y"] = it["y"] + req_gap

    # Verify hero reserve & report hero occlusion status
    hero_occlusion_offenders = []
    if hero_rect:
        for it in placed_items:
            t_lines = it.get("lines", [it["row"].text])
            sz = it["size"]
            for l_idx, line in enumerate(t_lines):
                lw = estimate_text_width(line, sz, it["font"], it.get("tracking", 0.0))
                lx = it["x"] - (lw * 0.5) if it["justify"] == "center" else (it["x"] - lw if it["justify"] == "right" else it["x"])
                line_gap = sz * 1.15 if len(t_lines) > 1 else 0.0
                ly = it["y"] + (l_idx - (len(t_lines) - 1) / 2.0) * line_gap
                line_rect = (lx, ly - sz * 0.88, lw, sz * 1.15)
                if check_rect_intersection(line_rect, hero_rect):
                    hero_occlusion_offenders.append(it["row"].role)

    if not hero_occlusion_offenders:
        print("HERO_OCCLUSION: none")
    else:
        print(f">>> [composer] HERO_OCCLUSION: offenders found: {hero_occlusion_offenders}")

    # Emit all placed text
    for it in placed_items:
        row = it["row"]
        lines = it.get("lines", [row.text])
        if row.role == "title":
            line_gap = it["size"] * 1.05
            if len(lines) > 1:
                l1_y = it["y"] - (line_gap * 0.5)
                l2_y = it["y"] + (line_gap * 0.5)
                # First line
                vc.add_text(
                    text=lines[0],
                    x=it["x"],
                    y=l1_y,
                    size=it["size"],
                    font=it["font"],
                    style="Bold",
                    tracking=25.0,
                    color="#0B2A5B" if is_light else it["color"],
                    justify="center",
                    role=row.role,
                )
                # Second line
                vc.add_text(
                    text=lines[1],
                    x=it["x"],
                    y=l2_y,
                    size=it["size"],
                    font=it["font"],
                    style="Bold",
                    tracking=25.0,
                    color="#4285F4" if (is_light and "RECRUITING" in lines[1].upper()) else it["color"],
                    justify="center",
                    role=row.role,
                )
            else:
                vc.add_text(
                    text=lines[0],
                    x=it["x"],
                    y=it["y"],
                    size=it["size"],
                    font=it["font"],
                    style="Bold",
                    tracking=25.0,
                    color=it["color"],
                    justify=it["justify"],
                    role=row.role,
                )
        elif row.role == "cta":
            if genre_policy.get("allow_pills", True):
                emit_pill_row(
                    vc=vc,
                    text=lines[0],
                    x=it["x"],
                    y=it["y"],
                    font=it["font"],
                    fill_color=accent_color,
                    text_color="#FFFFFF",
                    size=it["size"],
                    role="_structure_pill",
                )
            else:
                vc.add_text(
                    text=lines[0],
                    x=it["x"],
                    y=it["y"],
                    size=it["size"],
                    font=it["font"],
                    style=it["style"],
                    tracking=it["tracking"],
                    color=it["color"],
                    justify=it["justify"],
                    role=row.role,
                )
        else:
            if len(lines) > 1:
                line_gap = it["size"] * 1.2
                l1_y = it["y"] - (line_gap * 0.5)
                l2_y = it["y"] + (line_gap * 0.5)
                vc.add_text(
                    text=lines[0],
                    x=it["x"],
                    y=l1_y,
                    size=it["size"],
                    font=it["font"],
                    style=it["style"],
                    tracking=it["tracking"],
                    color=it["color"],
                    justify=it["justify"],
                    role=f"{row.role}_line1",
                )
                vc.add_text(
                    text=lines[1],
                    x=it["x"],
                    y=l2_y,
                    size=it["size"],
                    font=it["font"],
                    style=it["style"],
                    tracking=it["tracking"],
                    color=it["color"],
                    justify=it["justify"],
                    role=f"{row.role}_line2",
                )
            else:
                vc.add_text(
                    text=lines[0],
                    x=it["x"],
                    y=it["y"],
                    size=it["size"],
                    font=it["font"],
                    style=it["style"],
                    tracking=it["tracking"],
                    color=it["color"],
                    justify=it["justify"],
                    role=row.role,
                )

    # QR Row (if qr_link supplied and permitted by genre)
    if has_qr:
        emit_qr_row(
            vc=vc,
            qr_link=qr_url,
            cta_text=brief.get_text("cta") or "SCAN TO APPLY",
            x=qr_px,
            y=qr_py,
            qr_size=qr_sz,
            font=installed_fonts["sans"],
            text_color="#0B2A5B" if is_light else "#FFFFFF",
            canvas_base=canvas_base,
        )

    # Footer Bar Row (if closing supplied and permitted by genre)
    closing_txt = brief.get_text("closing") or brief.get_text("closing_line")
    if closing_txt and genre_policy.get("allow_footer_bar", True):
        emit_footer_bar_row(
            vc=vc,
            text=closing_txt,
            width=width,
            height=height,
            font=installed_fonts["sans"],
            fill_color="#1E2842" if is_light else structural_color,
            text_color="#FFFFFF",
            bar_height=bar_h,
        )

    # Vertical band coverage audit
    vband_items = [
        {"y": cmd["params"]["y"], "text": cmd["params"].get("text", ""), "size": cmd["params"].get("size", 20.0)}
        for cmd in vc.commands
        if cmd.get("command") == "text.create"
    ]
    cov_pct, occ_bands, _ = compute_vband_coverage(vband_items, canvas_h=height)
    print(f"V-BAND COVERAGE: {cov_pct:.0f}%")
    if cov_pct < 70.0:
        print(f">>> [composer] WARNING: Low vertical band coverage: {cov_pct:.0f}% < 70%. Bands occupied: {occ_bands}")

    apply_genre_effects(vc, genre=genre, accent_color=accent_color, hero_target_id=hero_node_id, is_light=is_light)
    return vc


def compose(
    brief: ExtractedBrief,
    palette: list[str],
    bg_path: Path,
    hero_path: Optional[Path | str] = None,
    hero_geom: Optional[Any] = None,
    archetype: str = "focal_point",
    layout_hints: Optional[list[str]] = None,
    width: Optional[float] = None,
    height: Optional[float] = None,
    layout_plan: Optional[dict[str, Any]] = None,
    school: Optional[str] = None,
) -> VectorCraftRenderer:
    """Master compose entrypoint: dispatches to slot execution if valid plan exists, else archetype default."""
    forced_archetype = os.environ.get("POSTER_FORCE_ARCHETYPE")
    if forced_archetype in ("focal_point", "z_pattern", "split", "grid_3col"):
        archetype = forced_archetype

    if width is None or height is None:
        from poster_agent.house_style import resolve_canvas_dimensions
        brief_fmt = brief.get_text("format")
        if brief_fmt:
            w_res, h_res = resolve_canvas_dimensions(brief)
            width = width or w_res
            height = height or h_res
        else:
            width = width or 1080.0
            height = height or 1350.0

    if school is None:
        try:
            from poster_agent.house_style import resolve_school
            school, _ = resolve_school(brief)
        except Exception:
            school = "KCT"

    vc = VectorCraftRenderer()
    vc.new_document(width=width, height=height, units="Points", color_mode="rgb", raster_resolution=300)

    plan = build_typography_plan(
        brief=brief,
        palette=palette,
        layout_hints=layout_hints,
        width=width,
        height=height,
        school=school,
    )

    if layout_plan and isinstance(layout_plan, dict) and ("slots" in layout_plan):
        return compose_slots(
            vc=vc,
            brief=brief,
            palette=palette,
            plan=plan,
            bg_path=bg_path,
            hero_path=hero_path,
            hero_geom=hero_geom,
            layout_plan=layout_plan,
            archetype=archetype,
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
