"""Stage 4: Theme Pack Renderer with Stable Element IDs and Text-Alone Occlusion Layering."""
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
    """Renders ExtractedBrief and MeasuredArt using stable theme packs and stable element IDs."""

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
        """Compose HTML with stable IDs and parametric CSS variables."""
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
            hero_size = 560

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title} - Theme Render</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700;800&family=Space+Grotesk:wght@600;700;800;900&family=Syne:wght@800;900&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    
    :root {{
      --title-top: 70px;
      --hero-top: {hero_top}px;
      --hero-size: {hero_size}px;
      --metadata-bottom: 55px;
      --card-bg: rgba(7, 11, 24, 0.85);
      --card-border: rgba(0, 243, 255, 0.35);
      --accent-color: #00FF66;
      --highlight-color: #00F3FF;
      --danger-color: #00FF66;
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
    }}

    /* ART LAYERS (Visibility toggleable for text-alone occlusion checks) */
    .art-layer {{
      visibility: {art_visibility};
    }}

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

    #hero_light_spill {{
      position: absolute;
      top: calc(var(--hero-top) + 260px);
      left: 50%;
      transform: translate(-50%, -50%);
      width: 950px;
      height: 950px;
      background: radial-gradient(circle, rgba(0, 255, 102, 0.35) 0%, rgba(0, 243, 255, 0.22) 38%, transparent 72%);
      filter: blur(65px);
      mix-blend-mode: screen;
      pointer-events: none;
      z-index: 2;
    }}

    #hero_art_1 {{
      position: absolute;
      top: var(--hero-top);
      left: 50%;
      transform: translateX(-50%);
      width: var(--hero-size);
      height: var(--hero-size);
      object-fit: contain;
      filter: drop-shadow(0 25px 50px rgba(0, 0, 0, 0.95)) drop-shadow(0 0 45px rgba(0, 255, 102, 0.50));
      z-index: 10;
      pointer-events: none;
    }}

    /* TYPOGRAPHY WITH STABLE ELEMENT IDS */
    #title_zone {{
      position: absolute;
      top: var(--title-top);
      left: 50px;
      right: 50px;
      z-index: 15;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }}

    #tagline_1 {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 20px;
      font-weight: 700;
      color: var(--highlight-color);
      letter-spacing: 0.16em;
      text-transform: uppercase;
      text-shadow: 0 0 16px rgba(0, 243, 255, 0.6);
      margin-bottom: 12px;
    }}

    #headline_zone {{
      display: flex;
      flex-direction: column;
      align-items: center;
    }}

    #headline_text_fallback {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 92px;
      font-weight: 900;
      letter-spacing: 0.04em;
      line-height: 1.02;
      text-transform: uppercase;
      color: #FFFFFF;
      background: linear-gradient(180deg, #FFFFFF 20%, #00F3FF 70%, #00FF66 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      filter: drop-shadow(0 15px 35px rgba(0, 0, 0, 0.95)) drop-shadow(0 0 25px rgba(0, 243, 255, 0.45));
    }}

    /* TOURNAMENT TRACKS BELT */
    #tracks_belt {{
      position: absolute;
      top: calc(var(--hero-top) + var(--hero-size) + 24px);
      left: 60px;
      right: 60px;
      z-index: 20;
      display: flex;
      justify-content: center;
      gap: 14px;
      flex-wrap: wrap;
    }}

    .track-badge {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 19px;
      font-weight: 700;
      color: var(--highlight-color);
      background: rgba(0, 243, 255, 0.08);
      border: 1px solid rgba(0, 243, 255, 0.32);
      padding: 9px 22px;
      border-radius: 8px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      backdrop-filter: blur(10px);
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 15px rgba(0, 243, 255, 0.12);
    }}

    /* BOTTOM METADATA WITH STABLE COMPONENT WRAPPERS */
    #bottom_metadata_container {{
      position: absolute;
      bottom: var(--metadata-bottom);
      left: 70px;
      right: 70px;
      z-index: 22;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}

    #card_date_venue {{
      display: grid;
      grid-template-columns: 1.15fr 1.35fr;
      gap: 28px;
      align-items: start;
      padding: 24px 30px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      backdrop-filter: blur(16px);
      box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6), 0 0 25px rgba(0, 243, 255, 0.15);
    }}

    #date_1 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 34px;
      font-weight: 800;
      color: var(--highlight-color);
      line-height: 1.1;
      text-shadow: 0 0 20px rgba(0, 243, 255, 0.45);
    }}

    #venue_1 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 24px;
      font-weight: 700;
      color: var(--text-main);
      line-height: 1.25;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.8);
    }}

    #subhead_prize_row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 20px;
    }}

    #subhead_1 {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 22px;
      font-weight: 700;
      color: var(--text-muted);
      letter-spacing: 0.05em;
    }}

    #prize_1 {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 24px;
      font-weight: 800;
      color: var(--accent-color);
      background: rgba(0, 255, 102, 0.12);
      padding: 8px 22px;
      border-radius: 6px;
      border: 1.5px solid var(--accent-color);
      box-shadow: 0 0 22px rgba(0, 255, 102, 0.35);
      white-space: nowrap;
    }}

    #cta_footer_row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 20px;
    }}

    #cta_1 {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 22px;
      font-weight: 800;
      color: #050811;
      background: var(--accent-color);
      padding: 12px 28px;
      border-radius: 6px;
      box-shadow: 0 0 32px rgba(0, 255, 102, 0.60);
      white-space: nowrap;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
  </style>
</head>
<body>
  <div class="poster-canvas">
    <!-- ART LAYERS -->
    <div id="layer_background" class="art-layer"></div>
    <div id="hero_light_spill" class="art-layer"></div>
    {f'<img id="hero_art_1" class="art-layer" src="{hero_data_uri}" alt="Hero Art" />' if hero_data_uri else ''}

    <!-- TOURNAMENT TRACKS BELT -->
    {f'<div id="tracks_belt">{tracks_badges_html}</div>' if tracks_badges_html else ''}

    <!-- TYPOGRAPHY WITH STABLE ELEMENT IDS -->
    <div id="title_zone">
      {f'<div id="tagline_1">{tagline}</div>' if tagline else ''}
      <div id="headline_zone">
        <h1 id="headline_text_fallback">{title}</h1>
      </div>
    </div>

    <!-- METADATA -->
    <div id="bottom_metadata_container">
      <div id="card_date_venue">
        <div>
          <div style="font-family: 'JetBrains Mono'; font-size: 15px; font-weight: 700; color: var(--text-muted); margin-bottom: 6px;">// DATE & TIME</div>
          <div id="date_1">{date_str}</div>
          {f'<div id="time_1" style="font-family: JetBrains Mono; font-size: 19px; font-weight: 600; color: var(--text-muted); margin-top: 6px;">{time_str}</div>' if time_str else ''}
        </div>
        <div>
          <div style="font-family: 'JetBrains Mono'; font-size: 15px; font-weight: 700; color: var(--text-muted); margin-bottom: 6px;">// VENUE & SPECS</div>
          <div id="venue_1">{venue_str}</div>
          {f'<div id="team_size_1" style="font-family: JetBrains Mono; font-size: 17px; font-weight: 700; color: var(--accent-color); margin-top: 6px;">{team_size_str}</div>' if team_size_str else ''}
        </div>
      </div>

      <div id="subhead_prize_row">
        <div id="subhead_1">{events_str or subtitle}</div>
        {f'<div id="prize_1">{prize_str}</div>' if prize_str else ''}
      </div>

      <div id="cta_footer_row">
        <div id="cta_1">{cta_str}</div>
        {f'<div id="organizer_1" style="font-family: JetBrains Mono; font-size: 18px; font-weight: 600; color: var(--text-muted);">{organizer_str}</div>' if organizer_str else ''}
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
                "subhead_1", "prize_1", "cta_1", "organizer_1", "hero_art_1"
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
