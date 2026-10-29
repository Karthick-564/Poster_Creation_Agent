"""End-to-End CLI to generate an error-free promotional poster from a brief."""
import argparse
import os
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
from poster_agent.renderer.renderer import PosterRenderer
from poster_agent.checks.runner import CheckRunner
from poster_agent.reviewer.reviewer import PosterReviewer
from poster_agent.loop.repair import RepairLoop


def run_pipeline(
    brief_text: str,
    use_mock: bool = False,
    run_review: bool = True,
    strategy: str | None = None,
    output_dir: str | None = None,
):
    print("=" * 60)
    print("POSTER-AGENT: AUTONOMOUS POSTER GENERATION PIPELINE")
    print("=" * 60)

    cfg = get_config()
    if strategy:
        cfg.ideogram.strategy = strategy
    context = load_context()

    inst_name = context.college_details.get("name", "Apex Institute of Technology")
    print(f"\n[1/5] Loaded Institutional Context: {inst_name}")
    print(f"      Available Assets: {context.asset_files}")

    # 1. Planner
    print("\n[2/5] Synthesizing Poster Blueprint (Planner)...")
    planner = PosterPlanner(config=cfg)

    # Normalize any escaped newlines and fix encoding/mojibake passed from command line shells
    clean_brief = (
        brief_text.replace("\\n", "\n")
        .replace("`n", "\n")
        .replace("\r", "")
        .replace("Â·", " • ")
        .replace("Â", "")
        .strip()
    )

    # If GROQ_API_KEY is available, use intelligent LLM planning; otherwise fall back to Template
    spec = None
    if os.environ.get("GROQ_API_KEY"):
        try:
            print("      Synthesizing intelligent blueprint via Groq LPU (openai/gpt-oss-120b)...")
            spec = planner.plan(requirements_text=clean_brief, context=context)
            print("      Intelligent blueprint successfully generated and verified!")
        except Exception as e:
            print(f"      [Warning] Groq planning returned error: {e}. Falling back to Template Library.")
            spec = None

    if spec is None:
        print("      (Using Template Library planner)")
        import re
        lib = TemplateLibrary()
        tpl = lib.get("event_portrait_hero")

        # Parse rich multi-field brief
        date_match = re.search(r"(?:Date|When)\s*:\s*([^\n]+)", clean_brief, re.IGNORECASE)
        venue_match = re.search(r"(?:Venue|Location|Where)\s*:\s*([^\n]+)", clean_brief, re.IGNORECASE)
        theme_match = re.search(r"(?:Theme|Subtitle|Tagline)\s*:\s*([^\n]+)", clean_brief, re.IGNORECASE)
        tracks_match = re.search(r"(?:Tracks|Keynotes|Highlights)\s*:\s*([^\n]+)", clean_brief, re.IGNORECASE)
        cta_match = re.search(r"(?:CTA|Register|Action)\s*:\s*([^\n]+)", clean_brief, re.IGNORECASE)

        date_text = date_match.group(1).strip() if date_match else "December 5-7, 2026"
        venue_text = venue_match.group(1).strip() if venue_match else "Main Auditorium Hall, Apex Campus"
        theme_text = theme_match.group(1).strip() if theme_match else ""
        tracks_text = tracks_match.group(1).strip() if tracks_match else ""
        cta_text = cta_match.group(1).strip() if cta_match else ""

        # Title: first line not matching key patterns
        lines = [l.strip() for l in clean_brief.splitlines() if l.strip()]
        title = "Apex Tech Hackathon 2026"
        for line in lines:
            if not re.match(r"^(?:Date|When|Venue|Location|Where|Theme|Subtitle|Tagline|Tracks|Keynotes|Highlights|CTA|Register|Action)\s*:", line, re.IGNORECASE):
                title = re.sub(r"^(?:Event\s*(?:Name)?|Title)\s*:\s*", "", line, flags=re.IGNORECASE).strip()
                break

        canvas_w = tpl.canvas_width_px if tpl else 2480
        canvas_h = tpl.canvas_height_px if tpl else 3508

        from poster_agent.spec.models import PosterSpec, BBox, TextElement, LogoPlacement, ArtSlot
        
        elements_list = [
            TextElement(
                id="headline_1",
                role="headline",
                text=title,
                source="brief",
                font="Outfit",
                size=76,
                weight=900,
                color="#FFFFFF",
                box=BBox(y_min=110, x_min=60, y_max=220, x_max=940),
            ),
        ]

        if theme_text:
            elements_list.append(
                TextElement(
                    id="subhead_1",
                    role="subheadline",
                    text=theme_text,
                    source="brief",
                    font="Inter",
                    size=24,
                    weight=600,
                    color="#F1F5F9",
                    box=BBox(y_min=230, x_min=60, y_max=290, x_max=940),
                )
            )

        # Side-by-side metadata cards: Date (left) and Venue (right)
        elements_list.extend([
            TextElement(
                id="date_1",
                role="date",
                text=date_text,
                source="brief",
                font="Inter",
                size=22,
                weight=700,
                color="#00F5D4",
                box=BBox(y_min=730, x_min=60, y_max=800, x_max=480),
            ),
            TextElement(
                id="venue_1",
                role="venue",
                text=venue_text,
                source="brief",
                font="Inter",
                size=20,
                weight=700,
                color="#FFFFFF",
                box=BBox(y_min=730, x_min=510, y_max=800, x_max=940),
            ),
        ])

        if tracks_text:
            elements_list.append(
                TextElement(
                    id="tracks_1",
                    role="body",
                    text=tracks_text,
                    source="brief",
                    font="Inter",
                    size=16,
                    weight=500,
                    color="#E2E8F0",
                    box=BBox(y_min=820, x_min=60, y_max=880, x_max=940),
                )
            )

        if cta_text:
            elements_list.append(
                TextElement(
                    id="cta_1",
                    role="label",
                    text=cta_text,
                    source="brief",
                    font="Outfit",
                    size=16,
                    weight=800,
                    color="#00F5D4",
                    box=BBox(y_min=900, x_min=60, y_max=955, x_max=460),
                )
            )

        spec = PosterSpec(
            canvas_width_px=canvas_w,
            canvas_height_px=canvas_h,
            dpi=300,
            template_id="event_portrait_hero",
            palette=["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"],
            text_safe_zones=[BBox(y_min=100, x_min=50, y_max=960, x_max=950)],
            elements=elements_list,
            logos=[
                LogoPlacement(
                    file="college_logo.png",
                    box=BBox(y_min=20, x_min=60, y_max=80, x_max=280),
                    clear_space_px=8,
                )
            ],
            art_slots=[
                ArtSlot(
                    id="art_hero",
                    prompt=f"A breathtaking 3D futuristic conceptual graphic design artwork featuring an intricate glowing holographic neural core, luminous neon cyan and magenta energy rings, obsidian crystalline structures, dark cinematic atmosphere",
                    box=BBox(y_min=305, x_min=60, y_max=710, x_max=940),
                    transparent=False,
                )
            ],
            assumptions=["Multi-tiered editorial layout with verified spatial flow"],
            missing_fields=[],
            qr_code="https://apextech.edu/events/register",
        )

    print(f"      Selected Template: {spec.template_id}")
    print(f"      Elements planned: {len(spec.elements)} text, {len(spec.logos)} logos")

    # 2. Generator adapter
    if use_mock:
        print("\n[3/5] Initializing Mock Generator Adapter...")
        generator = MockGenerator()
    else:
        print("\n[3/5] Initializing Ideogram Generator Adapter (Transport: ComfyUI)...")
        generator = IdeogramGenerator(strategy=cfg.ideogram.strategy)

    renderer = PosterRenderer()
    runner = CheckRunner(
        min_contrast_ratio=cfg.checks.min_contrast_ratio,
        min_font_pt=cfg.checks.min_font_pt,
    )

    # 3. Repair Loop
    print("\n[4/5] Running Generation & Deterministic Quality Repair Loop...")
    loop = RepairLoop(
        generator=generator,
        renderer=renderer,
        runner=runner,
        config=cfg,
    )
    result = loop.run(
        spec=spec,
        requirements_text=clean_brief,
        context=context,
    )

    print(f"\n      Repair Loop Status: {result.status} (Iterations used: {result.iterations_used})")
    if result.best_candidate:
        png_p = result.best_candidate.render_result.png_path
        pdf_p = result.best_candidate.render_result.pdf_path
        print(f"      Rendered PNG: {png_p}")
        print(f"      Rendered PDF: {pdf_p}")
        print(f"      Checks: {result.best_candidate.blocking_count} blocking, {result.best_candidate.warning_count} warnings")

    # 4. Reviewer
    if run_review and result.best_candidate:
        print("\n[5/5] Vision Model Review & 3-Second Test Evaluation...")
        reviewer = PosterReviewer()
        review = reviewer.review(
            poster_image_path=result.best_candidate.render_result.png_path,
            spec=result.final_spec,
        )
        print(f"      Polish Score: {review.polish}/5")
        print(f"      Hierarchy: {review.hierarchy}/5 | Readability: {review.readability}/5")
        print(f"      3-Second Test Passed: {review.three_second_test.passed}")
        print(f"      Identified: '{review.three_second_test.event}' on '{review.three_second_test.date}'")
        if review.fixes:
            print(f"      Recommendations: {review.fixes}")

    print("\n" + "=" * 60)
    print(f"RUN COMPLETE. Artifacts stored in: {result.run_dir}")
    print("=" * 60)
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate a validated promotional poster.")
    parser.add_argument("--brief", type=str, help="Plain language requirements string.")
    parser.add_argument("--brief-file", type=str, help="Path to text file containing the brief.")
    parser.add_argument("--mock", action="store_true", help="Use mock generator for fast test runs.")
    parser.add_argument("--strategy", type=str, choices=["A", "B"], default="B", help="Strategy A (model renders typography) or B (DOM text).")
    parser.add_argument("--output-dir", type=str, default=None, help="Optional destination run directory.")
    parser.add_argument("--skip-review", action="store_true", help="Skip vision model review critique.")
    args = parser.parse_args()

    if args.brief_file:
        brief_text = Path(args.brief_file).read_text(encoding="utf-8")
    elif args.brief:
        brief_text = args.brief
    else:
        brief_text = "Apex Tech Hackathon 2026\nDate: November 12-14, 2026\nVenue: Auditorium Hall, Apex Institute"

    run_pipeline(
        brief_text=brief_text,
        use_mock=args.mock,
        run_review=not args.skip_review,
        strategy=args.strategy,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
