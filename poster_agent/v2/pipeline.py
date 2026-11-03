"""Orchestration for the v2 poster pipeline.

Stages are explicit and each deterministic failure routes back to the stage
that can repair it: art to ``assets``, geometry/copy to ``plan``, raster
assembly to ``compose``. A VLM review is optional and runs only after the
deterministic suite passes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from poster_agent.ingestion.extractor import BriefExtractor, ExtractedBrief

from .assets import AssetBroker, MockAssetBroker
from .brand import get_brand, resolve_format
from .composer import MockRenderer
from .contracts import (
    AttemptRecord,
    BrandContract,
    PipelineResult,
    PosterSpec,
    RenderResult,
    ReviewResult,
)
from .gates import run_gates
from .planner import KCTPlanner, rescale_logo_to_asset
from .reviewer import Reviewer


class Pipeline:
    """One core, two frontends: batch CLI and (later) the MCP designer."""

    def __init__(
        self,
        broker: AssetBroker | None = None,
        renderer=None,
        planner: KCTPlanner | None = None,
        reviewer: Reviewer | None = None,
        brand: BrandContract | None = None,
        brand_path: str | Path | None = None,
        max_asset_attempts: int = 2,
        max_compose_attempts: int = 2,
    ):
        self.broker = broker
        self.renderer = renderer or MockRenderer()
        self.planner = planner or KCTPlanner()
        self.reviewer = reviewer
        self.brand = brand
        self.brand_path = brand_path
        self.max_asset_attempts = max_asset_attempts
        self.max_compose_attempts = max_compose_attempts

    def run(
        self,
        brief_text: str,
        school_id: str = "KCT",
        format_name: str = "story",
        output_dir: str | Path = "runs/v2",
        allow_placeholder_logo: bool = True,
        ocr_lines: Iterable[str] | None = None,
        max_candidates: int | None = None,
    ) -> PipelineResult:
        brand = self.brand or get_brand(school_id, self.brand_path)
        fmt = resolve_format(brand, format_name)
        brief = BriefExtractor().extract(brief_text)
        run_dir = Path(output_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        broker = self.broker or MockAssetBroker(
            run_dir / "assets",
            allow_placeholder_logo=allow_placeholder_logo,
        )

        attempts: list[AttemptRecord] = []
        candidates = self.planner.plan_candidates(brief, brand, fmt)
        if max_candidates is not None:
            candidates = candidates[: max(1, max_candidates)]

        best: PipelineResult | None = None
        best_review: PipelineResult | None = None
        best_review_score = -1.0
        best_blocking = 10_000

        for candidate_index, spec in enumerate(candidates):
            asset_attempt = 0
            compose_attempt = 0
            assets = None
            while True:
                if assets is None:
                    asset_attempt += 1
                    assets = broker.provide(spec, brand, force=asset_attempt > 1)
                    if assets.logo:
                        spec = rescale_logo_to_asset(spec, brand, assets.logo.width, assets.logo.height)

                compose_attempt += 1
                output_path = run_dir / (
                    f"{brand.school_id.lower()}_{spec.candidate_id}"
                    f"_a{asset_attempt}_c{compose_attempt}.png"
                )
                try:
                    render = self.renderer.render(
                        spec=spec,
                        assets=assets,
                        brand=brand,
                        output_path=output_path,
                        work_dir=run_dir,
                    )
                except Exception as exc:
                    attempts.append(
                        AttemptRecord(
                            attempt=len(attempts) + 1,
                            candidate_id=spec.candidate_id,
                            stage="compose",
                            outcome="failed",
                            detail=f"renderer error: {exc}",
                        )
                    )
                    if compose_attempt < self.max_compose_attempts:
                        continue
                    break

                gates = run_gates(spec, assets, brand, render, ocr_lines=ocr_lines)
                blocking_count = len(gates.blocking)
                attempts.append(
                    AttemptRecord(
                        attempt=len(attempts) + 1,
                        candidate_id=spec.candidate_id,
                        stage=gates.primary_stage() or "compose",
                        outcome="passed" if gates.passed else "failed",
                        detail=(
                            "deterministic gates passed"
                            if gates.passed
                            else f"{blocking_count} blocking: "
                            + ", ".join(sorted({i.code for i in gates.blocking})[:6])
                        ),
                    )
                )

                result = PipelineResult(
                    success=gates.passed,
                    school_id=brand.school_id,
                    spec=spec,
                    assets=assets,
                    render=render,
                    gates=gates,
                    attempts=list(attempts),
                    output_path=str(output_path),
                )

                if gates.passed:
                    review = self._review(render, spec, brand)
                    if review is not None:
                        result.review = review
                        if review.blocking or review.score < brand.review_threshold:
                            result.success = False
                            result.message = (
                                f"VLM review score {review.score:.1f} below threshold "
                                f"{brand.review_threshold:.1f}."
                            )
                            attempts.append(
                                AttemptRecord(
                                    attempt=len(attempts) + 1,
                                    candidate_id=spec.candidate_id,
                                    stage="review",
                                    outcome="failed",
                                    detail=result.message,
                                )
                            )
                            result.attempts = list(attempts)
                            if review.score > best_review_score:
                                best_review = result
                                best_review_score = review.score
                            # Try the next candidate rather than shipping a weak poster.
                            break
                    result.success = True
                    if review is None:
                        result.message = "Passed deterministic gates."
                    elif any(issue.code == "review_unavailable" for issue in review.issues):
                        result.message = "Passed deterministic gates; VLM review unavailable."
                    else:
                        result.message = "Passed deterministic gates and VLM review."
                    return result

                if blocking_count < best_blocking:
                    best_blocking = blocking_count
                    best = result

                route = gates.primary_stage()
                if route == "plan":
                    break  # next candidate
                if route == "assets" and asset_attempt < self.max_asset_attempts:
                    assets = None
                    compose_attempt = 0
                    continue
                if route == "compose" and compose_attempt < self.max_compose_attempts:
                    continue
                break

            # If the asset broker cannot fix it, move to the next candidate.

        if best_review is not None:
            if best_review_score < brand.review_threshold:
                reason = (
                    f"best craft score {best_review_score:.1f} is below threshold "
                    f"{brand.review_threshold:.1f}"
                )
            else:
                reason = f"best craft score {best_review_score:.1f} has a blocking review issue"
            best_review.message = (
                f"No candidate passed VLM review after {len(attempts)} attempt(s); {reason}."
            )
            best_review.attempts = list(attempts)
            return best_review

        if best is None:
            raise RuntimeError("No candidate produced a renderable result.")
        best.message = (
            f"No candidate passed all gates after {len(attempts)} attempt(s); "
            f"best candidate has {best_blocking} blocking issue(s)."
        )
        return best

    def _review(self, render: RenderResult, spec: PosterSpec, brand: BrandContract) -> ReviewResult | None:
        if not self.reviewer or not render.output_png:
            return None
        return self.reviewer.review(render.output_png, spec, brand)
