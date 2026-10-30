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
    ) -> str:
        art_visibility = "hidden" if hide_art else "visible"

        # Brief Strings (Verbatim)
        title = brief.get_text("title", "NOVA CTF 2026")
        tagline = brief.get_text("tagline", "Capture the flag. Break it. Fix it.")
        subtitle = brief.get_text("subtitle", "24-HOUR CYBERSECURITY TOURNAMENT")
        date_str = brief.get_text("date", "15-16 NOVEMBER 2026")
        time_str = brief.get_text("time", "9:00 AM ONWARDS")
        venue_str = brief.get_text("venue", "Main Computer Lab, Block C")
        events_str = brief.get_text("events", "WEB | CRYPTO | FORENSICS | REVERSING")
        prize_str = brief.get_text("prize", "₹50,000 Total Prize Pool")
        cta_str = brief.get_text("cta", "Register free at nova-ctf.example")
        organizer_str = brief.get_text("organizer", "Presented by NOVA Security Club")
        team_size_str = brief.get_text("team_size", "Teams of 2-4")

        # Clean prize string for HUD pill
        prize_display = prize_str if "PRIZE" in prize_str.upper() else f"PRIZE POOL {prize_str}"

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title} - Master Path 3 Blended HUD Poster</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=Space+Grotesk:wght@600;700;800&family=Syne:wght@800;900&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    
    body {{
      background: #000000;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      font-family: 'Space Grotesk', sans-serif;
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
      background-color: #0A0E17;
      background-image: 
        radial-gradient(circle at 50% 35%, rgba(0, 255, 156, 0.16) 0%, transparent 60%),
        radial-gradient(circle at 85% 15%, rgba(0, 209, 255, 0.20) 0%, transparent 50%),
        linear-gradient(180deg, rgba(10, 14, 23, 0.45) 0%, rgba(10, 14, 23, 0.15) 30%, rgba(10, 14, 23, 0.60) 70%, rgba(10, 14, 23, 0.95) 100%),
        url('{bg_uri}');
      background-size: cover;
      background-position: center;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 68px;
      color: #FFFFFF;
    }}

    .art-layer {{
      visibility: {art_visibility};
    }}

    /* TACTICAL GRID OVERLAY */
    .circuit-grid {{
      position: absolute;
      inset: 0;
      background-size: 54px 54px;
      background-image: 
        linear-gradient(to right, rgba(0, 255, 156, 0.04) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(0, 209, 255, 0.04) 1px, transparent 1px);
      pointer-events: none;
      z-index: 1;
    }}

    .grain {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      opacity: 0.14;
      pointer-events: none;
      z-index: 20;
      mix-blend-mode: overlay;
    }}

    /* HOLOGRAPHIC CYBER FLAG */
    .cyber-flag {{
      position: absolute;
      top: 25px;
      right: 25px;
      width: 250px;
      height: 250px;
      object-fit: contain;
      z-index: 15;
      transform: rotate(-4deg);
      mix-blend-mode: screen;
      filter: drop-shadow(0 0 25px rgba(0, 255, 156, 0.65)) drop-shadow(0 0 35px rgba(0, 209, 255, 0.45));
      pointer-events: none;
    }}

    /* TOP SECTION: PATH 3 GENERATIVE CIRCUIT INFILL TITLE */
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
      font-family: 'JetBrains Mono', monospace;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: #00FF9C;
      background: rgba(0, 255, 156, 0.08);
      padding: 6px 14px;
      border-radius: 4px;
      border: 1px solid rgba(0, 255, 156, 0.28);
    }}
    .top-badge::before {{
      content: "";
      width: 7px;
      height: 7px;
      background: #00FF9C;
      border-radius: 50%;
      box-shadow: 0 0 8px #00FF9C;
    }}

    .terminal-status {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      font-weight: 600;
      color: #8A94A6;
      letter-spacing: 0.12em;
    }}

    /* PATH 3 GENERATIVE CIRCUIT MASK INFILL TITLE */
    .main-title-path3 {{
      font-family: 'Syne', sans-serif;
      font-size: 102px;
      font-weight: 900;
      line-height: 0.95;
      letter-spacing: -0.02em;
      text-transform: uppercase;
      background-image: url('{bg_uri}');
      background-size: 750px;
      background-position: center;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      -webkit-text-stroke: 2px #00FF9C;
      filter: drop-shadow(0 0 25px rgba(0, 255, 156, 0.75)) drop-shadow(0 0 50px rgba(0, 209, 255, 0.50));
      margin-bottom: 14px;
      white-space: nowrap;
    }}

    .tagline-row {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .tagline-slash {{
      color: #00D1FF;
      font-weight: 800;
      font-size: 26px;
    }}
    .tagline {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 27px;
      font-weight: 600;
      letter-spacing: -0.01em;
      color: #00FF9C;
      text-shadow: 0 0 16px rgba(0, 255, 156, 0.40);
    }}

    /* CENTER HERO SHIELD WITH VOLUMETRIC BACKGLOW */
    .cyber-shield-container {{
      position: absolute;
      top: 350px;
      left: 50%;
      transform: translateX(-50%);
      width: 680px;
      height: 680px;
      z-index: 25;
      display: flex;
      justify-content: center;
      align-items: center;
      pointer-events: none;
    }}

    .shield-backglow {{
      position: absolute;
      width: 580px;
      height: 580px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(0, 255, 156, 0.24) 0%, rgba(0, 209, 255, 0.12) 50%, transparent 72%);
      filter: blur(45px);
    }}

    .cyber-shield-img {{
      position: relative;
      max-width: 650px;
      max-height: 650px;
      object-fit: contain;
      filter: drop-shadow(0 30px 65px rgba(0, 0, 0, 0.98)) drop-shadow(0 0 45px rgba(0, 255, 156, 0.65));
    }}

    /* BOTTOM METADATA: UNIFIED GRAPHIC DESIGN HUD PANEL */
    .section-lower {{
      position: relative;
      z-index: 30;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}

    .hud-panel {{
      background: rgba(10, 14, 23, 0.78);
      border: 1px solid rgba(0, 255, 156, 0.28);
      border-radius: 12px;
      padding: 24px 28px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      backdrop-filter: blur(18px);
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.85), 0 0 35px rgba(0, 255, 156, 0.15);
    }}

    .hud-main-grid {{
      display: grid;
      grid-template-columns: 1.15fr 1.35fr;
      gap: 32px;
      align-items: start;
    }}

    .micro-label {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: #8A94A6;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .micro-label::before {{
      content: "//";
      color: #00D1FF;
    }}

    .date-display {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 38px;
      font-weight: 800;
      letter-spacing: -0.01em;
      color: #00D1FF;
      line-height: 1.1;
      text-shadow: 0 0 22px rgba(0, 209, 255, 0.35);
    }}

    .venue-display {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 26px;
      font-weight: 700;
      color: #FFFFFF;
      line-height: 1.25;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.85);
    }}

    .hud-banner-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(0, 255, 156, 0.05);
      border: 1px solid rgba(0, 255, 156, 0.22);
      border-radius: 8px;
      padding: 14px 20px;
      gap: 16px;
    }}

    .subtitle-text {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 23px;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: #FFFFFF;
      line-height: 1.2;
    }}

    .bounty-pill {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 28px;
      font-weight: 800;
      letter-spacing: 0.02em;
      color: #00FF9C;
      white-space: nowrap;
      text-shadow: 0 0 16px rgba(0, 255, 156, 0.50);
      background: rgba(0, 255, 156, 0.12);
      padding: 8px 20px;
      border-radius: 6px;
      border: 1px solid #00FF9C;
      box-shadow: 0 0 22px rgba(0, 255, 156, 0.25);
    }}

    .hud-tracks-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 10px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      gap: 20px;
    }}

    .tracks-content {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0.06em;
      color: #00D1FF;
      white-space: nowrap;
    }}

    .meta-specs {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 15px;
      font-weight: 600;
      color: #8A94A6;
      display: flex;
      gap: 24px;
      white-space: nowrap;
    }}
    .meta-specs span {{
      color: #FFFFFF;
      font-weight: 700;
    }}

    .section-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 8px;
      border-top: 1px solid rgba(255, 255, 255, 0.10);
    }}

    .cta-pill {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 21px;
      font-weight: 800;
      color: #0A0E17;
      background: #00FF9C;
      letter-spacing: 0.02em;
      padding: 12px 28px;
      border-radius: 6px;
      box-shadow: 0 0 28px rgba(0, 255, 156, 0.45);
      text-transform: uppercase;
      white-space: nowrap;
    }}

    .organizer-pill {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 18px;
      font-weight: 600;
      color: #8A94A6;
      letter-spacing: 0.02em;
      white-space: nowrap;
    }}
  </style>
</head>
<body>

  <div class="poster-canvas">
    <div class="circuit-grid art-layer"></div>
    <svg class="grain art-layer" xmlns="http://www.w3.org/2000/svg">
      <filter id="noiseFilter"><feTurbulence type="fractalNoise" baseFrequency="0.75" numOctaves="3" stitchTiles="stitch"/></filter>
      <rect width="100%" height="100%" filter="url(#noiseFilter)"/>
    </svg>

    <!-- FLAG -->
    {f'<img id="accent_art_1" class="cyber-flag art-layer" src="{accent_uri}" alt="Cyber Flag" />' if accent_uri else ''}

    <!-- TOP SECTION: PATH 3 GENERATIVE CIRCUIT INFILL TITLE -->
    <div id="title_zone" class="section-title">
      <div class="top-meta-bar">
        <div class="top-badge">CTF_CHALLENGE // 2026</div>
        <div class="terminal-status">SYS_STATUS: ONLINE</div>
      </div>
      <h1 id="headline_text_fallback" class="main-title-path3">{title}</h1>
      <div class="tagline-row">
        <span class="tagline-slash">&gt;</span>
        <div id="tagline_1" class="tagline">{tagline}</div>
      </div>
    </div>

    <!-- SHIELD -->
    <div class="cyber-shield-container">
      <div class="shield-backglow art-layer"></div>
      {f'<img id="hero_art_1" class="cyber-shield-img art-layer" src="{hero_uri}" alt="Cyber Shield Motif" />' if hero_uri else ''}
    </div>

    <!-- HUD -->
    <div id="bottom_metadata_container" class="section-lower">
      <div id="card_date_venue" class="hud-panel">
        <div class="hud-main-grid">
          <div>
            <div class="micro-label">EVENT TIMEFRAME</div>
            <div id="date_1" class="date-display">{date_str}</div>
          </div>
          <div>
            <div class="micro-label">COORDINATES & VENUE</div>
            <div id="venue_1" class="venue-display">{venue_str}</div>
          </div>
        </div>

        <div id="subhead_prize_row" class="hud-banner-row">
          <div id="subhead_1" class="subtitle-text">{subtitle}</div>
          <div id="prize_1" class="bounty-pill">{prize_display}</div>
        </div>

        <div id="tracks_belt" class="hud-tracks-row">
          <div class="tracks-content">{events_str}</div>
          <div class="meta-specs">
            {f'<div>TEAM: <span id="team_size_1">{team_size_str}</span></div>' if team_size_str else ''}
            {f'<div>TIME: <span id="time_1">{time_str}</span></div>' if time_str else ''}
          </div>
        </div>
      </div>

      <div id="cta_footer_row" class="section-footer">
        <div id="cta_1" class="cta-pill">{cta_str}</div>
        <div id="organizer_1" class="organizer-pill">{organizer_str}</div>
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
            page = browser.new_page(
                viewport={"width": art_bundle.canvas_w, "height": art_bundle.canvas_h},
                device_scale_factor=2.0,
            )

            # Capture Full Render
            page.goto(full_html_path.resolve().as_uri(), wait_until="networkidle")
            page.wait_for_timeout(500)
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
