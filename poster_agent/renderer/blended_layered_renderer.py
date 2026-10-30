"""Blended Layered Poster Renderer.

Implements the "Art First, Vision-Assisted Layout Second" design philosophy:
- Replaces rigid rectangular segregation with Depth Layers (Z-Stacking).
- Eliminates opaque dashboard cards, placing text directly on scene with soft gradient scrims.
- Renders screen-blended light spill emitted from hero and accent assets.
- Allows massive headlines to sit behind the hero orb (intentional 3D overlap).
- Curves typography around circular hero contours via SVG textPath.
- Samples colors from the art and applies global color grade + ambient grain.
"""
from pathlib import Path
from typing import Any, Literal
from playwright.sync_api import sync_playwright

from poster_agent.vision.art_analyzer import ArtCompositionPlan


class BlendedLayeredRenderer:
    """Renders artistic, depth-layered promotional posters with true visual integration."""

    def compose_html(
        self,
        plan: ArtCompositionPlan,
        brief_data: dict[str, str],
        title_mode: Literal["path2_3d", "path3_infill"] = "path2_3d",
        bg_img_path: str = "",
        hero_img_path: str = "",
        accent_img_path: str = "",
        title_3d_img_path: str = "",
    ) -> str:
        """Compose HTML for the depth-stacked, art-blended poster."""
        
        # 1. Title Layer configuration
        if title_mode == "path2_3d" and title_3d_img_path:
            title_html = f"""
            <div class="title-path2-wrapper">
              <img src="{title_3d_img_path}" alt="{brief_data.get('title', 'EVENT')}" class="title-path2-img" />
            </div>
            """
        else:
            title_html = f"""
            <h1 class="headline-huge">{brief_data.get('title', 'EVENT')}</h1>
            """

        # 2. Extract brief strings (strictly verbatim)
        tagline = brief_data.get("tagline", "")
        date_str = brief_data.get("date", "")
        venue_str = brief_data.get("venue", "")
        subtitle_str = brief_data.get("subtitle", "")
        prize_str = brief_data.get("prize", "")
        events_str = brief_data.get("events", "")
        time_str = brief_data.get("time", "")
        entry_str = brief_data.get("entry", "")
        cta_str = brief_data.get("cta", "")
        contact_str = brief_data.get("contact", "")
        hashtag_str = brief_data.get("hashtag", "")
        organizer_str = brief_data.get("organizer", "")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{brief_data.get('title', 'POSTER')} - Blended Layered Composition</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700;800&family=Syne:wght@800;900&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #06030F;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      font-family: 'Space Grotesk', sans-serif;
      -webkit-font-smoothing: antialiased;
    }}

    .poster-canvas {{
      position: relative;
      width: {plan.canvas_w}px;
      height: {plan.canvas_h}px;
      background-color: {plan.palette.sky_deep_hex};
      overflow: hidden;
      color: {plan.palette.text_primary_hex};
    }}

    /* LAYER 0: BACKGROUND SCENE */
    .layer-background {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      background-image: url('{bg_img_path}');
      background-size: cover;
      background-position: center top;
      z-index: 1;
    }}

    /* LAYER 1: LIGHT SPILL EMITTERS */
    .hero-light-spill {{
      position: absolute;
      top: {plan.light_spill.hero_emitter_y}px;
      left: {plan.light_spill.hero_emitter_x}px;
      width: {plan.light_spill.hero_emitter_radius}px;
      height: {plan.light_spill.hero_emitter_radius}px;
      transform: translate(-50%, -50%);
      background: radial-gradient(circle, 
        {plan.light_spill.hero_glow_rgba} 0%, 
        {plan.light_spill.hero_core_rgba} 40%, 
        rgba(255, 77, 109, 0.15) 65%, 
        transparent 80%);
      filter: blur(55px);
      mix-blend-mode: screen;
      pointer-events: none;
      z-index: 2;
    }}

    .lantern-light-spill {{
      position: absolute;
      top: {plan.light_spill.lantern_emitter_y}px;
      left: {plan.light_spill.lantern_emitter_x}px;
      width: {plan.light_spill.lantern_emitter_radius}px;
      height: {plan.light_spill.lantern_emitter_radius}px;
      transform: translate(-50%, -50%);
      background: radial-gradient(circle, {plan.light_spill.lantern_glow_rgba} 0%, rgba(255, 77, 109, 0.28) 50%, transparent 75%);
      filter: blur(40px);
      mix-blend-mode: screen;
      pointer-events: none;
      z-index: 2;
    }}

    /* LAYER 2: MASSIVE HEADLINE (LAYERED UNDER HERO ORB) */
    .layer-title-zone {{
      position: absolute;
      top: {plan.title_y - 85}px;
      left: 40px;
      right: 40px;
      z-index: 5;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }}

    .tagline-verbatim {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 24px;
      font-weight: 700;
      color: {plan.palette.hero_glow_hex};
      letter-spacing: 0.05em;
      text-shadow: 0 0 16px rgba(122, 231, 199, 0.6);
      margin-bottom: 6px;
    }}

    .title-path2-wrapper {{
      width: 100%;
      display: flex;
      justify-content: center;
      align-items: center;
    }}

    .title-path2-img {{
      max-width: 780px;
      max-height: 250px;
      object-fit: contain;
      filter: drop-shadow(0 20px 45px rgba(0, 0, 0, 0.95)) drop-shadow(0 0 40px rgba(122, 231, 199, 0.55));
    }}

    .headline-huge {{
      font-family: 'Syne', sans-serif;
      font-size: 98px;
      font-weight: 900;
      letter-spacing: 0.01em;
      line-height: 0.95;
      background-image: 
        radial-gradient(circle at 40% 40%, rgba(255, 255, 255, 0.45) 0%, transparent 50%),
        url('{bg_img_path}');
      background-size: 750px, 850px;
      background-position: center, center 35%;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      -webkit-text-stroke: 2px {plan.palette.hero_glow_hex};
      filter: drop-shadow(0 0 25px rgba(122, 231, 199, 0.75)) drop-shadow(0 0 50px rgba(255, 77, 109, 0.45));
      white-space: nowrap;
    }}

    /* LAYER 3: HERO GLASS ORB (OVERLAPS TITLE LOWER CROWN) */
    .layer-hero-orb {{
      position: absolute;
      top: {plan.hero.box_y_min}px;
      left: {plan.hero.center_x}px;
      transform: translateX(-50%);
      width: {plan.hero.radius * 2}px;
      height: {plan.hero.radius * 2}px;
      z-index: 10;
      pointer-events: none;
    }}

    .orb-img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      filter: drop-shadow(0 30px 60px rgba(0, 0, 0, 0.95)) drop-shadow(0 0 45px rgba(122, 231, 199, 0.45));
    }}

    /* LAYER 4: FOREGROUND ACCENTS */
    .layer-foreground-lanterns {{
      position: absolute;
      top: 70px;
      right: 40px;
      width: 200px;
      height: 200px;
      object-fit: contain;
      z-index: 15;
      mix-blend-mode: screen;
      filter: drop-shadow(0 0 30px rgba(255, 183, 3, 0.7)) drop-shadow(0 0 45px rgba(255, 77, 109, 0.4));
      pointer-events: none;
    }}

    /* LAYER 5: INTERACTING TYPOGRAPHY */
    .layer-orbital-events {{
      position: absolute;
      top: {plan.hero.box_y_min}px;
      left: {plan.hero.center_x}px;
      transform: translateX(-50%);
      width: 600px;
      height: 600px;
      z-index: 20;
      pointer-events: none;
    }}

    .curved-events-svg {{
      width: 100%;
      height: 100%;
      overflow: visible;
    }}

    .orbital-text {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 21px;
      font-weight: 800;
      letter-spacing: 0.16em;
      fill: {plan.palette.hero_glow_hex};
      filter: drop-shadow(0 0 12px rgba(122, 231, 199, 0.85)) drop-shadow(0 2px 14px rgba(0, 0, 0, 0.95));
    }}

    .events-microcopy-pill {{
      position: absolute;
      top: {plan.hero.box_y_max - 50}px;
      left: {plan.hero.center_x}px;
      transform: translateX(-50%);
      font-family: 'JetBrains Mono', monospace;
      font-size: 16px;
      font-weight: 800;
      letter-spacing: 0.20em;
      color: {plan.palette.hero_highlight_hex};
      background: rgba(14, 7, 40, 0.65);
      padding: 4px 14px;
      border-radius: 4px;
      border: 1px solid rgba(255, 183, 3, 0.4);
      text-shadow: 0 0 12px rgba(255, 183, 3, 0.7);
      z-index: 21;
    }}

    /* SOFT GRADIENT SCRIM (NO OPAQUE CARD) */
    .layer-scrim {{
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 560px;
      background: linear-gradient(180deg, 
        transparent 0%, 
        rgba(14, 7, 40, 0.40) 20%, 
        rgba(14, 7, 40, 0.82) 55%, 
        rgba(14, 7, 40, 0.98) 90%, 
        {plan.palette.sky_deep_hex} 100%);
      z-index: 18;
      pointer-events: none;
    }}

    /* EDITORIAL INFO ELEMENTS DIRECTLY ON SCENE */
    .layer-scene-info {{
      position: absolute;
      bottom: 40px;
      left: 65px;
      right: 65px;
      z-index: 22;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}

    .info-date-venue-row {{
      display: grid;
      grid-template-columns: 1.1fr 1.4fr;
      gap: 28px;
      align-items: start;
      padding-bottom: 14px;
      border-bottom: 1px solid rgba(122, 231, 199, 0.25);
    }}

    .allowlist-label {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.14em;
      color: {plan.palette.text_muted_hex};
      margin-bottom: 6px;
    }}

    .date-display {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 34px;
      font-weight: 800;
      color: {plan.palette.hero_highlight_hex};
      line-height: 1.1;
      text-shadow: 0 0 20px rgba(255, 183, 3, 0.45);
    }}

    .venue-display {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 23px;
      font-weight: 700;
      color: {plan.palette.text_primary_hex};
      line-height: 1.25;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.85);
    }}

    .info-subtitle-prize-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }}

    .subtitle-display {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 23px;
      font-weight: 700;
      color: {plan.palette.text_primary_hex};
      letter-spacing: 0.02em;
      text-shadow: 0 2px 12px rgba(0, 0, 0, 0.85);
    }}

    .prize-badge {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 26px;
      font-weight: 800;
      color: {plan.palette.hero_accent_hex};
      white-space: nowrap;
      text-shadow: 0 0 20px rgba(255, 77, 109, 0.6);
      background: rgba(255, 77, 109, 0.16);
      padding: 7px 20px;
      border-radius: 8px;
      border: 1.5px solid {plan.palette.hero_accent_hex};
      box-shadow: 0 0 25px rgba(255, 77, 109, 0.35);
    }}

    .info-time-entry-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }}

    .time-display {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 22px;
      font-weight: 700;
      color: {plan.palette.text_primary_hex};
      letter-spacing: 0.02em;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.8);
    }}

    .entry-display {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 22px;
      font-weight: 600;
      color: {plan.palette.text_muted_hex};
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.8);
    }}

    .info-footer-container {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .footer-tier-1 {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }}

    .footer-tier-2 {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding-top: 6px;
    }}

    .cta-pill {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 22px;
      font-weight: 800;
      color: #0E0728;
      background: {plan.palette.hero_glow_hex};
      padding: 8px 24px;
      border-radius: 8px;
      box-shadow: 0 0 28px rgba(122, 231, 199, 0.55);
      white-space: nowrap;
    }}

    .organizer-display {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 21px;
      font-weight: 600;
      color: {plan.palette.text_muted_hex};
      white-space: nowrap;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.8);
    }}

    .contact-display {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 21px;
      font-weight: 600;
      color: {plan.palette.text_muted_hex};
      white-space: nowrap;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.8);
    }}

    .hashtag-display {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 22px;
      font-weight: 800;
      color: {plan.palette.hero_highlight_hex};
      background: rgba(255, 183, 3, 0.15);
      padding: 5px 16px;
      border-radius: 6px;
      border: 1px solid rgba(255, 183, 3, 0.45);
      text-shadow: 0 0 14px rgba(255, 183, 3, 0.5);
      white-space: nowrap;
    }}

    /* LAYER 6: UNIFIED COLOR GRADE & AMBIENT FILM GRAIN */
    .layer-color-grade {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      background: radial-gradient(circle at 50% 45%, rgba(122, 231, 199, 0.08) 0%, rgba(255, 77, 109, 0.06) 60%, transparent 80%);
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

    <!-- LAYER 0: BACKGROUND SCENE -->
    <div class="layer-background"></div>

    <!-- LAYER 1: LIGHT SPILL EMITTERS -->
    <div class="hero-light-spill"></div>
    <div class="lantern-light-spill"></div>

    <!-- LAYER 2: MASSIVE HEADLINE (LAYERED UNDER HERO ORB) -->
    <div class="layer-title-zone">
      <div class="tagline-verbatim">{tagline}</div>
      {title_html}
    </div>

    <!-- LAYER 3: HERO GLASS ORB (OVERLAPS LOWER CROWN OF TITLE) -->
    <div class="layer-hero-orb">
      <img src="{hero_img_path}" alt="Hero" class="orb-img" />
    </div>

    <!-- LAYER 4: FOREGROUND ACCENTS -->
    <img src="{accent_img_path}" alt="Accent" class="layer-foreground-lanterns" />

    <!-- LAYER 5: INTERACTING TYPOGRAPHY -->
    <div class="layer-orbital-events">
      <svg class="curved-events-svg" viewBox="0 0 600 600">
        <defs>
          <path id="orbital-arc-path" d="M 40,245 A 260,260 0 0,0 560,245" fill="none" />
        </defs>
        <text class="orbital-text">
          <textPath href="#orbital-arc-path" startOffset="50%" text-anchor="middle">
            {events_str}
          </textPath>
        </text>
      </svg>
    </div>

    <div class="events-microcopy-pill">// EVENTS</div>

    <!-- SOFT GRADIENT SCRIM (NO OPAQUE CARD) -->
    <div class="layer-scrim"></div>

    <!-- SCENE-INTEGRATED EDITORIAL INFO BLOCKS -->
    <div class="layer-scene-info">

      <!-- Row 1: Date + Venue -->
      <div class="info-date-venue-row">
        <div>
          <div class="allowlist-label">// DATE</div>
          <div class="date-display">{date_str}</div>
        </div>
        <div>
          <div class="allowlist-label">// VENUE</div>
          <div class="venue-display">{venue_str}</div>
        </div>
      </div>

      <!-- Row 2: Subtitle + Prize -->
      <div class="info-subtitle-prize-row">
        <div class="subtitle-display">{subtitle_str}</div>
        <div class="prize-badge">{prize_str}</div>
      </div>

      <!-- Row 3: Time + Entry -->
      <div class="info-time-entry-row">
        <div class="time-display">{time_str}</div>
        <div class="entry-display">{entry_str}</div>
      </div>

      <!-- Row 4: 2-Tier Footer -->
      <div class="info-footer-container">
        <div class="footer-tier-1">
          <div class="cta-pill">{cta_str}</div>
          <div class="organizer-display">{organizer_str}</div>
        </div>
        <div class="footer-tier-2">
          <div class="contact-display">{contact_str}</div>
          <div class="hashtag-display">{hashtag_str}</div>
        </div>
      </div>

    </div>

    <!-- LAYER 6: UNIFIED COLOR GRADE & AMBIENT FILM GRAIN -->
    <div class="layer-color-grade"></div>
    <svg class="layer-film-grain" xmlns="http://www.w3.org/2000/svg">
      <filter id="noiseFilter"><feTurbulence type="fractalNoise" baseFrequency="0.75" numOctaves="3" stitchTiles="stitch"/></filter>
      <rect width="100%" height="100%" filter="url(#noiseFilter)"/>
    </svg>

  </div>

</body>
</html>
"""

    def render(
        self,
        html_content: str,
        output_png: Path | str,
        scale_factor: int = 2,
    ) -> Path:
        """Render HTML string to 2x PNG via Playwright."""
        out_p = Path(output_png).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        temp_html = out_p.with_suffix(".html")
        temp_html.write_text(html_content, encoding="utf-8")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1080, "height": 1350},
                device_scale_factor=scale_factor,
            )
            page.goto(temp_html.as_uri(), wait_until="networkidle")
            page.wait_for_timeout(500)
            canvas = page.locator(".poster-canvas")
            canvas.screenshot(path=str(out_p))
            browser.close()

        return out_p
