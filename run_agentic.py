#!/usr/bin/env python3
"""CLI entrypoint for the Agentic Poster Designer pipeline."""
import argparse
from pathlib import Path
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from poster_agent.agentic.llm_backend import get_backend
from poster_agent.agentic.pipeline import AgenticPosterPipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Run Agentic Poster Designer pipeline.")
    parser.add_argument("--brief-file", type=str, default="briefs/brief_c4_demo.txt", help="Path to poster brief file")
    parser.add_argument("--run-id", type=str, default=None, help="Custom run identifier")
    parser.add_argument("--school", type=str, default=None, help="School brand key (KCT, KCLAS, KCTBS, KI, KIA)")
    parser.add_argument("--format", type=str, default=None, help="Format name (story, square, fourfive, A3, A4)")
    parser.add_argument("--allow-generation", action="store_true", help="Enable diffusion image generation (S3)")
    parser.add_argument("--replay", type=str, default=None, help="Replay existing run_id deterministically")
    parser.add_argument("--designer-role", type=str, default="designer", help="Designer role configured in agentic.yaml")
    parser.add_argument("--config", type=str, default=None, help="Path to custom agentic config YAML")
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 76)
    print(f"AGENTIC POSTER DESIGNER PIPELINE")
    if args.replay:
        print(f"Mode: REPLAY OF '{args.replay}'")
    else:
        print(f"Brief:  {args.brief_file}")
        print(f"School: {args.school or 'Auto-resolved'}")
        print(f"Format: {args.format or 'Auto-resolved'}")
        print(f"Diffusion Generation: {'ENABLED' if args.allow_generation else 'NATIVE/SUPPLIED ASSETS ONLY'}")
    print("=" * 76)

    # Initialize backend
    designer_backend = None
    if not args.replay:
        try:
            designer_backend = get_backend(role=args.designer_role, config_path=args.config)
            print(f"[Backend] Loaded {args.designer_role}: {designer_backend.__class__.__name__} ({designer_backend.model})")
        except Exception as e:
            print(f"[Backend] Note: Could not load live backend '{args.designer_role}' ({e}). Running with structured creative designer.")

    pipeline = AgenticPosterPipeline(
        project_root=PROJECT_ROOT,
        designer_backend=designer_backend,
        config_path=args.config,
    )

    plan = pipeline.run(
        brief_file=args.brief_file,
        run_id=args.run_id,
        school_id=args.school,
        format_name=args.format,
        allow_generation=args.allow_generation,
        replay_run_id=args.replay,
    )

    status = plan.get("status", "UNKNOWN")
    print(f"\n[DONE] Pipeline Status: {status}")
    if status in ("SUCCESS", "REPLAY_SUCCESS"):
        deliverables = plan.get("deliverables", {})
        print(f"  - Master Render: {deliverables.get('master_render_2x')}")
        print(f"  - Master PDF:    {deliverables.get('master_print_pdf')}")
        print(f"  - VCS Session:   {deliverables.get('session_vcs')}")
        print(f"  - Gates Passed:  {plan.get('gate_results', {}).get('passed')}")
        print(f"  - Tool Calls:    {plan.get('total_tool_calls')}")
        print(f"  - Wall Time:     {plan.get('wall_time_sec')}s")
    else:
        print(f"  - Halt Stage:    {plan.get('halt_stage')}")
        print(f"  - Reason:        {plan.get('reason')}")
        if plan.get("clarifying_question"):
            print(f"  - Question:      {plan.get('clarifying_question')}")


if __name__ == "__main__":
    main()

