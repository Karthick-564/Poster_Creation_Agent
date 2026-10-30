"""Stage 7: 3-Round Bounded Typed Patcher with Automatic Rollback Verification."""
import copy
import re
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.checks.pixel_verifier import CheckIssue, VerificationReport
from poster_agent.renderer.theme_renderer import ThemeRenderResult, ThemePackRenderer
from poster_agent.ingestion.extractor import ExtractedBrief
from poster_agent.vision.art_measurer import MeasuredArtBundle


class TypedOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op_name: Literal["scale_font", "move", "set_z", "add_scrim", "resize_layer", "swap_token"]
    element_id: str
    params: dict[str, Any]
    reason: str


class PatchRoundResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    round_number: int
    ops_attempted: list[TypedOp]
    accepted: bool
    blocking_before: int
    blocking_after: int
    diff_summary: str


class LoopSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    converged: bool
    rounds_used: int
    max_rounds: int = 3
    final_blocking_count: int
    round_history: list[PatchRoundResult] = Field(default_factory=list)


class TypedLayoutPatcher:
    """Bounded, deterministic layout patcher operating on stable element IDs."""

    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max_rounds

    def apply_op(self, html_content: str, op: TypedOp) -> str:
        """Mutate HTML content with the bounded typed operation."""
        patched = html_content

        if op.op_name == "scale_font":
            factor = max(0.70, min(1.30, float(op.params.get("factor", 0.88))))
            # Find selector for element_id and adjust font-size
            pat = rf"(#{op.element_id}\s*\{{[^}}]*?font-size:\s*)(\d+)px"
            m = re.search(pat, patched)
            if m:
                curr_size = int(m.group(2))
                new_size = max(14, int(curr_size * factor))
                patched = re.sub(pat, rf"\g<1>{new_size}px", patched)

        elif op.op_name == "move":
            dy = max(-150, min(150, int(op.params.get("dy", 0))))
            dx = max(-150, min(150, int(op.params.get("dx", 0))))
            if dy != 0:
                if op.element_id == "hero_art_1":
                    patched = re.sub(r"(--hero-top:\s*)(\d+)px", lambda m: f"{m.group(1)}{max(200, int(m.group(2)) + dy)}px", patched)
                elif op.element_id in ["bottom_metadata_container", "card_date_venue"]:
                    patched = re.sub(r"(--metadata-bottom:\s*)(\d+)px", lambda m: f"{m.group(1)}{max(20, int(m.group(2)) - dy)}px", patched)
                else:
                    pat = rf"(#{op.element_id}\s*\{{[^}}]*?top:\s*)(\d+)px"
                    patched = re.sub(pat, lambda m: f"{m.group(1)}{max(10, int(m.group(2)) + dy)}px", patched)

        elif op.op_name == "set_z":
            z_val = max(1, min(50, int(op.params.get("z", 20))))
            pat = rf"(#{op.element_id}\s*\{{[^}}]*?z-index:\s*)\d+"
            patched = re.sub(pat, rf"\g<1>{z_val}", patched)

        elif op.op_name == "add_scrim":
            opacity = max(0.15, min(0.95, float(op.params.get("opacity", 0.55))))
            if op.element_id == "cta_1":
                # Enhance CTA button contrast directly
                patched = re.sub(r"(#cta_1\s*\{[^}]*?background:\s*)[^;]+;", r"\g<1>#7AE7C7; color: #06030F; font-weight: 800;", patched)
            else:
                # Enhance card background opacity
                patched = re.sub(
                    r"--card-bg:\s*rgba\(\d+,\s*\d+,\s*\d+,\s*[\d\.]+\);",
                    f"--card-bg: rgba(14, 7, 40, {opacity});",
                    patched,
                )

        elif op.op_name == "resize_layer":
            factor = max(0.50, min(1.50, float(op.params.get("factor", 0.9))))
            if op.element_id == "hero_art_1":
                patched = re.sub(r"(--hero-size:\s*)(\d+)px", lambda m: f"{m.group(1)}{int(int(m.group(2)) * factor)}px", patched)

        return patched

    def plan_ops_from_issues(self, issues: list[CheckIssue]) -> list[TypedOp]:
        """Convert check issues directly into bounded typed operations."""
        ops: list[TypedOp] = []
        for issue in issues:
            if issue.check_name == "wcag_sampled_contrast":
                ops.append(TypedOp(
                    op_name="add_scrim",
                    element_id=issue.element_id,
                    params={"opacity": 0.75},
                    reason=f"Increase contrast for #{issue.element_id}",
                ))
            elif issue.check_name == "occlusion_detected":
                ops.append(TypedOp(
                    op_name="move",
                    element_id="hero_art_1",
                    params={"dy": 45},
                    reason="Shift hero art downward to prevent overlapping title",
                ))
            elif issue.check_name in ["safe_margin_overflow", "bottom_safe_margin_overflow"]:
                ops.append(TypedOp(
                    op_name="scale_font",
                    element_id=issue.element_id,
                    params={"factor": 0.88},
                    reason=f"Scale down #{issue.element_id} to stay inside safe margins",
                ))
        return ops

    def execute_3_round_loop(
        self,
        current_html: str,
        initial_render: ThemeRenderResult,
        initial_report: VerificationReport,
        verifier: Any,
        renderer: ThemePackRenderer,
        brief: ExtractedBrief,
        art_bundle: MeasuredArtBundle,
        output_dir: Path | str,
        base_slug: str,
        bg_path: str | Path,
        hero_path: str | Path = "",
        title_3d_path: str | Path = "",
        accent_path: str | Path = "",
    ) -> tuple[str, ThemeRenderResult, VerificationReport, LoopSummary]:
        """Run up to 3 bounded rounds with automatic rollback on regression."""
        active_html = current_html
        active_report = initial_report
        best_render: ThemeRenderResult = initial_render
        cand_render: ThemeRenderResult = initial_render
        history: list[PatchRoundResult] = []

        for rnd in range(1, self.max_rounds + 1):
            if active_report.blocking_count == 0:
                break

            planned_ops = self.plan_ops_from_issues(active_report.issues)
            if not planned_ops:
                break

            candidate_html = active_html
            for op in planned_ops:
                candidate_html = self.apply_op(candidate_html, op)

            # Re-render candidate
            cand_slug = f"{base_slug}_round_{rnd}"
            cand_render = renderer.render(
                brief=brief,
                art_bundle=art_bundle,
                output_dir=output_dir,
                base_slug=cand_slug,
                bg_path=bg_path,
                hero_path=hero_path,
                title_3d_path=title_3d_path,
                accent_path=accent_path,
            )

            cand_report = verifier.run_all(
                render_result=cand_render,
                brief=brief,
                canvas_w=art_bundle.canvas_w,
                canvas_h=art_bundle.canvas_h,
            )

            blocking_before = active_report.blocking_count
            blocking_after = cand_report.blocking_count

            # Rollback check: accept only if blocking count strictly decreases
            if blocking_after < blocking_before:
                active_html = candidate_html
                active_report = cand_report
                best_render = cand_render
                accepted = True
                summary = f"Round {rnd} ACCEPTED: blocking errors dropped from {blocking_before} to {blocking_after}."
            else:
                # Revert
                accepted = False
                summary = f"Round {rnd} REVERTED: blocking errors did not decrease ({blocking_before} -> {blocking_after})."

            history.append(PatchRoundResult(
                round_number=rnd,
                ops_attempted=planned_ops,
                accepted=accepted,
                blocking_before=blocking_before,
                blocking_after=blocking_after,
                diff_summary=summary,
            ))

        converged = active_report.blocking_count == 0
        loop_summary = LoopSummary(
            converged=converged,
            rounds_used=len(history),
            max_rounds=self.max_rounds,
            final_blocking_count=active_report.blocking_count,
            round_history=history,
        )

        return active_html, best_render or cand_render, active_report, loop_summary
