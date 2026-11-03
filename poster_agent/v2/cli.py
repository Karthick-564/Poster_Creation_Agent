"""Batch CLI for the v2 poster core.

Examples:
    python -m poster_agent.v2.cli --brief-file briefs/brief_kct_v2_demo.txt
    python -m poster_agent.v2.cli --brief-file briefs/brief_kct_v2_demo.txt --mode live
"""
from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from .assets import ComfyUIAssetBroker, MockAssetBroker
from .composer import MockRenderer, VectorCraftComposer
from .pipeline import Pipeline
from .reviewer import StaticReviewer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KCT-first v2 poster pipeline")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--brief-file", type=Path, help="Path to a poster brief")
    source.add_argument("--brief", type=str, help="Inline poster brief text")
    parser.add_argument("--school", default="KCT")
    parser.add_argument("--format", default="story", dest="format_name")
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--out", type=Path, default=Path("runs/v2"))
    parser.add_argument("--endpoint", default="http://127.0.0.1:8188")
    parser.add_argument("--no-placeholder-logo", action="store_true")
    parser.add_argument("--review-score", type=float, default=None, help="Enable a static VLM stand-in score")
    parser.add_argument("--vlm-review", action="store_true", help="Run the live VLM critic after deterministic gates")
    parser.add_argument("--review-endpoint", default=None, help="OpenAI-compatible vision endpoint for --vlm-review")
    parser.add_argument("--json", action="store_true", help="Print the full audit trail as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    brief_text = args.brief_file.read_text(encoding="utf-8") if args.brief_file else args.brief

    if args.mode == "live":
        if platform.system() != "Windows":
            print(
                "Live mode needs the Windows VectorCraft binary. Run this command on Windows, "
                "or use --mode mock for offline verification.",
                file=sys.stderr,
            )
            return 2
        broker = ComfyUIAssetBroker(args.out / "assets", endpoint=args.endpoint)
        renderer = VectorCraftComposer()
    else:
        broker = MockAssetBroker(
            args.out / "assets",
            allow_placeholder_logo=not args.no_placeholder_logo,
        )
        renderer = MockRenderer()

    reviewer = StaticReviewer(score=args.review_score) if args.review_score is not None else None
    if reviewer is None and args.vlm_review:
        from poster_agent.config.settings import ReviewerConfig

        from .vlm_reviewer import PosterReviewerV2

        config = ReviewerConfig(endpoint=args.review_endpoint) if args.review_endpoint else None
        reviewer = PosterReviewerV2(config=config)
    pipeline = Pipeline(broker=broker, renderer=renderer, reviewer=reviewer)
    result = pipeline.run(
        brief_text=brief_text,
        school_id=args.school,
        format_name=args.format_name,
        output_dir=args.out,
        allow_placeholder_logo=not args.no_placeholder_logo,
    )

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        blocking = result.gates.blocking
        warnings = result.gates.warnings
        print(f"success: {result.success}")
        print(f"school: {result.school_id}")
        print(f"candidate: {result.spec.candidate_id}")
        print(f"output: {result.output_path}")
        print(f"gates: {'PASS' if result.gates.passed else 'FAIL'} "
              f"({len(blocking)} blocking, {len(warnings)} warnings)")
        for issue in blocking:
            print(f"  BLOCK [{issue.stage}/{issue.code}] {issue.message}")
        for issue in warnings:
            print(f"  WARN  [{issue.stage}/{issue.code}] {issue.message}")
        print(f"attempts: {len(result.attempts)}")
        print(f"message: {result.message}")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
