"""Bake-off evaluation script comparing reviewer configurations and measuring consistency, flaws, and latency."""
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root in python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from poster_agent.context.loader import load_context
from poster_agent.spec.models import PosterSpec, BBox, TextElement, LogoPlacement
from poster_agent.renderer.renderer import PosterRenderer
from poster_agent.reviewer.reviewer import PosterReviewer, ReviewResult


def create_sample_spec(title: str, date: str, venue: str) -> PosterSpec:
    return PosterSpec(
        canvas_width_px=1200,
        canvas_height_px=1600,
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
                text=date,
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
                text=venue,
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
        assumptions=["Bake-off benchmark layout"],
        missing_fields=[],
        qr_code="https://apextech.edu",
    )


def run_bakeoff(
    briefs_dir: Path | str = "scripts/bakeoff/briefs",
    output_dir: Path | str = "scripts/bakeoff/reports",
    runs_per_config: int = 2,
) -> dict[str, Any]:
    b_dir = Path(briefs_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    renderer = PosterRenderer()
    context = load_context()

    brief_files = sorted(list(b_dir.glob("*.txt")))
    if not brief_files:
        print("No brief files found in", briefs_dir)
        return {}

    configs_to_test = [
        {"name": "LFM3-VL-2B (Thinking ON)", "model": "LFM3-VL-2B", "thinking": True},
        {"name": "LFM3-VL-2B (Thinking OFF)", "model": "LFM3-VL-2B", "thinking": False},
    ]

    report_data: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "configs": [c["name"] for c in configs_to_test],
        "briefs_evaluated": [b.stem for b in brief_files],
        "results": {},
    }

    print("=" * 70)
    print("STARTING VISION REVIEWER BAKE-OFF BENCHMARK")
    print(f"Testing {len(configs_to_test)} configurations across {len(brief_files)} briefs.")
    print("=" * 70)

    for b_file in brief_files:
        b_name = b_file.stem
        lines = b_file.read_text(encoding="utf-8").splitlines()
        event_name = lines[0].replace("Event Name:", "").strip() if lines else "Event"
        date_line = next((l.replace("Date:", "").strip() for l in lines if l.startswith("Date:")), "TBD")
        venue_line = next((l.replace("Venue:", "").strip() for l in lines if l.startswith("Venue:")), "TBD")

        spec = create_sample_spec(title=event_name, date=date_line, venue=venue_line)
        temp_render_dir = out_dir / "temp_render"
        render_res = renderer.render(spec, temp_render_dir, strategy="B", base_name=b_name)

        report_data["results"][b_name] = {}

        for cfg in configs_to_test:
            cfg_name = cfg["name"]
            reviewer = PosterReviewer(model_name=cfg["model"], thinking_mode=cfg["thinking"])

            scores_hierarchy = []
            scores_balance = []
            scores_readability = []
            scores_polish = []
            three_second_passes = 0
            latencies = []

            for r in range(runs_per_config):
                res = reviewer.review(poster_image_path=render_res.png_path, spec=spec)
                scores_hierarchy.append(res.hierarchy)
                scores_balance.append(res.balance)
                scores_readability.append(res.readability)
                scores_polish.append(res.polish)
                if res.three_second_test.passed:
                    three_second_passes += 1
                latencies.append(res.latency_seconds)

            # Calculate metrics
            avg_polish = statistics.mean(scores_polish)
            polish_std = statistics.stdev(scores_polish) if len(scores_polish) > 1 else 0.0
            avg_latency = statistics.mean(latencies)

            metrics = {
                "avg_hierarchy": round(statistics.mean(scores_hierarchy), 2),
                "avg_balance": round(statistics.mean(scores_balance), 2),
                "avg_readability": round(statistics.mean(scores_readability), 2),
                "avg_polish": round(avg_polish, 2),
                "consistency_score": round(max(0.0, 1.0 - polish_std), 2),
                "three_second_pass_rate": f"{three_second_passes}/{runs_per_config}",
                "avg_latency_s": round(avg_latency, 2),
            }
            report_data["results"][b_name][cfg_name] = metrics
            print(f"[{b_name}] {cfg_name} -> Polish: {metrics['avg_polish']}, Latency: {metrics['avg_latency_s']}s")

    # Save JSON report
    report_json_path = out_dir / "bakeoff_results.json"
    report_json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

    # Generate Markdown Table Report
    md_lines = [
        "# Vision Reviewer Bake-Off Benchmark Report",
        f"**Date**: {report_data['timestamp']}",
        "",
        "| Brief | Reviewer Config | Polish (1-5) | Readability | Consistency | 3-Sec Pass | Avg Latency |",
        "|---|---|---|---|---|---|---|",
    ]

    for b_name, configs_dict in report_data["results"].items():
        for cfg_name, m in configs_dict.items():
            md_lines.append(
                f"| `{b_name}` | **{cfg_name}** | {m['avg_polish']}/5 | {m['avg_readability']}/5 | "
                f"{m['consistency_score'] * 100:.0f}% | {m['three_second_pass_rate']} | {m['avg_latency_s']}s |"
            )

    report_md_path = out_dir / "bakeoff_report.md"
    report_md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("\nBake-off complete! Reports saved:")
    print(" -", report_md_path)
    print(" -", report_json_path)

    return report_data


if __name__ == "__main__":
    run_bakeoff()

