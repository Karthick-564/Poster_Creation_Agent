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
    issues_before: int
    issues_after: int
    diff_summary: str
    critic_verdict: str = ""


class LoopSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    converged: bool
    rounds_used: int
    max_rounds: int = 3
    final_issue_count: int
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
            pat = rf"(#{op.element_id}\s*\{{[^}}]*?font-size:\s*)(\d+)px"
            m = re.search(pat, patched)
            if m:
                curr_size = int(m.group(2))
                new_size = max(14, int(curr_size * factor))
                patched = re.sub(pat, rf"\g<1>{new_size}px", patched)

        elif op.op_name == "move":
            dy = max(-150, min(150, int(op.params.get("dy", 0))))
            if dy != 0:
                if op.element_id == "hero_art_1":
                    patched = re.sub(
                        r"(--hero-top:\s*)(\d+)px",
                        lambda m: f"{m.group(1)}{max(180, int(m.group(2)) + dy)}px",
                        patched,
                    )
                elif op.element_id in ["bottom_metadata_container", "card_date_venue"]:
                    patched = re.sub(
                        r"(--metadata-bottom:\s*)(\d+)px",
                        lambda m: f"{m.group(1)}{max(20, int(m.group(2)) + dy)}px",
                        patched,
                    )
                else:
                    pat = rf"(#{op.element_id}\s*\{{[^}}]*?top:\s*)(\d+)px"
                    patched = re.sub(pat, lambda m: f"{m.group(1)}{max(10, int(m.group(2)) + dy)}px", patched)

        elif op.op_name == "set_z":
            z_val = max(1, min(50, int(op.params.get("z", 20))))
            pat = rf"(#{op.element_id}\s*\{{[^}}]*?z-index:\s*)\d+"
            patched = re.sub(pat, rf"\g<1>{z_val}", patched)

        elif op.op_name == "add_scrim":
            opacity = max(0.20, min(0.98, float(op.params.get("opacity", 0.85))))
            if op.element_id == "cta_1":
                patched = re.sub(
                    r"(#cta_1\s*\{[^}]*?background:\s*)[^;]+;",
                    r"\g<1>#00FF66; color: #050811; font-weight: 800;",
                    patched,
                )
            else:
                patched = re.sub(
                    r"--card-bg:\s*rgba\(\d+,\s*\d+,\s*\d+,\s*[\d\.]+\);",
                    f"--card-bg: rgba(7, 11, 24, {opacity});",
                    patched,
                )

        elif op.op_name == "resize_layer":
            factor = max(0.50, min(2.50, float(op.params.get("factor", 1.35))))
            if op.element_id == "hero_art_1":
                patched = re.sub(
                    r"(--hero-size:\s*)(\d+)px",
                    lambda m: f"{m.group(1)}{int(int(m.group(2)) * factor)}px",
                    patched,
                )

        elif op.op_name == "swap_token":
            # Harmonize tokens to cohesive cyber palette
            patched = re.sub(r"--highlight-color:\s*#[a-fA-F0-9]+;", "--highlight-color: #00F3FF;", patched)
            patched = re.sub(r"--danger-color:\s*#[a-fA-F0-9]+;", "--danger-color: #00FF66;", patched)
            patched = re.sub(r"--accent-color:\s*#[a-fA-F0-9]+;", "--accent-color: #00FF66;", patched)
            patched = re.sub(r"--card-border:\s*rgba\([^)]+\);", "--card-border: rgba(0, 243, 255, 0.40);", patched)

        return patched

    def plan_ops_from_issues(self, issues: list[CheckIssue]) -> list[TypedOp]:
        """Convert physical and VLM critique issues deterministically into typed ops."""
        ops: list[TypedOp] = []
        seen_ops: set[str] = set()

        for issue in issues:
            key = f"{issue.recommended_op}:{issue.element_id}"
            if key in seen_ops:
                continue
            seen_ops.add(key)

            if issue.check_name == "wcag_sampled_contrast":
                ops.append(TypedOp(
                    op_name="add_scrim",
                    element_id=issue.element_id,
                    params={"opacity": 0.90},
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
            elif issue.check_name == "vlm_hero_too_small":
                ops.append(TypedOp(
                    op_name="resize_layer",
                    element_id="hero_art_1",
                    params={"factor": 1.40},
                    reason="VLM: Enlarge hero art to command central composition",
                ))
            elif issue.check_name == "vlm_center_void":
                ops.append(TypedOp(
                    op_name="move",
                    element_id="hero_art_1",
                    params={"dy": 45},
                    reason="VLM: Shift hero art downward towards center",
                ))
                ops.append(TypedOp(
                    op_name="move",
                    element_id="bottom_metadata_container",
                    params={"dy": 50},
                    reason="VLM: Shift metadata upward towards center to eliminate void",
                ))
            elif issue.check_name == "vlm_color_clash":
                ops.append(TypedOp(
                    op_name="swap_token",
                    element_id="card_date_venue",
                    params={"target_theme": "cyber_unified"},
                    reason="VLM: Harmonize clashing colors to cyber neon palette",
                ))

        return ops

    def execute_3_round_loop(
        self,
        current_html: str,
        initial_render: ThemeRenderResult,
        initial_issues: list[CheckIssue],
        verifier: Any,
        inspector: Any,
        renderer: ThemePackRenderer,
        brief: ExtractedBrief,
        art_bundle: MeasuredArtBundle,
        output_dir: Path | str,
        base_slug: str,
        bg_path: str | Path,
        hero_path: str | Path = "",
        title_3d_path: str | Path = "",
        accent_path: str | Path = "",
    ) -> tuple[str, ThemeRenderResult, list[CheckIssue], LoopSummary]:
        """Run up to 3 bounded rounds with automatic rollback on regression."""
        active_html = current_html
        active_render = initial_render
        active_issues = copy.deepcopy(initial_issues)
        history: list[PatchRoundResult] = []

        for rnd in range(1, self.max_rounds + 1):
            if not active_issues:
                break

            planned_ops = self.plan_ops_from_issues(active_issues)
            if not planned_ops:
                break

            candidate_html = active_html
            for op in planned_ops:
                candidate_html = self.apply_op(candidate_html, op)

            # Re-render candidate with html_override
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
                html_override=candidate_html,
            )

            # Re-verify physically
            cand_report: VerificationReport = verifier.run_all(
                render_result=cand_render,
                brief=brief,
                canvas_w=art_bundle.canvas_w,
                canvas_h=art_bundle.canvas_h,
            )

            # Re-audit with VLM inspector
            cand_vlm = inspector.audit_poster(cand_render.full_png_path, brief=brief) if inspector else None
            new_vlm_issues = cand_vlm.detected_issues if cand_vlm else []

            new_total_issues = cand_report.issues + new_vlm_issues
            issues_before = len(active_issues)
            issues_after = len(new_total_issues)

            # Rollback check: accept only if issue count strictly decreases
            if issues_after < issues_before:
                active_html = candidate_html
                active_render = cand_render
                active_issues = new_total_issues
                accepted = True
                summary = f"Round {rnd} ACCEPTED: issues decreased from {issues_before} to {issues_after}."
            else:
                accepted = False
                summary = f"Round {rnd} REVERTED: issues did not decrease ({issues_before} -> {issues_after})."

            critic_notes = []
            if cand_vlm:
                for p in cand_vlm.probes:
                    status_str = "PASS" if p.passed else "FAIL"
                    critic_notes.append(f"[{p.probe_name}: {status_str} (vote: {p.majority_vote[:35]})]")

            history.append(PatchRoundResult(
                round_number=rnd,
                ops_attempted=planned_ops,
                accepted=accepted,
                issues_before=issues_before,
                issues_after=issues_after,
                diff_summary=summary,
                critic_verdict="; ".join(critic_notes),
            ))

        converged = len(active_issues) == 0
        loop_summary = LoopSummary(
            converged=converged,
            rounds_used=len(history),
            max_rounds=self.max_rounds,
            final_issue_count=len(active_issues),
            round_history=history,
        )

        return active_html, active_render, active_issues, loop_summary
