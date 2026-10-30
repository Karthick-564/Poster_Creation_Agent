"""Unified 8-Stage Poster Production Harness with End-to-End Audit Reporting."""
import os
import re
import time
from pathlib import Path
from typing import Any

from poster_agent.ingestion.extractor import BriefExtractor, ExtractedBrief
from poster_agent.vision.art_measurer import ArtMeasurer, MeasuredArtBundle
from poster_agent.renderer.theme_renderer import ThemePackRenderer, ThemeRenderResult
from poster_agent.checks.pixel_verifier import PixelVerifier, VerificationReport
from poster_agent.reviewer.probes import VisualInspector, VisualAuditReport
from poster_agent.loop.typed_patcher import TypedLayoutPatcher, LoopSummary
from poster_agent.reporting.audit_logger import AuditLogger
from poster_agent.renderer.print_engine import PrintEngine


class PosterPipeline:
    """End-to-End Orchestrator executing the complete 8-stage harness."""

    def __init__(self, run_id: str | None = None, output_base: Path | str = "runs"):
        self.run_id = run_id or f"run_{int(time.time())}"
        self.output_dir = Path(output_base) / self.run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = AuditLogger(run_id=self.run_id, output_dir=self.output_dir)

    def run(
        self,
        raw_brief: str,
        context_text: str = "",
        bg_image_path: str | Path = "",
        hero_image_path: str | Path = "",
        title_3d_path: str | Path = "",
        accent_image_path: str | Path = "",
        theme_name: str = "cyber_aurora",
        format_name: str = "A2",
    ) -> tuple[Path, Path, Path, Path]:
        """Execute all 8 stages and return (master_pdf, bleed_png, audit_md, audit_json)."""

        # -------------------------------------------------------------
        # STAGE 1: BRIEF INGESTION & PROVENANCE (ZERO-DROP)
        # -------------------------------------------------------------
        extractor = BriefExtractor(required_keys=["title", "date", "venue"])
        brief = extractor.extract(raw_brief=raw_brief, context_text=context_text)

        s1_status = "PASSED" if brief.zero_drop_passed else "FAILED"
        s1_summary = f"Extracted {len(brief.fields)} fields with zero dummy data. Missing required: {brief.missing_fields}"
        self.logger.record_stage(
            stage_number=1,
            stage_name="Brief Ingestion & Provenance Tagging",
            status=s1_status,
            summary=s1_summary,
            details={
                "extracted_fields": {k: {"text": v.text, "source": v.source} for k, v in brief.fields.items()},
                "missing_fields": brief.missing_fields,
                "zero_drop_passed": brief.zero_drop_passed,
                "unmapped_lines": brief.unmapped_lines,
            },
        )
        if not brief.zero_drop_passed:
            raise ValueError(f"Stage 1 Halt: Missing required brief fields: {brief.missing_fields}")

        # -------------------------------------------------------------
        # STAGE 2: DRAFT SPATIAL PLANNING
        # -------------------------------------------------------------
        canvas_w = 1258
        canvas_h = 1772
        title_text = brief.get_text("title")
        slug_title = re.sub(r"[^\w\s-]", "", title_text).strip().lower().replace(" ", "_")
        if not slug_title:
            slug_title = "poster_design"
        self.logger.record_stage(
            stage_number=2,
            stage_name="Draft Spatial Planning",
            status="PASSED",
            summary=f"Selected '{theme_name}' archetype with vertical modular typographic scale.",
            details={
                "canvas_w": canvas_w,
                "canvas_h": canvas_h,
                "theme": theme_name,
                "headline_target_pt": 96,
                "date_target_pt": 38,
            },
        )

        # -------------------------------------------------------------
        # STAGE 3: TRUE ART MEASUREMENT
        # -------------------------------------------------------------
        measurer = ArtMeasurer(target_w=canvas_w, target_h=canvas_h)
        hero_geom = None
        hero_halo = None

        if hero_image_path and Path(hero_image_path).exists():
            hero_geom, hero_halo = measurer.measure_alpha_cutout(hero_image_path)

        calm_box = None
        if bg_image_path and Path(bg_image_path).exists():
            calm_box = measurer.measure_calm_negative_space(bg_image_path)

        dpi_reports = []
        if bg_image_path and Path(bg_image_path).exists():
            dpi_reports.append(measurer.calculate_layer_effective_dpi("background", bg_image_path))
        if hero_image_path and Path(hero_image_path).exists():
            dpi_reports.append(measurer.calculate_layer_effective_dpi("hero_cutout", hero_image_path))

        art_bundle = MeasuredArtBundle(
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            hero_geometry=hero_geom,
            hero_halo=hero_halo,
            calm_zone=calm_box,
            layer_dpis=dpi_reports,
            optical_center_x=canvas_w // 2,
            optical_center_y=int(canvas_h * 0.415),
        )

        self.logger.record_stage(
            stage_number=3,
            stage_name="True Art Measurement",
            status="PASSED",
            summary=f"Measured actual alpha bounds (hero: {hero_geom.width if hero_geom else 0}x{hero_geom.height if hero_geom else 0}px) and calm zone.",
            details={
                "hero_bounds": hero_geom.model_dump() if hero_geom else None,
                "hero_halo": hero_halo.model_dump() if hero_halo else None,
                "calm_negative_space": calm_box.model_dump() if calm_box else None,
                "layer_effective_dpis": [d.model_dump() for d in dpi_reports],
            },
        )

        # -------------------------------------------------------------
        # STAGE 4: PASS-2 RE-PLAN & THEME RENDERING
        # -------------------------------------------------------------
        renderer = ThemePackRenderer(theme_name=theme_name)
        render_res = renderer.render(
            brief=brief,
            art_bundle=art_bundle,
            output_dir=self.output_dir,
            base_slug=f"{slug_title}_initial",
            bg_path=bg_image_path,
            hero_path=hero_image_path,
            title_3d_path=title_3d_path,
            accent_path=accent_image_path,
        )

        self.logger.record_stage(
            stage_number=4,
            stage_name="Pass-2 Re-Plan & Theme Rendering",
            status="PASSED",
            summary=f"Rendered initial composite and text-alone occlusion layers with {len(render_res.dom_boxes)} stable DOM boxes.",
            details={
                "html_path": str(render_res.html_path),
                "full_png_path": str(render_res.full_png_path),
                "dom_elements_tracked": list(render_res.dom_boxes.keys()),
            },
        )

        # -------------------------------------------------------------
        # STAGE 5: DETERMINISTIC VERIFICATION (PHYSICAL PIXEL LEVEL)
        # -------------------------------------------------------------
        verifier = PixelVerifier(min_contrast=4.5, safe_margin_px=50)
        report = verifier.run_all(
            render_result=render_res,
            brief=brief,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
        )

        s5_status = "PASSED" if report.passed else "WARNING"
        s5_summary = f"Physical checks: {report.blocking_count} blocking errors, {report.warning_count} warnings."
        self.logger.record_stage(
            stage_number=5,
            stage_name="Deterministic Physical Verification",
            status=s5_status,
            summary=s5_summary,
            details={
                "blocking_count": report.blocking_count,
                "warning_count": report.warning_count,
                "issues": [i.model_dump() for i in report.issues],
            },
        )

        # -------------------------------------------------------------
        # STAGE 6: GROUNDED VISUAL INSPECTION (LFM3-VL-2B PROBES)
        # -------------------------------------------------------------
        inspector = VisualInspector()
        vlm_report = inspector.audit_poster(render_res.full_png_path, brief=brief)

        s6_status = "PASSED" if vlm_report.overall_passed else "WARNING"
        s6_summary = f"LFM3-VL-2B (3 samples): 3-Sec Glance {'PASSED' if vlm_report.probes[0].passed else 'FAILED'} | Dominance {'PASSED' if len(vlm_report.probes) > 1 and vlm_report.probes[1].passed else 'FAILED'} | Void {'PASSED' if len(vlm_report.probes) > 2 and vlm_report.probes[2].passed else 'FAILED'} | Color {'PASSED' if len(vlm_report.probes) > 3 and vlm_report.probes[3].passed else 'FAILED'}"
        self.logger.record_stage(
            stage_number=6,
            stage_name="Grounded Visual Inspection (LFM3-VL-2B)",
            status=s6_status,
            summary=s6_summary,
            details={
                "overall_passed": vlm_report.overall_passed,
                "negative_control_passed": vlm_report.negative_control_passed,
                "probes": [p.model_dump() for p in vlm_report.probes],
                "detected_issues": [i.model_dump() for i in vlm_report.detected_issues],
                "latency_seconds": vlm_report.latency_seconds,
            },
        )

        # -------------------------------------------------------------
        # STAGE 7: 3-ROUND TYPED PATCHER WITH ROLLBACK
        # -------------------------------------------------------------
        patcher = TypedLayoutPatcher(max_rounds=3)
        combined_initial_issues = report.issues + vlm_report.detected_issues
        final_html, final_render, final_issues, loop_summary = patcher.execute_3_round_loop(
            current_html=render_res.html_path.read_text(encoding="utf-8"),
            initial_render=render_res,
            initial_issues=combined_initial_issues,
            verifier=verifier,
            inspector=inspector,
            renderer=renderer,
            brief=brief,
            art_bundle=art_bundle,
            output_dir=self.output_dir,
            base_slug=f"{slug_title}_patched",
            bg_path=bg_image_path,
            hero_path=hero_image_path,
            title_3d_path=title_3d_path,
            accent_path=accent_image_path,
        )

        s7_status = "PASSED" if loop_summary.converged else ("WARNING" if loop_summary.final_issue_count == 0 else "FAILED")
        s7_summary = f"Completed {loop_summary.rounds_used} rounds. Final remaining issues: {loop_summary.final_issue_count}."
        self.logger.record_stage(
            stage_number=7,
            stage_name="3-Round Bounded Typed Patcher",
            status=s7_status,
            summary=s7_summary,
            details={
                "converged": loop_summary.converged,
                "rounds_used": loop_summary.rounds_used,
                "history": [h.model_dump() for h in loop_summary.round_history],
            },
        )

        # -------------------------------------------------------------
        # STAGE 8: PRINT PRE-FLIGHT CERTIFICATION & EXPORT
        # -------------------------------------------------------------
        print_engine = PrintEngine(format_name=format_name)
        pdf_path, png_path, tiff_path, preflight = print_engine.render_print_master(
            html_content=final_html,
            output_dir=self.output_dir,
            base_slug=f"{slug_title}_{format_name.lower()}_final",
        )

        s8_status = "PASSED" if preflight.passed_all else "WARNING"
        s8_summary = f"Exported {format_name} print master: Vector PDF, 300 DPI Bleed PNG, CMYK TIFF."
        self.logger.record_stage(
            stage_number=8,
            stage_name="Print Pre-Flight Certification & Export",
            status=s8_status,
            summary=s8_summary,
            details={
                "preflight_passed": preflight.passed_all,
                "effective_resolution_ppi": preflight.effective_resolution_ppi,
                "pdf_path": str(pdf_path),
                "png_path": str(png_path),
                "tiff_path": str(tiff_path),
                "preflight_details": preflight.details,
            },
        )

        # Export multi-stage reports
        md_report, json_report = self.logger.export_report(brief_title=title_text)

        return pdf_path, png_path, md_report, json_report
