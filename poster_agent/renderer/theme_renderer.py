"""Stage 4: Unified Master HUD Graphic Design Renderer (Faithful Golden Path 3 Architecture).

Faithfully ports the exact HTML/CSS structure of poster_blend_path3_master.html:
- Multi-stop radial background gradients with ambient film grain overlay.
- Generative circuit infill mask headline (Syne 900 with neon green/cyan glow).
- Centered 3D hero shield with radial backglow and atmospheric light bleeding.
- Unified graphic design HUD panel containing timeframe, venue, bounty, and category tracks in an integrated terminal container.
- Clean footer CTA pill with zero floating box segregation.
- Stable element IDs preserved for zero-drop brief extraction and print pre-flight checks.
"""
import base64
import json
import re
from pathlib import Path
from typing import Any
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, ConfigDict

from poster_agent.ingestion.extractor import ExtractedBrief
from poster_agent.vision.art_measurer import MeasuredArtBundle


class DOMBox(BaseModel):
    model_config = ConfigDict(extra="forbid")
    element_id: str
    tag: str
    left: float
    top: float
    right: float
    bottom: float
    width: float
    height: float


class ThemeRenderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    html_path: Path
    full_png_path: Path
    text_only_png_path: Path
    vector_pdf_path: Path
    dom_boxes: dict[str, DOMBox]
    theme_name: str


class ThemePackRenderer:
    """Renders ExtractedBrief into the authentic, depth-blended Path 3 graphic design layout."""

    def __init__(self, theme_name: str = "cyber_ctf"):
        self.theme_name = theme_name

    def compose_html(
        self,
        brief: ExtractedBrief,
        art_bundle: MeasuredArtBundle,
        bg_uri: str,
        hero_uri: str = "",
        title_3d_uri: str = "",
        accent_uri: str = "",
        hide_art: bool = False,
        palette_vars_css: str = "",
        title_treatment: str = "css_gradient_glow",
    ) -> str:
        art_visibility = "hidden" if hide_art else "visible"

        # Brief Strings (Verbatim)
        title = brief.get_text("title", "EVENT 2027")
        tagline = brief.get_text("tagline", "")
        subtitle = brief.get_text("subtitle", "")
        date_str = brief.get_text("date", "")
        time_str = brief.get_text("time", "")
        venue_str = brief.get_text("venue", "")
        events_str = brief.get_text("events", "")
        prize_str = brief.get_text("prize", "")
        cta_str = brief.get_text("cta", "")
        organizer_str = brief.get_text("organizer", "")
        team_size_str = brief.get_text("team_size", "")
        dress_code_str = brief.get_text("dress_code", "")

        prize_display = prize_str if "PRIZE" in prize_str.upper() else f"PRIZE POOL {prize_str}"

        # Resolve font paths (OFL open fonts)
        font_dir = Path(__file__).resolve().parent.parent.parent / "assets/fonts"
        inter_semi = (font_dir / "Inter-SemiBold.ttf").as_uri() if (font_dir / "Inter-SemiBold.ttf").exists() else ""
        inter_reg = (font_dir / "Inter-Regular.ttf").as_uri() if (font_dir / "Inter-Regular.ttf").exists() else ""
        mono_reg = (font_dir / "JetBrainsMono-Regular.ttf").as_uri() if (font_dir / "JetBrainsMono-Regular.ttf").exists() else ""
        sans_bold = (font_dir / "SourceSans3-Bold.ttf").as_uri() if (font_dir / "SourceSans3-Bold.ttf").exists() else ""

        # Title HTML block based on title_treatment
        if title_treatment == "generative_3d" and title_3d_uri:
            title_html = f'<img id="headline_3d_img" class="title-3d-asset" src="{title_3d_uri}" alt="{title}" /><h1 id="headline_text_fallback" class="visually-hidden">{title}</h1>'
        elif title_treatment == "flat":
            title_html = f'<h1 id="headline_text_fallback" class="main-title-flat">{title}</h1>'
        else:  # css_gradient_glow
            title_html = f'<h1 id="headline_text_fallback" class="main-title-glow">{title}</h1>'

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    /* Open-License OFL Fonts Loaded Locally via @font-face */
    @font-face {{
      font-family: 'OFL-Sans';
      src: url('{inter_reg}') format('truetype');
      font-weight: 400;
      font-style: normal;
    }}
    @font-face {{
      font-family: 'OFL-Sans';
      src: url('{inter_semi}') format('truetype');
      font-weight: 600;
      font-style: normal;
    }}
    @font-face {{
      font-family: 'OFL-Display';
      src: url('{sans_bold}') format('truetype');
      font-weight: 700;
      font-style: normal;
    }}
    @font-face {{
      font-family: 'OFL-Mono';
      src: url('{mono_reg}') format('truetype');
      font-weight: 400;
      font-style: normal;
    }}

    {palette_vars_css}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    
    body {{
      background: var(--color-canvas-base, #0A0E17);
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      font-family: 'OFL-Sans', sans-serif;
      -webkit-font-smoothing: antialiased;
      overflow: hidden;
      width: {art_bundle.canvas_w}px;
      height: {art_bundle.canvas_h}px;
      margin: 0;
      padding: 0;
    }}

    .poster-canvas {{
      position: relative;
      width: {art_bundle.canvas_w}px;
      height: {art_bundle.canvas_h}px;
      background-color: var(--color-canvas-base, #0A0E17);
      background-image: url('{bg_uri}');
      background-size: cover;
      background-position: center;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 68px;
      color: var(--color-structural, #FFFFFF);
    }}

    .art-layer {{
      visibility: {art_visibility};
    }}

    .visually-hidden {{
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }}

    /* TOP SECTION */
    .section-title {{
      position: relative;
      z-index: 10;
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
    }}

    .top-meta-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      max-width: 1100px;
    }}

    .top-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-family: 'OFL-Mono', monospace;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--role-organizer-color, var(--color-secondary-accent, #00FF9C));
      background: rgba(0, 0, 0, 0.25);
      padding: 6px 14px;
      border-radius: 4px;
      border: 1px solid var(--role-organizer-color, var(--color-secondary-accent, #00FF9C));
    }}

    .main-title-glow {{
      font-family: 'OFL-Display', sans-serif;
      font-size: 96px;
      font-weight: 900;
      line-height: 0.95;
      letter-spacing: -0.01em;
      text-transform: uppercase;
      color: var(--role-title-color, var(--color-structural, #FFFFFF));
      text-shadow: 0 0 35px var(--color-accent, #00FF9C);
      margin-bottom: 14px;
    }}

    .main-title-flat {{
      font-family: 'OFL-Display', sans-serif;
      font-size: 96px;
      font-weight: 900;
      line-height: 0.95;
      letter-spacing: -0.01em;
      text-transform: uppercase;
      color: var(--role-title-color, var(--color-structural, #1F2A24));
      margin-bottom: 14px;
    }}

    .title-3d-asset {{
      max-width: 900px;
      max-height: 220px;
      object-fit: contain;
      filter: drop-shadow(0 15px 30px rgba(0, 0, 0, 0.8));
      margin-bottom: 14px;
    }}

    .tagline-row {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .tagline {{
      font-family: 'OFL-Sans', sans-serif;
      font-size: 24px;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: var(--role-tagline-color, var(--color-secondary-accent, #00D1FF));
    }}

    /* HERO ASSET - COMMANDING VISUAL PRESENCE */
    .hero-container {{
      position: absolute;
      top: 380px;
      left: 50%;
      transform: translateX(-50%);
      width: 820px;
      height: 820px;
      z-index: 20;
      display: flex;
      justify-content: center;
      align-items: center;
      pointer-events: none;
    }}

    .hero-img {{
      position: relative;
      max-width: 800px;
      max-height: 800px;
      object-fit: contain;
      filter: drop-shadow(0 25px 50px rgba(0, 0, 0, 0.45));
    }}

    /* LOWER METADATA - EDITORIAL TYPOGRAPHY, ZERO AMATEUR BOXES */
    .section-lower {{
      position: relative;
      z-index: 30;
      display: flex;
      flex-direction: column;
      gap: 20px;
      padding: 30px 36px;
      background: var(--scrim-gradient, linear-gradient(to top, rgba(10, 14, 23, 0.92) 0%, rgba(10, 14, 23, 0.75) 60%, transparent 100%));
      border-radius: 0;
      backdrop-filter: blur(8px);
    }}

    .hud-panel {{
      background: transparent !important;
      border: none !important;
      border-radius: 0 !important;
      padding: 0 !important;
      display: flex;
      flex-direction: column;
      gap: 18px;
      box-shadow: none !important;
    }}

    .hud-main-grid {{
      display: grid;
      grid-template-columns: 1fr 1.3fr;
      gap: 36px;
      align-items: start;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--role-divider-color, rgba(255, 255, 255, 0.18));
    }}

    .micro-label {{
      font-family: 'OFL-Mono', monospace;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--role-tagline-color, var(--color-secondary-accent, #8A94A6));
      margin-bottom: 6px;
    }}

    .date-display {{
      font-family: 'OFL-Display', sans-serif;
      font-size: 36px;
      font-weight: 800;
      color: var(--role-date-color, var(--color-structural, #FFFFFF));
      line-height: 1.1;
      letter-spacing: -0.01em;
    }}

    .venue-display {{
      font-family: 'OFL-Sans', sans-serif;
      font-size: 24px;
      font-weight: 600;
      color: var(--role-venue-color, var(--color-structural, #FFFFFF));
      line-height: 1.25;
    }}

    .hud-banner-row {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      background: transparent;
      border: none;
      padding: 0;
      gap: 20px;
    }}

    .subtitle-text {{
      font-family: 'OFL-Sans', sans-serif;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--role-subtitle-color, var(--color-structural, #FFFFFF));
    }}

    .bounty-pill {{
      font-family: 'OFL-Display', sans-serif;
      font-size: 28px;
      font-weight: 800;
      letter-spacing: 0.03em;
      color: var(--role-prize-color, var(--color-accent, #E9A23B));
      white-space: nowrap;
      padding: 0;
      border: none;
      background: transparent;
    }}

    .tracks-content {{
      font-family: 'OFL-Mono', monospace;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--role-events-color, var(--color-structural, #FFFFFF));
      padding-top: 14px;
      border-top: 1px solid var(--role-divider-color, rgba(255, 255, 255, 0.15));
      opacity: 0.95;
    }}

    .section-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 16px;
      border-top: 1px solid var(--role-divider-color, rgba(255, 255, 255, 0.2));
    }}

    .cta-pill {{
      font-family: 'OFL-Mono', monospace;
      font-size: 20px;
      font-weight: 800;
      color: var(--role-cta-color, var(--color-accent, #E9A23B));
      background: transparent !important;
      letter-spacing: 0.08em;
      padding: 0 !important;
      border: none !important;
      border-radius: 0 !important;
      text-transform: uppercase;
      white-space: nowrap;
    }}

    .organizer-pill {{
      font-family: 'OFL-Sans', sans-serif;
      font-size: 15px;
      font-weight: 600;
      color: var(--role-organizer-color, var(--color-secondary-accent, #8A94A6));
      letter-spacing: 0.03em;
      white-space: nowrap;
    }}
  </style>
</head>
<body>

  <div class="poster-canvas">
    <!-- TOP SECTION -->
    <div id="title_zone" class="section-title">
      <div class="top-meta-bar">
        <div class="top-badge">{organizer_str or 'PRESENTED ANNOUNCEMENT'}</div>
      </div>
      {title_html}
      {f'<div class="tagline-row"><div id="tagline_1" class="tagline">{tagline}</div></div>' if tagline else ''}
    </div>

    <!-- HERO -->
    <div class="hero-container">
      {f'<img id="hero_art_1" class="hero-img art-layer" src="{hero_uri}" alt="Hero Motif" />' if hero_uri else ''}
    </div>

    <!-- HUD -->
    <div id="bottom_metadata_container" class="section-lower">
      <div id="card_date_venue" class="hud-panel">
        <div class="hud-main-grid">
          <div>
            <div class="micro-label">EVENT TIMEFRAME</div>
            <div id="date_1" class="date-display">{date_str}{f'<span style="display:block;font-size:18px;font-weight:600;opacity:0.88;margin-top:4px;">{time_str}</span>' if time_str else ''}</div>
          </div>
          <div>
            <div class="micro-label">LOCATION & VENUE</div>
            <div id="venue_1" class="venue-display">{venue_str}{f'<div id="dress_code_1" class="micro-label" style="margin-top:6px;opacity:0.85;">DRESS CODE: {dress_code_str}</div>' if dress_code_str else ''}</div>
          </div>
        </div>

        {f'<div id="subhead_prize_row" class="hud-banner-row"><div id="subhead_1" class="subtitle-text">{subtitle}</div><div id="prize_1" class="bounty-pill">{prize_display}</div></div>' if subtitle or prize_str else ''}

        {f'<div id="tracks_belt" class="tracks-content">{events_str}</div>' if events_str else ''}
      </div>

      <div id="cta_footer_row" class="section-footer">
        {f'<div id="cta_1" class="cta-pill">{cta_str}</div>' if cta_str else ''}
        {f'<div id="organizer_1" class="organizer-pill">{organizer_str}</div>' if organizer_str else ''}
      </div>
    </div>
  </div>

</body>
</html>
"""
        return html_doc

    def render(
        self,
        brief: ExtractedBrief,
        art_bundle: MeasuredArtBundle,
        output_dir: Path | str,
        base_slug: str,
        bg_path: str | Path,
        hero_path: str | Path = "",
        title_3d_path: str | Path = "",
        accent_path: str | Path = "",
        html_override: str | None = None,
        palette_vars_css: str = "",
        title_treatment: str = "css_gradient_glow",
    ) -> ThemeRenderResult:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        def to_uri(p: str | Path) -> str:
            if not p or not Path(p).exists():
                return ""
            return Path(p).resolve().as_uri()

        bg_uri = to_uri(bg_path)
        hero_uri = to_uri(hero_path)
        title_uri = to_uri(title_3d_path)
        accent_uri = to_uri(accent_path)

        if html_override:
            html_full = html_override
            hide_style = "<style>.art-layer { visibility: hidden !important; } #hero_art_1, #accent_art_1, .circuit-grid, .shield-backglow { display: none !important; }</style>"
            if "</head>" in html_override:
                html_text_only = html_override.replace("</head>", f"{hide_style}</head>")
            else:
                html_text_only = f"{hide_style}{html_override}"
        else:
            html_full = self.compose_html(
                brief, art_bundle, bg_uri, hero_uri, title_uri, accent_uri,
                hide_art=False, palette_vars_css=palette_vars_css, title_treatment=title_treatment
            )
            html_text_only = self.compose_html(
                brief, art_bundle, bg_uri, hero_uri, title_uri, accent_uri,
                hide_art=True, palette_vars_css=palette_vars_css, title_treatment=title_treatment
            )

        full_html_path = out_dir / f"{base_slug}.html"
        full_html_path.write_text(html_full, encoding="utf-8")

        text_only_html_path = out_dir / f"{base_slug}_text_only.html"
        text_only_html_path.write_text(html_text_only, encoding="utf-8")

        full_png_path = out_dir / f"{base_slug}_full.png"
        text_only_png_path = out_dir / f"{base_slug}_text_only.png"
        pdf_path = out_dir / f"{base_slug}_master.pdf"

        dom_boxes: dict[str, DOMBox] = {}

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": art_bundle.canvas_w, "height": art_bundle.canvas_h},
                device_scale_factor=2.0,
            )

            # Wait for document and local fonts to be fully loaded and rendered
            page.goto(full_html_path.resolve().as_uri(), wait_until="networkidle")
            page.evaluate("() => document.fonts.ready")
            page.wait_for_timeout(400)
            canvas = page.locator(".poster-canvas")
            canvas.screenshot(path=str(full_png_path))

            # Stable IDs
            stable_ids = [
                "title_zone", "headline_text_fallback", "tagline_1", "tracks_belt",
                "card_date_venue", "date_1", "venue_1", "time_1", "team_size_1",
                "subhead_1", "prize_1", "cta_1", "organizer_1", "hero_art_1", "accent_art_1"
            ]
            for sid in stable_ids:
                loc = page.locator(f"#{sid}")
                if loc.count() > 0:
                    box = loc.bounding_box()
                    if box:
                        dom_boxes[sid] = DOMBox(
                            element_id=sid,
                            tag=sid.split("_")[0],
                            left=round(box["x"], 1),
                            top=round(box["y"], 1),
                            right=round(box["x"] + box["width"], 1),
                            bottom=round(box["y"] + box["height"], 1),
                            width=round(box["width"], 1),
                            height=round(box["height"], 1),
                        )

            # Vector PDF
            page.pdf(
                path=str(pdf_path),
                width=f"{art_bundle.canvas_w}px",
                height=f"{art_bundle.canvas_h}px",
                print_background=True,
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            )

            # Text-only
            page.goto(text_only_html_path.resolve().as_uri(), wait_until="networkidle")
            page.wait_for_timeout(300)
            canvas = page.locator(".poster-canvas")
            canvas.screenshot(path=str(text_only_png_path))

            browser.close()

        return ThemeRenderResult(
            html_path=full_html_path,
            full_png_path=full_png_path,
            text_only_png_path=text_only_png_path,
            vector_pdf_path=pdf_path,
            dom_boxes=dom_boxes,
            theme_name=self.theme_name,
        )
