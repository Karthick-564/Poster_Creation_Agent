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
    output_dir: str | None = None,
):
    print("=" * 60)
    print("POSTER-AGENT: AUTONOMOUS POSTER GENERATION PIPELINE")
    print("=" * 60)

    cfg = get_config()
    context = load_context()

    inst_name = context.college_details.get("name", "Apex Institute of Technology")
    print(f"\n[1/5] Loaded Institutional Context: {inst_name}")
    print(f"      Available Assets: {context.asset_files}")

    # 1. Planner
    print("\n[2/5] Synthesizing Poster Blueprint (Planner)...")
    planner = PosterPlanner(config=cfg)

    # If GROQ_API_KEY is not set or mock requested, build a compliant spec via Template
    if not os.environ.get("GROQ_API_KEY") or use_mock:
        print("      (Using Template Library planner for local execution)")
        lib = TemplateLibrary()
        tpl = lib.get("event_portrait_hero")
        # Extract title from brief
        lines = [line.strip() for line in brief_text.splitlines() if line.strip()]
        title = lines[0].replace("Event Name:", "").replace("Title:", "").strip() if lines else "Apex Tech Hackathon 2026"
        date_line = next((l.replace("Date:", "").strip() for l in lines if l.startswith("Date:")), "November 12-14, 2026")
        venue_line = next((l.replace("Venue:", "").strip() for l in lines if l.startswith("Venue:")), "Auditorium Hall, Apex Institute")

        from poster_agent.spec.models import PosterSpec, BBox, TextElement, LogoPlacement
        spec = PosterSpec(
            canvas_width_px=tpl.canvas_width_px if tpl else 1200,
            canvas_height_px=tpl.canvas_height_px if tpl else 1600,
            dpi=300,
            template_id="event_portrait_hero",
            palette=["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"],
            text_safe_zones=[BBox(y_min=180, x_min=50, y_max=900, x_max=950)],
            elements=[
                TextElement(
                    id="headline_1",
                    role="headline",
                    text=title,
                    source="brief",
                    font="Outfit",
                    size=36,
                    weight=800,
                    color="#FFFFFF",
                    box=BBox(y_min=180, x_min=80, y_max=280, x_max=920),
                ),
                TextElement(
                    id="date_1",
                    role="date",
                    text=date_line,
                    source="brief",
                    font="Inter",
                    size=20,
                    weight=600,
                    color="#00F5D4",
                    box=BBox(y_min=750, x_min=80, y_max=810, x_max=600),
                ),
                TextElement(
                    id="venue_1",
                    role="venue",
                    text=venue_line,
                    source="brief",
                    font="Inter",
                    size=18,
                    weight=500,
                    color="#FFFFFF",
                    box=BBox(y_min=820, x_min=80, y_max=870, x_max=800),
                ),
            ],
            logos=[
                LogoPlacement(
                    file="college_logo.png",
                    box=BBox(y_min=40, x_min=80, y_max=120, x_max=350),
                    clear_space_px=20,
                )
            ],
            art_slots=[],
            assumptions=["Automated template instantiation"],
            missing_fields=[],
            qr_code="https://apextech.edu",
        )
    else:
        spec = planner.plan(requirements_text=brief_text, context=context)

    print(f"      Selected Template: {spec.template_id}")
    print(f"      Elements planned: {len(spec.elements)} text, {len(spec.logos)} logos")

    # 2. Generator adapter
    if use_mock:
        print("\n[3/5] Initializing Mock Generator Adapter...")
        generator = MockGenerator()
    else:
        print("\n[3/5] Initializing Ideogram Generator Adapter (Transport: ComfyUI)...")
        generator = IdeogramGenerator()

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
        requirements_text=brief_text,
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
    )


if __name__ == "__main__":
    main()
