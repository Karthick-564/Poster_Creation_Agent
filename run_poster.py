"""Single-Command Production CLI for Autonomous Poster Generation.

Usage:
  python run_poster.py --brief "POSTER BRIEF: ..."
  python run_poster.py --brief-file my_brief.txt
"""
import argparse
import sys
from pathlib import Path

# Ensure UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from poster_agent.unified_pipeline import UnifiedPosterPipeline


def main():
    parser = argparse.ArgumentParser(description="Autonomous Strict-Gated Poster Production CLI")
    parser.add_argument("--brief", type=str, help="Raw poster brief string")
    parser.add_argument("--brief-file", type=str, help="Path to text or markdown file containing the poster brief")
    parser.add_argument("--run-id", type=str, default=None, help="Optional unique run ID")
    parser.add_argument("--artifact-dir", type=str, default=None, help="Optional external directory to copy deliverables to")
    parser.add_argument("--mock", action="store_true", help="Run with mock generation without requiring ComfyUI")
    parser.add_argument("--context", type=str, default="", help="Optional additional institutional brand context")
    args = parser.parse_args()

    brief_text = ""
    if args.brief_file:
        file_path = Path(args.brief_file)
        if not file_path.exists():
            print(f"Error: Brief file not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        brief_text = file_path.read_text(encoding="utf-8")
    elif args.brief:
        brief_text = args.brief
    else:
        print("Error: Must provide either --brief or --brief-file", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    pipeline = UnifiedPosterPipeline(
        run_id=args.run_id,
        artifact_dir=args.artifact_dir,
        use_mock=args.mock,
    )
    result = pipeline.execute(brief_text=brief_text, context_text=args.context)
    print("\nCLI RESULT SUMMARY:")
    print(f"Master Print PDF : {result['pdf']}")
    print(f"2x Render PNG    : {result['png_2x']}")
    print(f"Score            : {result['score']}/10")
    print(f"Audit Markdown   : {result['report_md']}")


if __name__ == "__main__":
    main()

