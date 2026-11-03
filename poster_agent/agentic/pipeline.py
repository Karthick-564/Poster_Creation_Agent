"""Agentic Poster Creation Pipeline Orchestrator.

Implements the single unified path:
S1 Intake -> S2 Asset Decisions -> S3 Generation -> S4 Designer Loop -> S5 Gate Review -> S7 Export.
Persists complete plan.json and supports --replay <run_id> for deterministic offline execution.
"""
from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Optional

from poster_agent.agentic.assets import AssetDecisionStage
from poster_agent.agentic.critic import CriticStage
from poster_agent.agentic.designer import DesignerStage
from poster_agent.agentic.generate import GenerationStage
from poster_agent.agentic.intake import IntakeStage
from poster_agent.agentic.llm_backend import LLMBackend, get_backend
from poster_agent.agentic.router import Router, RouterDecision, RerouteAction
from poster_agent.agentic.structure import lock_all_zones
from poster_agent.house_style import load_house_style, resolve_canvas_dimensions, resolve_school
from poster_agent.mcp.vectorcraft_server import VectorCraftMCPServer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class AgenticPosterPipeline:
    """End-to-end pipeline driving the agentic poster workflow."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        designer_backend: Optional[LLMBackend] = None,
        critic_backend: Optional[LLMBackend] = None,
        config_path: Optional[Path | str] = None,
    ):
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.config_path = config_path or (self.project_root / "configs" / "agentic.yaml")
        self.designer_backend = designer_backend
        self.critic_backend = critic_backend
        if self.critic_backend is None:
            try:
                self.critic_backend = get_backend(role="critic", config_path=self.config_path)
            except Exception:
                self.critic_backend = None
        self.house_style = load_house_style()

    def run(
        self,
        brief_file: Path | str,
        run_id: Optional[str] = None,
        school_id: Optional[str] = None,
        format_name: Optional[str] = None,
        allow_generation: bool = False, # M2 first run uses supplied/native assets
        replay_run_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute one complete poster creation run."""
        start_time = time.time()
        actual_run_id = run_id or f"agentic_{int(time.time())}"
        run_dir = self.project_root / "runs" / actual_run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # -------------------------------------------------------------
        # Replay Mode Check (--replay <run_id>)
        # -------------------------------------------------------------
        if replay_run_id:
            return self._execute_replay(replay_run_id=replay_run_id, target_run_dir=run_dir)

        # -------------------------------------------------------------
        # Stage 1: Intake & Verbatim Ingestion
        # -------------------------------------------------------------
        intake_stage = IntakeStage()
        intake_res = intake_stage.process(brief_file)
        raw_brief = Path(brief_file).read_text(encoding="utf-8")
        if not intake_res.is_valid:
            plan_fail = {
                "run_id": actual_run_id,
                "status": "HALTED",
                "halt_stage": "S1_intake",
                "reason": "Missing critical brief information",
                "clarifying_question": intake_res.clarifying_question,
                "missing_critical": intake_res.missing_critical,
            }
            self._write_plan(run_dir, plan_fail)
            return plan_fail

        # Resolve school and canvas dimensions
        school, school_info = resolve_school(intake_res.brief, house_style=self.house_style)
        if school_id and school_id in self.house_style.get("schools", {}):
            school = school_id
            school_info = self.house_style["schools"][school_id]

        cw, ch = resolve_canvas_dimensions(format_name or intake_res.brief, house_style=self.house_style)
        palette = school_info.get("palette", {}).values()
        palette_list = list(palette) if palette else ["#070B19", "#00F5D4", "#7B2FFF", "#FF3D68", "#F0F6FC"]

        # -------------------------------------------------------------
        # Stage 2: Asset Decisions
        # -------------------------------------------------------------
        asset_stage = AssetDecisionStage(project_root=self.project_root)
        decisions = asset_stage.decide(
            brief=intake_res.brief,
            school_id=school,
            allow_generation=allow_generation,
        )

        # -------------------------------------------------------------
        # Stage 3: Layer Asset Generation & Measurement
        # -------------------------------------------------------------
        gen_stage = GenerationStage(project_root=self.project_root)
        gen_res = gen_stage.run(
            asset_decisions=decisions,
            run_dir=run_dir,
            palette=palette_list,
            canvas_w=cw,
            canvas_h=ch,
            brief_title=intake_res.fields.get("title", "Event"),
        )
        if not gen_res.refusal_clean:
            plan_refusal = {
                "run_id": actual_run_id,
                "status": "HALTED",
                "halt_stage": "S3_generation",
                "reason": gen_res.refusal_reason,
                "seeds": gen_res.seeds,
            }
            self._write_plan(run_dir, plan_refusal)
            return plan_refusal

        # -------------------------------------------------------------
        # Stage 4 to 6: Autonomous Designer & Review-Router Loop (Max 3 Cycles)
        # -------------------------------------------------------------
        router = Router()
        critic = CriticStage(backend=self.critic_backend)
        reroutes: list[dict[str, Any]] = []

        max_cycles = 3
        cycle = 1
        export_success = False
        master_png = run_dir / "master_render_2x.png"
        master_pdf = run_dir / "master_print.pdf"
        preview_png = run_dir / "preview.png"

        total_designer_calls = 0
        last_transcript_path = None
        measure_result: dict[str, Any] = {}
        ocr_result: dict[str, Any] = {}
        critic_result: dict[str, Any] = {}
        halt_reason: Optional[str] = None
        locked_report: dict[str, Any] = {}

        while cycle <= max_cycles:
            # 1. Initialize MCP Server session & locked zones
            server = VectorCraftMCPServer(session_id=f"{actual_run_id}_c{cycle}", base_dir=self.project_root)
            server.create_doc(width=cw, height=ch)
            server.load_brief(str(brief_file))
            locked_report = lock_all_zones(server, intake_res.brief, school_id=school)

            # 2. Stage 4: Designer Loop
            designer = DesignerStage(server=server, backend=self.designer_backend)
            designer_res = designer.run(
                brief_fields=intake_res.fields,
                palette=palette_list,
                run_dir=run_dir,
                background_layer=gen_res.layers.get("background"),
                hero_layer=gen_res.layers.get("hero"),
            )
            total_designer_calls += designer_res.get("total_tool_calls", 0)
            last_transcript_path = designer_res.get("transcript_path")

            # 3. Stage 5: Review
            # a) Deterministic physical QA gates
            measure_result = server.measure()

            # b) Render preview for visual inspection
            prev_res = server.render_preview(scale=1.0)
            preview_png = server.session_dir / "preview.png"

            # c) OCR check on background and preview
            bg_path = Path(gen_res.layers["background"]) if gen_res.layers.get("background") else None
            ocr_result = critic.run_ocr_review(
                final_image_path=preview_png,
                bg_image_path=bg_path,
                brief_text=raw_brief,
            )

            # d) Structured VL Critic 9-point checklist
            manifest_rows = list(server.manifest_rows)
            has_hero = bool(gen_res.layers.get("hero"))
            critic_result = critic.run_checklist_review(
                final_image_path=preview_png,
                brief_fields=intake_res.fields,
                palette=palette_list,
                gate_results=measure_result,
                manifest_rows=manifest_rows,
                has_hero=has_hero,
                ocr_passed=ocr_result.get("passed", True),
            )

            # 4. Stage 6: Failure Router
            decision = router.route(
                cycle=cycle,
                gate_results=measure_result,
                ocr_results=ocr_result,
                critic_results=critic_result,
                locked_status=locked_report,
            )

            if decision.reroute_action:
                reroutes.append(decision.reroute_action.to_dict())

            if not decision.should_reroute:
                # All signals passed: Proceed to Stage 7 Export
                if measure_result.get("passed", False):
                    server.save_session(run_dir / "session.vcs")
                    exp = server.export(output_png=str(master_png), output_pdf=str(master_pdf))
                    export_success = exp.get("status") == "ok"
                break

            if decision.target_stage == "HALT":
                halt_reason = decision.halt_reason
                break

            # Handle S3 regeneration if requested
            if decision.target_stage == "S3":
                gen_res = gen_stage.run(
                    asset_decisions=decisions,
                    run_dir=run_dir,
                    palette=palette_list,
                    canvas_w=cw,
                    canvas_h=ch,
                    brief_title=intake_res.fields.get("title", "Event"),
                )

            cycle += 1

        # -------------------------------------------------------------
        # Persist plan.json Audit Trail
        # -------------------------------------------------------------
        plan_status = "SUCCESS" if export_success else ("HALTED_WITH_FAILURES" if halt_reason else "REVIEW_REJECTED")
        plan = {
            "run_id": actual_run_id,
            "status": plan_status,
            "halt_reason": halt_reason,
            "school": school,
            "canvas_dimensions": [cw, ch],
            "brief": intake_res.summary(),
            "asset_provenance": decisions.provenance,
            "seeds": gen_res.seeds,
            "locked_zones": locked_report,
            "cycles_used": min(cycle, max_cycles),
            "reroutes": reroutes,
            "total_tool_calls": total_designer_calls,
            "transcript_path": last_transcript_path,
            "gate_results": measure_result,
            "ocr_results": ocr_result,
            "critic_checklist": critic_result,
            "deliverables": {
                "master_render_2x": str(master_png.relative_to(self.project_root)) if master_png.exists() else None,
                "master_print_pdf": str(master_pdf.relative_to(self.project_root)) if master_pdf.exists() else None,
                "session_vcs": str((run_dir / "session.vcs").relative_to(self.project_root)) if (run_dir / "session.vcs").exists() else None,
            },
            "wall_time_sec": round(time.time() - start_time, 2),
        }
        self._write_plan(run_dir, plan)
        return plan

    def _write_plan(self, run_dir: Path, plan_data: dict[str, Any]) -> None:
        plan_file = run_dir / "plan.json"
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, indent=2)

    def _execute_replay(self, replay_run_id: str, target_run_dir: Path) -> dict[str, Any]:
        """Re-execute S4-S7 deterministically from saved plan and transcript without GPU/network."""
        source_dir = self.project_root / "runs" / replay_run_id
        plan_path = source_dir / "plan.json"
        if not plan_path.exists():
            raise FileNotFoundError(f"Cannot replay run '{replay_run_id}': plan.json not found at {plan_path}")

        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        cw, ch = plan.get("canvas_dimensions", [1080.0, 1920.0])

        # Restore VectorCraft session
        source_vcs = source_dir / "session.vcs"
        server = VectorCraftMCPServer(session_id=target_run_dir.name, base_dir=self.project_root)
        server.create_doc(width=cw, height=ch)

        if source_vcs.exists():
            server.load_session(str(source_vcs))

        # Re-measure and re-export
        m = server.measure()
        master_png = target_run_dir / "master_render_2x.png"
        master_pdf = target_run_dir / "master_print.pdf"
        exp = server.export(output_png=str(master_png), output_pdf=str(master_pdf))

        replay_plan = dict(plan)
        replay_plan["replay_of"] = replay_run_id
        replay_plan["status"] = "REPLAY_SUCCESS" if exp.get("status") == "ok" else "REPLAY_FAILED"
        self._write_plan(target_run_dir, replay_plan)
        return replay_plan

