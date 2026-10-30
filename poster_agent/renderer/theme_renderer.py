"""Stage 4: Theme Pack Renderer with Stable Element IDs and Text-Alone Occlusion Layering."""
import base64
import json
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

    def __init__(self, theme_name: str = "cyber_aurora"):
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
        title = brief.get_text("title", "EVENT TITLE")
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

        # Dynamic hero size and position based on measured art bounds
        if art_bundle.hero_geometry:
            hero_top = max(260, art_bundle.hero_geometry.y_min // 2)
            hero_size = max(380, min(650, art_bundle.hero_geometry.width // 2))
        else:
            hero_top = 345
            hero_size = 580

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title} - Theme Render</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700;800&family=Space+Grotesk:wght@500;700;800&family=Syne:wght@800;900&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    
    :root {{
      --title-top: 85px;
      --hero-top: {hero_top}px;
      --hero-size: {hero_size}px;
      --metadata-bottom: 60px;
      --card-bg: rgba(14, 7, 40, 0.68);
      --card-border: rgba(122, 231, 199, 0.28);
      --accent-color: #7AE7C7;
      --highlight-color: #FFB703;
      --danger-color: #FF4D6D;
      --text-main: #FFF3E0;
      --text-muted: #C9B8FF;
    }}

    body {{
      background: #0E0728;
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
      top: calc(var(--hero-top) + 290px);
      left: 50%;
      transform: translate(-50%, -50%);
      width: 880px;
      height: 880px;
      background: radial-gradient(circle, rgba(122, 231, 199, 0.38) 0%, rgba(255, 183, 3, 0.22) 40%, transparent 75%);
      filter: blur(55px);
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
      filter: drop-shadow(0 30px 60px rgba(0, 0, 0, 0.95)) drop-shadow(0 0 45px rgba(122, 231, 199, 0.45));
      z-index: 10;
      pointer-events: none;
    }}

    #accent_art_1 {{
      position: absolute;
      top: 135px;
      right: 65px;
      width: 165px;
      height: 165px;
      object-fit: contain;
      opacity: 0.40;
      mix-blend-mode: screen;
      filter: blur(1.5px) drop-shadow(0 0 25px rgba(255, 183, 3, 0.4));
      z-index: 3;
      pointer-events: none;
    }}

    /* TYPOGRAPHY WITH STABLE ELEMENT IDS */
    #title_zone {{
      position: absolute;
      top: var(--title-top);
      left: 60px;
      right: 60px;
      z-index: 12;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }}

    #tagline_1 {{
      font-size: 26px;
      font-weight: 700;
      color: var(--accent-color);
      letter-spacing: 0.06em;
      text-shadow: 0 0 16px rgba(122, 231, 199, 0.6);
      margin-bottom: 8px;
    }}

    #headline_1 {{
      max-width: 920px;
      max-height: 290px;
      object-fit: contain;
      filter: drop-shadow(0 30px 60px rgba(0, 0, 0, 0.98)) drop-shadow(0 0 50px rgba(122, 231, 199, 0.75));
    }}

    #headline_text_fallback {{
      font-family: 'Syne', sans-serif;
      font-size: 96px;
      font-weight: 900;
      letter-spacing: 0.02em;
      color: var(--accent-color);
      text-shadow: 0 0 35px rgba(122, 231, 199, 0.85);
      line-height: 1.0;
    }}

    /* BOTTOM METADATA WITH STABLE COMPONENT WRAPPERS */
    #bottom_metadata_container {{
      position: absolute;
      bottom: var(--metadata-bottom);
      left: 80px;
      right: 80px;
      z-index: 22;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}

    #card_date_venue {{
      display: grid;
      grid-template-columns: 1.15fr 1.35fr;
      gap: 28px;
      align-items: start;
      padding: 22px 28px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      backdrop-filter: blur(14px);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }}

    #date_1 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 38px;
      font-weight: 800;
      color: var(--highlight-color);
      line-height: 1.1;
      text-shadow: 0 0 24px rgba(255, 183, 3, 0.45);
    }}

    #venue_1 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 26px;
      font-weight: 700;
      color: var(--text-main);
      line-height: 1.25;
      text-shadow: 0 2px 12px rgba(0, 0, 0, 0.85);
    }}

    #subhead_prize_row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 20px;
    }}

    #subhead_1 {{
      font-size: 28px;
      font-weight: 700;
      color: var(--text-main);
      letter-spacing: 0.02em;
    }}

    #prize_1 {{
      font-size: 28px;
      font-weight: 800;
      color: var(--danger-color);
      background: rgba(255, 77, 109, 0.16);
      padding: 8px 22px;
      border-radius: 8px;
      border: 1.8px solid var(--danger-color);
      box-shadow: 0 0 28px rgba(255, 77, 109, 0.35);
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
      font-size: 24px;
      font-weight: 800;
      color: #0E0728;
      background: var(--accent-color);
      padding: 10px 26px;
      border-radius: 8px;
      box-shadow: 0 0 30px rgba(122, 231, 199, 0.55);
      white-space: nowrap;
    }}
  </style>
</head>
<body>
  <div class="poster-canvas">
    <!-- ART LAYERS -->
    <div id="layer_background" class="art-layer"></div>
    <div id="hero_light_spill" class="art-layer"></div>
    {f'<img id="hero_art_1" class="art-layer" src="{hero_data_uri}" alt="Hero Art" />' if hero_data_uri else ''}
    {f'<img id="accent_art_1" class="art-layer" src="{accent_data_uri}" alt="Accent Art" />' if accent_data_uri else ''}

    <!-- TYPOGRAPHY WITH STABLE ELEMENT IDS -->
    <div id="title_zone">
      {f'<div id="tagline_1">{tagline}</div>' if tagline else ''}
      {f'<img id="headline_1" src="{title_3d_data_uri}" alt="{title}" />' if title_3d_data_uri else f'<h1 id="headline_text_fallback">{title}</h1>'}
    </div>

    <!-- METADATA -->
    <div id="bottom_metadata_container">
      <div id="card_date_venue">
        <div>
          <div style="font-family: 'JetBrains Mono'; font-size: 16px; font-weight: 700; color: var(--text-muted); margin-bottom: 6px;">// DATE</div>
          <div id="date_1">{date_str}</div>
          {f'<div id="time_1" style="font-family: JetBrains Mono; font-size: 20px; font-weight: 600; color: var(--text-muted); margin-top: 6px;">{time_str}</div>' if time_str else ''}
        </div>
        <div>
          <div style="font-family: 'JetBrains Mono'; font-size: 16px; font-weight: 700; color: var(--text-muted); margin-bottom: 6px;">// VENUE</div>
          <div id="venue_1">{venue_str}</div>
          {f'<div id="team_size_1" style="font-family: JetBrains Mono; font-size: 18px; font-weight: 700; color: var(--accent-color); margin-top: 6px;">{team_size_str}</div>' if team_size_str else ''}
        </div>
      </div>

      <div id="subhead_prize_row">
        <div id="subhead_1">{subtitle}</div>
        {f'<div id="prize_1">{prize_str}</div>' if prize_str else ''}
      </div>

      <div id="cta_footer_row">
        <div id="cta_1">{cta_str}</div>
        {f'<div id="organizer_1" style="font-size: 20px; font-weight: 600; color: var(--text-muted);">{organizer_str}</div>' if organizer_str else ''}
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
                "title_zone", "headline_1", "headline_text_fallback", "tagline_1",
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
