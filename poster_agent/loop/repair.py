"""Repair loop: iterative candidate generation, quality gating, cheapest-first automated repairs."""
import copy
from enum import Enum
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.config.settings import AppConfig, get_config
from poster_agent.context.loader import ContextBundle
from poster_agent.spec.models import PosterSpec, BBox
from poster_agent.generators.base import GeneratorAdapter, GeneratedArt
from poster_agent.renderer.renderer import PosterRenderer, RenderResult
from poster_agent.checks.models import CheckReport, CheckResult
from poster_agent.checks.runner import CheckRunner
from poster_agent.logging.run_log import RunLogger


class RepairAction(str, Enum):
    REFLOW_TEXT = "reflow_text"        # Re-render only: adjust font sizes/margins
    EDIT_SPEC = "edit_spec"            # Re-render only: adjust colors, logos, order
    NEW_SEED = "new_seed"              # Regenerate art with a new seed
    SWITCH_STRATEGY = "switch_strategy"# Switch between Strategy A and Strategy B


class CandidateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_index: int
    art: GeneratedArt
    render_result: RenderResult
    check_report: CheckReport
    blocking_count: int
    warning_count: int


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["SUCCESS", "FAILED"]
    best_candidate: CandidateResult | None
    iterations_used: int
    final_spec: PosterSpec
    run_dir: Path
    summary: str
    failure_reasons: list[str] = Field(default_factory=list)


def score_candidate(candidate: CandidateResult) -> float:
    """Calculate ranking score (lower is better; 0 blocking is required for success)."""
    # Each blocking error has heavy penalty (1000 pts), warning has minor penalty (10 pts)
    return (candidate.blocking_count * 1000.0) + (candidate.warning_count * 10.0)


class RepairLoop:
    """Executes the N-iteration generation and quality repair loop."""

    def __init__(
        self,
        generator: GeneratorAdapter,
        renderer: PosterRenderer,
        runner: CheckRunner,
        config: AppConfig | None = None,
    ):
        self.generator = generator
        self.renderer = renderer
        self.runner = runner
        self.config = config or get_config()

    def run(
        self,
        spec: PosterSpec,
        requirements_text: str,
        context: ContextBundle,
        base_dir: Path | str = "runs",
    ) -> RunResult:
        logger = RunLogger(requirements_text=requirements_text, base_dir=base_dir)
        logger.log_context(context)

        max_iterations = self.config.repair.max_iterations
        k_candidates = self.config.repair.candidates
        current_strategy = self.config.ideogram.strategy

        current_spec = spec.model_copy(deep=True)
        current_seed = 100000
        best_overall_candidate: CandidateResult | None = None
        actions_taken: list[str] = []

        cached_art_candidates: list[GeneratedArt] | None = None

        for iteration in range(1, max_iterations + 1):
            logger.log_spec_version(current_spec, iteration)
            it_dir = logger.get_iteration_dir(iteration)

            # 1. Art Generation (only if needed or first iteration)
            if cached_art_candidates is None:
                art_candidates = self.generator.generate(
                    spec=current_spec,
                    count=k_candidates,
                    base_seed=current_seed,
                    output_dir=it_dir,
                )
            else:
                art_candidates = cached_art_candidates

            candidate_results: list[CandidateResult] = []
            log_candidates_tuple = []

            # 2. Render & Check each candidate
            for idx, art in enumerate(art_candidates):
                render_res = self.renderer.render(
                    spec=current_spec,
                    output_dir=it_dir,
                    strategy=current_strategy,
                    art_image_path=art.image_path,
                    base_name=f"candidate_{idx + 1}",
                )

                check_rep = self.runner.run_all(
                    spec=current_spec,
                    context=context,
                    image_path=render_res.png_path,
                    dom_boxes=render_res.dom_boxes,
                )

                cand_res = CandidateResult(
                    candidate_index=idx + 1,
                    art=art,
                    render_result=render_res,
                    check_report=check_rep,
                    blocking_count=check_rep.blocking_count,
                    warning_count=check_rep.warning_count,
                )
                candidate_results.append(cand_res)
                log_candidates_tuple.append((idx + 1, render_res.png_path, check_rep))

            # 3. Select best candidate of this iteration
            candidate_results.sort(key=score_candidate)
            best_this_round = candidate_results[0]

            if best_overall_candidate is None or score_candidate(best_this_round) < score_candidate(best_overall_candidate):
                best_overall_candidate = best_this_round

            # 4. Check if clean pass achieved
            if best_this_round.blocking_count == 0:
                decision = f"Iteration {iteration}: Candidate {best_this_round.candidate_index} PASSED all blocking checks."
                logger.log_iteration(
                    iteration=iteration,
                    generator_payload=best_this_round.art.payload,
                    seed=best_this_round.art.seed,
                    candidates=log_candidates_tuple,
                    decision_text=decision,
                )
                logger.finalize_run(
                    status="SUCCESS",
                    best_png_path=best_this_round.render_result.png_path,
                    best_pdf_path=best_this_round.render_result.pdf_path,
                    final_spec=current_spec,
                    iterations_used=iteration,
                    repair_actions=actions_taken,
                )
                return RunResult(
                    status="SUCCESS",
                    best_candidate=best_this_round,
                    iterations_used=iteration,
                    final_spec=current_spec,
                    run_dir=logger.run_dir,
                    summary=f"SUCCESS in iteration {iteration}: {best_this_round.check_report.summary}",
                    failure_reasons=[],
                )

            # 5. Determine and apply cheapest repair action
            action, repair_desc = self._determine_repair_action(
                best_this_round.check_report, iteration
            )
            actions_taken.append(f"Iter {iteration}: {action.value} ({repair_desc})")

            decision = (
                f"Iteration {iteration}: Best Candidate {best_this_round.candidate_index} had "
                f"{best_this_round.blocking_count} blocking failures. Applying repair: {action.value} - {repair_desc}"
            )
            logger.log_iteration(
                iteration=iteration,
                generator_payload=best_this_round.art.payload,
                seed=best_this_round.art.seed,
                candidates=log_candidates_tuple,
                decision_text=decision,
            )

            # Apply repair mutation to spec/state
            current_spec, current_strategy, current_seed, cached_art_candidates = self._apply_repair(
                action=action,
                spec=current_spec,
                strategy=current_strategy,
                current_seed=current_seed,
                existing_art=art_candidates if action in (RepairAction.REFLOW_TEXT, RepairAction.EDIT_SPEC) else None,
                context=context,
            )

        # Budget exhausted without a 100% clean candidate
        failure_reasons = [
            f"[{r.check_name}]: {r.detail}"
            for r in (best_overall_candidate.check_report.results if best_overall_candidate else [])
            if r.severity == "blocking"
        ]

        logger.finalize_run(
            status="FAILED",
            best_png_path=best_overall_candidate.render_result.png_path if best_overall_candidate else None,
            best_pdf_path=best_overall_candidate.render_result.pdf_path if best_overall_candidate else None,
            final_spec=current_spec,
            iterations_used=max_iterations,
            repair_actions=actions_taken,
        )

        return RunResult(
            status="FAILED",
            best_candidate=best_overall_candidate,
            iterations_used=max_iterations,
            final_spec=current_spec,
            run_dir=logger.run_dir,
            summary=(
                f"FAILED: Exhausted {max_iterations} attempts. "
                f"Best attempt still had {len(failure_reasons)} blocking defects."
            ),
            failure_reasons=failure_reasons,
        )

    def _determine_repair_action(
        self, report: CheckReport, iteration: int
    ) -> tuple[RepairAction, str]:
        """Map failure types to cheapest feasible repair action."""
        blocking_checks = [r for r in report.results if r.severity == "blocking"]
        check_names = [b.check_name for b in blocking_checks]

        # Cheapest 1: Overflow / Margins -> Reflow text (re-render only)
        if any("overflow" in name for name in check_names):
            return RepairAction.REFLOW_TEXT, "Shrink font sizes and adjust padding"

        # Cheapest 2: Contrast failures -> Edit spec colors (re-render only)
        if any("contrast" in name for name in check_names):
            return RepairAction.EDIT_SPEC, "Invert or increase text color contrast"

        # Cheapest 3: Visual order violations -> Edit spec coordinates (re-render only)
        if any("order" in name for name in check_names):
            return RepairAction.EDIT_SPEC, "Reorder element vertical layout"

        # Cheapest 4: Logo size / required logo missing -> Edit spec (re-render only)
        if any("logo" in name for name in check_names):
            return RepairAction.EDIT_SPEC, "Resize or place missing required logo"

        # Mid-cost: Text duplication / artifacts -> Regenerate art with new seed
        if any("duplicated" in name for name in check_names):
            return RepairAction.NEW_SEED, "Regenerate art with different random seed"

        # High-cost / Repeated failure: Switch strategy
        if iteration >= 3:
            return RepairAction.SWITCH_STRATEGY, "Toggle between Strategy A and Strategy B"

        return RepairAction.NEW_SEED, "Regenerate art with new random seed"

    def _apply_repair(
        self,
        action: RepairAction,
        spec: PosterSpec,
        strategy: Literal["A", "B"],
        current_seed: int,
        existing_art: list[GeneratedArt] | None,
        context: ContextBundle,
    ) -> tuple[PosterSpec, Literal["A", "B"], int, list[GeneratedArt] | None]:
        new_spec = spec.model_copy(deep=True)
        new_strategy = strategy
        new_seed = current_seed
        cached_art = existing_art

        if action == RepairAction.REFLOW_TEXT:
            # Shrink font sizes by 15% (min 14pt)
            for elem in new_spec.elements:
                elem.size = max(14, int(elem.size * 0.85))
            cached_art = existing_art

        elif action == RepairAction.EDIT_SPEC:
            # Fix contrast by using high-contrast white
            for elem in new_spec.elements:
                elem.color = "#FFFFFF"

            # Fix ordering if subheadline was above headline
            h_elem = next((e for e in new_spec.elements if e.role == "headline"), None)
            s_elem = next((e for e in new_spec.elements if e.role == "subheadline"), None)
            if h_elem and s_elem and s_elem.box.y_min < h_elem.box.y_max:
                # Place subheadline below headline
                s_elem.box.y_min = min(900, h_elem.box.y_max + 20)
                s_elem.box.y_max = min(980, s_elem.box.y_min + 70)

            # Fix missing logo if absent
            if not new_spec.logos:
                new_spec.logos.append(
                    LogoPlacement(
                        file="college_logo.png",
                        box=BBox(y_min=40, x_min=80, y_max=100, x_max=320),
                        clear_space_px=20,
                    )
                )
            cached_art = existing_art

        elif action == RepairAction.NEW_SEED:
            new_seed = current_seed + 101
            cached_art = None  # Force re-generation

        elif action == RepairAction.SWITCH_STRATEGY:
            new_strategy = "A" if strategy == "B" else "B"
            new_seed = current_seed + 202
            cached_art = None

        return new_spec, new_strategy, new_seed, cached_art
