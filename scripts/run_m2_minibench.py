"""M2 Mini-Benchmark: 3 briefs x 3 runs each.

Evaluates pipeline reproducibility, gate variance, tool calls, and execution times
across independent runs of the agentic poster designer.
Persists report to runs/m2_minibench_report.json.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from poster_agent.agentic.pipeline import AgenticPosterPipeline

BRIEFS = [
    {
        "id": "c4_recruitment",
        "name": "GDG KCT Recruitment",
        "file": PROJECT_ROOT / "briefs" / "brief_c4_demo.txt",
    },
    {
        "id": "noir_beats",
        "name": "Noir Beats 2026",
        "file": PROJECT_ROOT / "briefs" / "brief_noir_beats.txt",
    },
    {
        "id": "robotics_demoday",
        "name": "Robotics Demo Day",
        "file": PROJECT_ROOT / "briefs" / "brief_robotics_demoday.txt",
    },
]


def run_minibench(repeats: int = 3) -> dict[str, Any]:
    pipeline = AgenticPosterPipeline()
    runs_dir = PROJECT_ROOT / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    benchmark_records = []
    print("=" * 80)
    print(f"STARTING M2 MINI-BENCHMARK: {len(BRIEFS)} briefs x {repeats} repetitions")
    print("=" * 80)

    for b_idx, b in enumerate(BRIEFS):
        brief_id = b["id"]
        brief_file = b["file"]
        print(f"\n--- Brief {b_idx + 1}/{len(BRIEFS)}: {b['name']} ({brief_file.name}) ---")

        for rep in range(1, repeats + 1):
            run_id = f"m2_bench_{brief_id}_run{rep}"
            t0 = time.time()
            plan = pipeline.run(
                brief_file=brief_file,
                run_id=run_id,
                allow_generation=False,
            )
            elapsed = time.time() - t0

            gate_res = plan.get("gate_results", {})
            rec = {
                "brief_id": brief_id,
                "brief_file": str(brief_file.relative_to(PROJECT_ROOT)),
                "run_id": run_id,
                "rep": rep,
                "status": plan.get("status"),
                "passed": gate_res.get("passed", False),
                "failure_count": gate_res.get("failure_count", 0),
                "v_band_coverage_pct": gate_res.get("v_band_coverage_pct", 0.0),
                "total_tool_calls": plan.get("total_tool_calls", 0),
                "wall_time_sec": round(elapsed, 2),
                "deliverables": plan.get("deliverables", {}),
            }
            benchmark_records.append(rec)
            status_str = f"PASS ({rec['v_band_coverage_pct']}% v-band)" if rec["passed"] else f"FAIL ({rec['failure_count']} gates)"
            print(f"  Rep {rep}: {rec['run_id']} -> {status_str} in {rec['wall_time_sec']}s")

    # Compute variance stats per brief
    brief_stats = {}
    for b in BRIEFS:
        b_id = b["id"]
        recs = [r for r in benchmark_records if r["brief_id"] == b_id]
        pass_count = sum(1 for r in recs if r["passed"])
        times = [r["wall_time_sec"] for r in recs]
        tool_counts = [r["total_tool_calls"] for r in recs]
        coverages = [r["v_band_coverage_pct"] for r in recs]

        mean_time = sum(times) / len(times) if times else 0.0
        var_time = sum((t - mean_time) ** 2 for t in times) / len(times) if times else 0.0

        brief_stats[b_id] = {
            "name": b["name"],
            "total_runs": len(recs),
            "pass_count": pass_count,
            "pass_rate_pct": (pass_count / len(recs) * 100.0) if recs else 0.0,
            "mean_wall_time_sec": round(mean_time, 2),
            "std_wall_time_sec": round(var_time ** 0.5, 2),
            "tool_calls": tool_counts,
            "v_band_coverages": coverages,
            "variance_zero": len(set(tool_counts)) <= 1 and len(set(coverages)) <= 1,
        }

    report = {
        "benchmark_name": "M2 Mini-Benchmark (3 briefs x 3 runs)",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_runs": len(benchmark_records),
        "overall_pass_rate_pct": (sum(1 for r in benchmark_records if r["passed"]) / len(benchmark_records) * 100.0),
        "brief_stats": brief_stats,
        "runs": benchmark_records,
    }

    report_path = PROJECT_ROOT / "runs" / "m2_minibench_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print(f"MINI-BENCHMARK COMPLETE: {report['overall_pass_rate_pct']:.1f}% Overall Pass Rate")
    print(f"Report saved to: {report_path.relative_to(PROJECT_ROOT)}")
    print("=" * 80)

    return report


if __name__ == "__main__":
    run_minibench()
