"""End-to-End CLI to generate an error-free promotional poster from a brief."""
import argparse
import json
import os
import re
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from poster_agent.config.settings import get_config
from poster_agent.context.loader import load_context
from poster_agent.planner.planner import PosterPlanner
from poster_agent.planner.templates import TemplateLibrary
from poster_agent.generators.mock import MockGenerator
from poster_agent.generators.ideogram import IdeogramGenerator
from poster_agent.generators.comfyui_client import ComfyUIClient
from poster_agent.renderer.renderer import PosterRenderer
from poster_agent.renderer.blended_layered_renderer import BlendedLayeredRenderer
from poster_agent.vision.art_analyzer import ArtAnalyzer
from poster_agent.checks.runner import CheckRunner
from poster_agent.reviewer.reviewer import PosterReviewer
from poster_agent.loop.repair import RepairLoop


def parse_brief_dict(brief_text: str) -> tuple[dict[str, str], dict[str, str]]:
    """Parse raw brief text into structured text fields and generative art prompts."""
    clean = (
        brief_text.replace("\\n", "\n")
        .replace("`n", "\n")
        .replace("\r", "")
        .strip()
    )

    fields: dict[str, str] = {}
    
    # Text extractions
    patterns = {
        "title": r"(?:^|\n)\s*(?:Event\s+Title|Title)\s*:\s*([^\n]+)",
        "tagline": r"(?:^|\n)\s*(?:Tagline|Theme)\s*:\s*([^\n]+)",
        "subtitle": r"(?:^|\n)\s*(?:Subtitle)\s*:\s*([^\n]+)",
        "date": r"(?:^|\n)\s*(?:Date|When)\s*:\s*([^\n]+)",
        "time": r"(?:^|\n)\s*(?:Time)\s*:\s*([^\n]+)",
        "venue": r"(?:^|\n)\s*(?:Venue|Location|Where)\s*:\s*([^\n]+)",
        "events": r"(?:^|\n)\s*(?:Events|Tracks|Highlights)\s*:\s*([^\n]+)",
        "prize": r"(?:^|\n)\s*(?:Prize\s*(?:line)?|Prizes)\s*:\s*([^\n]+)",
        "entry": r"(?:^|\n)\s*(?:Entry|Tickets)\s*:\s*([^\n]+)",
        "cta": r"(?:^|\n)\s*(?:CTA|Register|Action)\s*:\s*([^\n]+)",
        "contact": r"(?:^|\n)\s*(?:Contact|Email)\s*:\s*([^\n]+)",
        "hashtag": r"(?:^|\n)\s*(?:Hashtag)\s*:\s*([^\n]+)",
        "organizer": r"(?:^|\n)\s*(?:Organizer|Presented\s*by)\s*:\s*([^\n]+)",
    }

    for key, pat in patterns.items():
        m = re.search(pat, clean, re.IGNORECASE)
        if m:
            fields[key] = m.group(1).strip()

    # Fallback for Title if not explicitly labeled
    if "title" not in fields:
        lines = [l.strip() for l in clean.splitlines() if l.strip()]
        known_prefixes = [
            "title:", "tagline:", "theme:", "subtitle:", "date:", "when:", "venue:", "where:",
            "location:", "time:", "events:", "tracks:", "highlights:", "prize", "entry:", "tickets:",
            "cta:", "register:", "action:", "contact:", "email:", "hashtag:", "organizer:", "presented",
            "brief", "format:", "size:", "output:", "text content", "style:", "mood:", "palette:",
            "layout rules", "hard constraints"
        ]
        for line in lines:
            if not any(line.lower().startswith(k) for k in known_prefixes) or "brief:" in line.lower():
                raw_t = re.sub(r"^(?:(?:POSTER\s+)?BRIEF|EVENT(?:\s+NAME)?|TITLE)\s*:\s*", "", line, flags=re.IGNORECASE).strip()
                fields["title"] = re.sub(r"^[#-*\s]+", "", raw_t).strip()
                break

    # Defaults for standard display
    fields.setdefault("title", "TECH FEST 2026")
    fields.setdefault("tagline", "Where code meets creativity.")
    fields.setdefault("subtitle", "INTER-COLLEGE ANNUAL FESTIVAL")
    fields.setdefault("date", "12-14 FEBRUARY 2027")
    fields.setdefault("time", "10:00 AM - 6:00 PM DAILY")
    fields.setdefault("venue", "CENTRAL AUDITORIUM, MAIN CAMPUS")
    fields.setdefault("events", "HACKATHON / ROBO WARS / WORKSHOPS / GAMING")
    fields.setdefault("prize", "PRIZES WORTH ₹2,00,000")
    fields.setdefault("entry", "Free entry with student ID")
    fields.setdefault("cta", "REGISTER: fest2026.example/join")
    fields.setdefault("contact", "contact@fest2026.example")
    fields.setdefault("hashtag", "#Fest2026")
    fields.setdefault("organizer", "Presented by Student Council")

    # Art prompts extraction
    mood_match = re.search(r"(?:Mood|Style)\s*:\s*([^\n]+)", clean, re.IGNORECASE)
    mood = mood_match.group(1).strip() if mood_match else "dreamy, futuristic, warm night sky with aurora light"

    palette_matches = re.findall(r"#[0-9a-fA-F]{6}", clean)
    palette = palette_matches if palette_matches else ["#1B1040", "#7AE7C7", "#FF4D6D", "#FFB703"]

    art_prompts = {
        "mood": mood,
        "palette": palette,
        "bg_prompt": f"Poster background art: {mood}. Luminous lighting, cosmic gradients, deep negative space for text. Color theme: {', '.join(palette)}.",
        "hero_prompt": f"A single stunning glowing 3D symbolic graphic hero asset matching {fields['title']} and mood of {mood}. Ethereal crystal glass, volumetric lighting, isolated on empty alpha channel, transparent background, clean sticker cutout, 3D render, sharp edges, no words, no hands.",
        "accent_prompt": f"Small floating atmospheric glowing accent elements matching {mood}. Isolated on empty alpha channel, transparent background, clean sticker cutout, warm candlelight.",
        "title_prompt": f"Sculpted 3D text typography spelling '{fields['title']}'. Polished chrome and vibrant glass ribbons with glowing edges, isolated on empty alpha channel, transparent background, sharp edges.",
    }

    return fields, art_prompts


def run_art_first_pipeline(
    brief_text: str,
    output_dir: str = "runs/exports",
    title_mode: str = "path2_3d",
    scale_factor: int = 2,
    existing_assets_dir: str | None = None,
):
    """Fully automated Art-First, Vision-Assisted Depth-Layered Pipeline."""
    print("=" * 60)
    print("POSTER-AGENT: AUTONOMOUS ART-FIRST BLENDED PIPELINE")
    print("=" * 60)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Parse Brief
    print("\n[1/5] Extracting Verbatim Fields & Synthesizing Generative Art Prompts...")
    fields, art_prompts = parse_brief_dict(brief_text)
    print(f"      Title: {fields['title']}")
    print(f"      Date: {fields['date']} | Venue: {fields['venue']}")
    print(f"      Palette: {art_prompts['palette']}")

    # 2. Asset Generation (ComfyUI)
    slug = fields["title"].lower().replace(" ", "_")
    run_assets_dir = out_path / "assets" / slug
    run_assets_dir.mkdir(parents=True, exist_ok=True)

    bg_path = run_assets_dir / "bg.png"
    hero_path = run_assets_dir / "hero_rgba.png"
    accent_path = run_assets_dir / "accent_rgba.png"
    title_path = run_assets_dir / "title_3d_rgba.png"

    # Check if pre-existing assets can be reused (e.g. from brain directory)
    if existing_assets_dir and Path(existing_assets_dir).exists():
        e_dir = Path(existing_assets_dir)
        for f in e_dir.glob("*.png"):
            if "bg" in f.name.lower() and not bg_path.exists():
                import shutil; shutil.copyfile(f, bg_path)
            elif "orb" in f.name.lower() or "hero" in f.name.lower():
                if not hero_path.exists(): import shutil; shutil.copyfile(f, hero_path)
            elif "lantern" in f.name.lower() or "accent" in f.name.lower():
                if not accent_path.exists(): import shutil; shutil.copyfile(f, accent_path)
            elif "title" in f.name.lower():
                if not title_path.exists(): import shutil; shutil.copyfile(f, title_path)

    comfy = ComfyUIClient()
    if comfy.is_alive():
        print("\n[2/5] ComfyUI is online. Generating multi-layer assets autonomously...")
        if not bg_path.exists():
            print("      Generating Background via Ideogram 4.0...")
            comfy.generate_ideogram_background(
                description=art_prompts["bg_prompt"],
                palette=art_prompts["palette"],
                output_path=bg_path,
                prefix=f"{slug}_bg",
            )
        if not hero_path.exists():
            print("      Generating Hero Cutout via Qwen-Image 2.1 native alpha...")
            comfy.generate_qwen_rgba(
                prompt=art_prompts["hero_prompt"],
                output_path=hero_path,
                prefix=f"{slug}_hero",
            )
        if not accent_path.exists():
            print("      Generating Accent Cutout via Qwen-Image 2.1 native alpha...")
            comfy.generate_qwen_rgba(
                prompt=art_prompts["accent_prompt"],
                output_path=accent_path,
                prefix=f"{slug}_accent",
            )
        if title_mode == "path2_3d" and not title_path.exists():
            print("      Generating 3D Headline Typography Cutout via Qwen-Image 2.1...")
            comfy.generate_qwen_rgba(
                prompt=art_prompts["title_prompt"],
                output_path=title_path,
                prefix=f"{slug}_title",
            )
    else:
        print("\n[2/5] ComfyUI offline or assets already available. Using cached/local assets...")

    # 3. Vision Analysis
    print("\n[3/5] Inspecting Generated Art with Vision Analyzer...")
    analyzer = ArtAnalyzer()
    plan = analyzer.analyze(
        bg_path=bg_path if bg_path.exists() else None,
        hero_rgba_path=hero_path if hero_path.exists() else None,
        accent_rgba_path=accent_path if accent_path.exists() else None,
    )
    print(f"      Sampled Glow Tone: {plan.palette.hero_glow_hex}")
    print(f"      Sampled Highlight: {plan.palette.hero_highlight_hex}")
    print(f"      Hero Geometry: Center=({plan.hero.center_x}, {plan.hero.center_y}), Radius={plan.hero.radius}px")
    print(f"      Orbital Arc Path: {plan.orbital_arc.svg_path_d}")

    # 4. Compose Depth-Layered HTML
    print("\n[4/5] Synthesizing Depth-Layered Layout (Z-Stacking, Light Spill & Arc Typography)...")
    renderer = BlendedLayeredRenderer()
    html_content = renderer.compose_html(
        plan=plan,
        brief_data=fields,
        title_mode=title_mode if title_path.exists() else "path3_infill",
        bg_img_path=str(bg_path).replace("\\", "/"),
        hero_img_path=str(hero_path).replace("\\", "/"),
        accent_img_path=str(accent_path).replace("\\", "/"),
        title_3d_img_path=str(title_path).replace("\\", "/"),
    )

    # 5. Render at 2x via Playwright
    output_png = out_path / f"{slug}_{title_mode}_2x.png"
    print(f"\n[5/5] Rendering 2x Pixel-Exact Composite via Playwright...")
    rendered_png = renderer.render(
        html_content=html_content,
        output_png=output_png,
        scale_factor=scale_factor,
    )
    print(f"      Master Rendered Output: {rendered_png}")

    print("\n" + "=" * 60)
    print(f"PIPELINE COMPLETE. Master file ready at: {rendered_png}")
    print("=" * 60)
    return rendered_png


def main():
    parser = argparse.ArgumentParser(description="Generate a validated promotional poster.")
    parser.add_argument("--brief", type=str, help="Plain language requirements string.")
    parser.add_argument("--brief-file", type=str, help="Path to text file containing the brief.")
    parser.add_argument("--mock", action="store_true", help="Use mock generator for fast test runs.")
    parser.add_argument("--strategy", type=str, choices=["A", "B"], default="B", help="Strategy A or B.")
    parser.add_argument("--output-dir", type=str, default=None, help="Destination directory.")
    parser.add_argument("--skip-review", action="store_true", help="Skip vision model review critique.")
    parser.add_argument("--art-first", action="store_true", help="Execute the Art-First, Vision-Assisted Depth-Layered pipeline.")
    parser.add_argument("--assets-dir", type=str, default=None, help="Optional directory with pre-generated assets.")
    args = parser.parse_args()

    # Read brief
    if args.brief_file:
        brief_text = Path(args.brief_file).read_text(encoding="utf-8")
    elif args.brief:
        brief_text = args.brief
    else:
        brief_text = """AURORA 2026
Tagline: Where code meets culture.
Subtitle: INTER-COLLEGE TECH & CULTURE FEST
Date: 12-14 FEBRUARY 2027
Time: 10:00 AM - 6:00 PM DAILY
Venue: CENTRAL AUDITORIUM, GREEN VALLEY COLLEGE, COIMBATORE
Events: HACKATHON / ROBO WARS / DANCE / OPEN MIC
Prize line: PRIZES WORTH ₹2,00,000
Entry: Free entry with college ID
CTA: REGISTER: aurora26.example/join
Contact: queries@aurora26.example
Hashtag: #Aurora26
Organizer: Presented by the Student Council
Style: warm, festive, dreamy night sky with aurora light
Palette: #1B1040, #FF4D6D, #FFB703, #FFF3E0, #7AE7C7, #C9B8FF"""

    if args.art_first:
        run_art_first_pipeline(
            brief_text=brief_text,
            output_dir=args.output_dir or "runs/exports",
            title_mode="path2_3d",
            existing_assets_dir=args.assets_dir or r"C:\Users\iQube\.gemini\antigravity\brain\98f40bc9-b037-4830-8e36-54702f37f83a",
        )
        return

    run_pipeline(
        brief_text=brief_text,
        use_mock=args.mock,
        run_review=not args.skip_review,
        strategy=args.strategy,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
