"""Stage 4: Theme Pack Renderer with Method 3 Generative Texture Infill & Depth Blending.

Implements the "Art First, Vision-Assisted Layout Second" architecture:
- Circuit Infill Mask: Background circuit traces flow through headline letterforms with neon vector strokes.
- Intentional 3D Z-Overlap: Headline sits at z-index: 5; Hero Shield sits at z-index: 10 overlapping title base.
- Atmospheric Multi-stop Scrim: Text sits directly in atmospheric lighting with glowing HUD borders (no harsh isolated floating boxes).
- Screen-Blended Light Spill: Emits radiant emerald-cyan atmosphere behind hero asset.
- Film Grain & Radial Color Grading: Mathematically unifies all raster and vector elements.
- Stable Element IDs: Every typography element maintains a stable ID for deterministic audits and typed patching.
"""
import base64
import json
import re
from pathlib import Path
from typing import Any
from PIL import Image
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, ConfigDict, Field

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
    """Renders ExtractedBrief and MeasuredArt using Method 3 depth-blended compositing."""

    def __init__(self, theme_name: str = "cyber_ctf"):
        self.theme_name = theme_name

    def compose_html(
        self,
        brief: ExtractedBrief,
        art_bundle: MeasuredArtBundle,
        bg_data_uri: str,
        hero_data_uri: str = "",
        title_3d_data_uri: str = "",
        accent_data_uri: str = "",
        hide_art: bool = False,
    ) -> str:
        """Compose HTML with Method 3 texture infill, depth overlap, and atmospheric scrim."""
        art_visibility = "hidden" if hide_art else "visible"

        # Extract fields verbatim from brief
        title = brief.get_text("title", "NOVA CTF 2026")
        tagline = brief.get_text("tagline", "")
        subtitle = brief.get_text("subtitle", "")
        date_str = brief.get_text("date", "")
        time_str = brief.get_text("time", "")
        venue_str = brief.get_text("venue", "")
        events_str = brief.get_text("events", "")
        prize_str = brief.get_text("prize", "")
        cta_str = brief.get_text("cta", "REGISTER NOW")
        contact_str = brief.get_text("contact", "")
        hashtag_str = brief.get_text("hashtag", "")
        organizer_str = brief.get_text("organizer", "")
        team_size_str = brief.get_text("team_size", "")

        # Parse tournament categories
        event_items = [e.strip() for e in re.split(r"[|,]", events_str) if e.strip()] if events_str else []
        tracks_badges_html = "".join(f'<div class="track-badge">{item}</div>' for item in event_items)

        # Dynamic hero size and position based on measured art bounds (commanding focal point)
        if art_bundle.hero_geometry:
            hero_top = 285
            hero_size = max(520, min(720, int(art_bundle.hero_geometry.width * 0.95)))
        else:
            hero_top = 295
            hero_size = 580

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title} - Method 3 Depth-Blended Composition</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700;800&family=Space+Grotesk:wght@600;700;800;900&family=Syne:wght@800;900&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    
    :root {{
      --title-top: 65px;
      --hero-top: {hero_top}px;
      --hero-size: {hero_size}px;
      --metadata-bottom: 55px;
      --accent-color: #00FF66;
      --highlight-color: #00F3FF;
      --gold-color: #FFB703;
      --danger-color: #FF4D6D;
      --text-main: #FFFFFF;
      --text-muted: #8EA4C8;
    }}

    body {{
      background: #050811;
      width: {art_bundle.canvas_w}px;
      height: {art_bundle.canvas_h}px;
      margin: 0;
      padding: 0;
      font-family: 'Space Grotesk', sans-serif;
      -webkit-font-smoothing: antialiased;
      overflow: hidden;
    }}

    .poster-canvas {{
      position: relative;
      width: {art_bundle.canvas_w}px;
      height: {art_bundle.canvas_h}px;
      overflow: hidden;
      color: var(--text-main);
      background-color: #050811;
    }}

    /* ART LAYERS (Visibility toggleable for text-alone occlusion checks) */
    .art-layer {{
      visibility: {art_visibility};
    }}

    /* LAYER 0: BACKGROUND CIRCUIT MOTHERBOARD */
    #layer_background {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      background-image: url('{bg_data_uri}');
      background-size: cover;
      background-position: center top;
      z-index: 1;
    }}

    /* TACTICAL GRID OVERLAY */
    .circuit-grid {{
      position: absolute;
      inset: 0;
      background-size: 54px 54px;
      background-image: 
        linear-gradient(to right, rgba(0, 255, 102, 0.04) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(0, 243, 255, 0.04) 1px, transparent 1px);
      pointer-events: none;
      z-index: 2;
    }}

    /* LAYER 1: SCREEN-BLENDED LIGHT SPILL EMITTER */
    #hero_light_spill {{
      position: absolute;
      top: calc(var(--hero-top) + 260px);
      left: 50%;
      transform: translate(-50%, -50%);
      width: 1000px;
      height: 1000px;
      background: radial-gradient(circle, 
        rgba(0, 255, 102, 0.38) 0%, 
        rgba(0, 243, 255, 0.24) 40%, 
        rgba(5, 8, 17, 0.1) 68%,
        transparent 80%);
      filter: blur(70px);
      mix-blend-mode: screen;
      pointer-events: none;
      z-index: 3;
    }}

    /* ACCENT ART (OPTIONAL HOLOGRAPHIC FLAG AT TOP RIGHT) */
    #accent_art_1 {{
      position: absolute;
      top: 45px;
      right: 45px;
      width: 220px;
      height: 220px;
      object-fit: contain;
      z-index: 6;
      transform: rotate(-3deg);
      mix-blend-mode: screen;
      filter: drop-shadow(0 0 25px rgba(0, 255, 102, 0.65)) drop-shadow(0 0 40px rgba(0, 243, 255, 0.45));
      pointer-events: none;
    }}

    /* LAYER 2: METHOD 3 GENERATIVE TEXTURE INFILL HEADLINE (Z-INDEX: 5) */
    #title_zone {{
      position: absolute;
      top: var(--title-top);
      left: 50px;
      right: 50px;
      z-index: 5;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }}

    .top-telemetry-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      max-width: 1100px;
      margin-bottom: 8px;
    }}

    .telemetry-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.20em;
      text-transform: uppercase;
      color: var(--accent-color);
      background: rgba(0, 255, 102, 0.08);
      padding: 6px 14px;
      border-radius: 4px;
      border: 1px solid rgba(0, 255, 102, 0.30);
      text-shadow: 0 0 10px rgba(0, 255, 102, 0.5);
    }}
    .telemetry-badge::before {{
      content: "";
      width: 7px;
      height: 7px;
      background: var(--accent-color);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--accent-color);
    }}

    .telemetry-status {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      font-weight: 700;
      color: var(--highlight-color);
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }}

    #tagline_1 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 24px;
      font-weight: 700;
      color: var(--highlight-color);
      letter-spacing: 0.06em;
      text-shadow: 0 0 18px rgba(0, 243, 255, 0.6);
      margin-bottom: 4px;
    }}

    #headline_zone {{
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 100%;
    }}

    /* METHOD 3 CIRCUIT INFILL MASK */
    #headline_text_fallback {{
      font-family: 'Syne', sans-serif;
      font-size: 108px;
      font-weight: 900;
      letter-spacing: -0.01em;
      line-height: 0.95;
      text-transform: uppercase;
      background-image: 
        radial-gradient(circle at 45% 35%, rgba(255, 255, 255, 0.50) 0%, transparent 45%),
        url('{bg_data_uri}');
      background-size: 900px, 950px;
      background-position: center, center 28%;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      -webkit-text-stroke: 2.2px var(--accent-color);
      filter: drop-shadow(0 20px 45px rgba(0, 0, 0, 0.98)) 
              drop-shadow(0 0 30px rgba(0, 255, 102, 0.85)) 
              drop-shadow(0 0 60px rgba(0, 243, 255, 0.45));
      white-space: nowrap;
    }}

    /* LAYER 3: HERO SHIELD EMBLEM (Z-INDEX: 10 - INTENTIONAL 3D OVERLAP OVER TITLE BASE) */
    #hero_art_1 {{
      position: absolute;
      top: var(--hero-top);
      left: 50%;
      transform: translateX(-50%);
      width: var(--hero-size);
      height: var(--hero-size);
      object-fit: contain;
      filter: drop-shadow(0 35px 75px rgba(0, 0, 0, 0.98)) drop-shadow(0 0 50px rgba(0, 255, 102, 0.60));
      z-index: 10;
      pointer-events: none;
    }}

    /* LAYER 4: TOURNAMENT TRACKS BELT WITH TACTICAL CONNECTORS (Z-INDEX: 18) */
    #tracks_belt {{
      position: absolute;
      top: calc(var(--hero-top) + var(--hero-size) + 12px);
      left: 60px;
      right: 60px;
      z-index: 18;
      display: flex;
      justify-content: center;
      gap: 16px;
      flex-wrap: wrap;
    }}

    .track-badge {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 19px;
      font-weight: 800;
      color: var(--highlight-color);
      background: rgba(0, 243, 255, 0.08);
      border: 1px solid rgba(0, 243, 255, 0.38);
      padding: 9px 24px;
      border-radius: 6px;
      text-transform: uppercase;
      letter-spacing: 0.10em;
      backdrop-filter: blur(14px);
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.6), 0 0 16px rgba(0, 243, 255, 0.20);
    }}

    /* LAYER 5: ATMOSPHERIC GRADIENT SCRIM (NO ISOLATED CARD BOX) */
    .layer-scrim {{
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 780px;
      background: linear-gradient(180deg, 
        transparent 0%, 
        rgba(5, 8, 17, 0.35) 20%, 
        rgba(5, 8, 17, 0.82) 55%, 
        rgba(5, 8, 17, 0.98) 90%, 
        #050811 100%);
      z-index: 19;
      pointer-events: none;
    }}

    /* LAYER 6: SCENE-INTEGRATED EDITORIAL METADATA (Z-INDEX: 22) */
    #bottom_metadata_container {{
      position: absolute;
      bottom: var(--metadata-bottom);
      left: 75px;
      right: 75px;
      z-index: 22;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}

    #card_date_venue {{
      display: grid;
      grid-template-columns: 1.15fr 1.35fr;
      gap: 32px;
      align-items: start;
      padding: 22px 28px;
      background: rgba(7, 11, 24, 0.70);
      border: 1px solid rgba(0, 243, 255, 0.28);
      border-radius: 12px;
      backdrop-filter: blur(18px);
      box-shadow: 0 15px 35px rgba(0, 0, 0, 0.7), 0 0 25px rgba(0, 243, 255, 0.12);
    }}

    .micro-label {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.16em;
      color: var(--text-muted);
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .micro-label::before {{
      content: "//";
      color: var(--highlight-color);
      font-weight: 800;
    }}

    #date_1 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 38px;
      font-weight: 800;
      color: var(--gold-color);
      line-height: 1.1;
      text-shadow: 0 0 22px rgba(255, 183, 3, 0.45);
    }}

    #venue_1 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 25px;
      font-weight: 700;
      color: var(--text-main);
      line-height: 1.25;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.85);
    }}

    #subhead_prize_row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 20px;
      background: rgba(0, 255, 102, 0.05);
      border: 1px solid rgba(0, 255, 102, 0.22);
      border-radius: 10px;
      padding: 14px 22px;
    }}

    #subhead_1 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 22px;
      font-weight: 700;
      color: var(--text-main);
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}

    #prize_1 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 28px;
      font-weight: 800;
      color: var(--accent-color);
      background: rgba(0, 255, 102, 0.12);
      padding: 8px 24px;
      border-radius: 6px;
      border: 1.8px solid var(--accent-color);
      box-shadow: 0 0 24px rgba(0, 255, 102, 0.35);
      white-space: nowrap;
      text-shadow: 0 0 16px rgba(0, 255, 102, 0.5);
    }}

    #cta_footer_row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 20px;
      padding-top: 4px;
    }}

    #cta_1 {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 23px;
      font-weight: 800;
      color: #050811;
      background: var(--accent-color);
      padding: 13px 32px;
      border-radius: 6px;
      box-shadow: 0 0 35px rgba(0, 255, 102, 0.60);
      white-space: nowrap;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    #organizer_1 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 19px;
      font-weight: 600;
      color: var(--text-muted);
      letter-spacing: 0.02em;
    }}

    /* LAYER 7: UNIFIED COLOR GRADE & AMBIENT FILM GRAIN (Z-INDEX: 30) */
    .layer-color-grade {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      background: radial-gradient(circle at 50% 45%, rgba(0, 243, 255, 0.07) 0%, rgba(0, 255, 102, 0.05) 55%, transparent 80%);
      mix-blend-mode: color-dodge;
      pointer-events: none;
      z-index: 30;
    }}

    .layer-film-grain {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      opacity: 0.12;
      mix-blend-mode: overlay;
      pointer-events: none;
      z-index: 31;
    }}
  </style>
</head>
<body>
  <div class="poster-canvas">
    <!-- ART LAYERS -->
    <div id="layer_background" class="art-layer"></div>
    <div class="circuit-grid art-layer"></div>
    <div id="hero_light_spill" class="art-layer"></div>
    {f'<img id="hero_art_1" class="art-layer" src="{hero_data_uri}" alt="Hero Shield Art" />' if hero_data_uri else ''}
    {f'<img id="accent_art_1" class="art-layer" src="{accent_data_uri}" alt="Accent Art" />' if accent_data_uri else ''}

    <!-- LAYER 2: METHOD 3 GENERATIVE TEXTURE INFILL HEADLINE (Z-INDEX: 5) -->
    <div id="title_zone">
      <div class="top-telemetry-bar">
        <div class="telemetry-badge">CTF_CHALLENGE // 2026</div>
        <div class="telemetry-status">SYS_STATUS: ONLINE</div>
      </div>
      {f'<div id="tagline_1">{tagline}</div>' if tagline else ''}
      <div id="headline_zone">
        <h1 id="headline_text_fallback">{title}</h1>
      </div>
    </div>

    <!-- LAYER 4: TOURNAMENT TRACKS BELT -->
    {f'<div id="tracks_belt">{tracks_badges_html}</div>' if tracks_badges_html else ''}

    <!-- LAYER 5: ATMOSPHERIC GRADIENT SCRIM -->
    <div class="layer-scrim"></div>

    <!-- LAYER 6: SCENE-INTEGRATED EDITORIAL METADATA -->
    <div id="bottom_metadata_container">
      <div id="card_date_venue">
        <div>
          <div class="micro-label">EVENT TIMEFRAME</div>
          <div id="date_1">{date_str}</div>
          {f'<div id="time_1" style="font-family: JetBrains Mono; font-size: 18px; font-weight: 600; color: var(--text-muted); margin-top: 6px;">{time_str}</div>' if time_str else ''}
        </div>
        <div>
          <div class="micro-label">COORDINATES & VENUE</div>
          <div id="venue_1">{venue_str}</div>
          {f'<div id="team_size_1" style="font-family: JetBrains Mono; font-size: 17px; font-weight: 700; color: var(--accent-color); margin-top: 6px;">{team_size_str}</div>' if team_size_str else ''}
        </div>
      </div>

      <div id="subhead_prize_row">
        <div id="subhead_1">{subtitle or "24-HOUR CYBERSECURITY TOURNAMENT"}</div>
        {f'<div id="prize_1">{prize_str}</div>' if prize_str else ''}
      </div>

      <div id="cta_footer_row">
        <div id="cta_1">{cta_str}</div>
        {f'<div id="organizer_1">{organizer_str}</div>' if organizer_str else ''}
      </div>
    </div>

    <!-- LAYER 7: COLOR GRADE & AMBIENT FILM GRAIN -->
    <div class="layer-color-grade art-layer"></div>
    <svg class="layer-film-grain art-layer" xmlns="http://www.w3.org/2000/svg">
      <filter id="noiseFilter"><feTurbulence type="fractalNoise" baseFrequency="0.75" numOctaves="3" stitchTiles="stitch"/></filter>
      <rect width="100%" height="100%" filter="url(#noiseFilter)"/>
    </svg>
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
    ) -> ThemeRenderResult:
        """Render both full poster and text-only occlusion layer with Playwright."""
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
            hide_style = "<style>.art-layer { visibility: hidden !important; } #hero_art_1, #accent_art_1, #layer_background, #hero_light_spill { display: none !important; }</style>"
            if "</head>" in html_override:
                html_text_only = html_override.replace("</head>", f"{hide_style}</head>")
            else:
                html_text_only = f"{hide_style}{html_override}"
        else:
            html_full = self.compose_html(brief, art_bundle, bg_uri, hero_uri, title_uri, accent_uri, hide_art=False)
            html_text_only = self.compose_html(brief, art_bundle, bg_uri, hero_uri, title_uri, accent_uri, hide_art=True)

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
            # Viewport
            page = browser.new_page(
                viewport={"width": art_bundle.canvas_w, "height": art_bundle.canvas_h},
                device_scale_factor=2.0,
            )

            # 1. Capture Full Render
            page.goto(full_html_path.resolve().as_uri(), wait_until="networkidle")
            page.wait_for_timeout(500)
            canvas = page.locator(".poster-canvas")
            canvas.screenshot(path=str(full_png_path))

            # Extract DOM Bounding Boxes for all stable IDs
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

            # Export Vector PDF
            page.pdf(
                path=str(pdf_path),
                width=f"{art_bundle.canvas_w}px",
                height=f"{art_bundle.canvas_h}px",
                print_background=True,
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            )

            # 2. Capture Text-Only Layer for Occlusion Mathematical Subtraction
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
