"""CheckRunner: Orchestrates all deterministic quality gates."""
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.context.loader import ContextBundle
from poster_agent.renderer.renderer import DOMBoundingBox
from poster_agent.spec.models import PosterSpec
from .models import CheckResult, CheckReport
from .ocr import run_ocr_check, OCRResult
from .geometry import run_geometry_check
from .contrast import run_contrast_check
from .logo import run_logo_check


class CheckRunner:
    """Executes all deterministic quality gates on a poster candidate."""

    def __init__(
        self,
        min_contrast_ratio: float = 4.5,
        min_font_pt: int = 14,
        max_allowed_overlap_px: float = 5.0,
        min_margin_px: float = 40.0,
    ):
        self.min_contrast_ratio = min_contrast_ratio
        self.min_font_pt = min_font_pt
        self.max_allowed_overlap_px = max_allowed_overlap_px
        self.min_margin_px = min_margin_px

    def run_all(
        self,
        spec: PosterSpec,
        context: ContextBundle,
        image_path: str | Path,
        dom_boxes: dict[str, DOMBoundingBox] | None = None,
        ocr_result: OCRResult | None = None,
    ) -> CheckReport:
        """Run all deterministic checks."""
        all_results: list[CheckResult] = []

        # 1. OCR Text check
        ocr_checks = run_ocr_check(spec=spec, image_path=image_path, ocr_result=ocr_result)
        all_results.extend(ocr_checks)

        # 2. Geometry check (if dom_boxes available)
        if dom_boxes:
            geo_checks = run_geometry_check(
                spec=spec,
                dom_boxes=dom_boxes,
                max_allowed_overlap_px=self.max_allowed_overlap_px,
                min_margin_px=self.min_margin_px,
            )
            all_results.extend(geo_checks)

        # 3. Contrast & font size check
        contrast_checks = run_contrast_check(
            spec=spec,
            poster_image_path=image_path,
            min_contrast_ratio=self.min_contrast_ratio,
            min_font_pt=self.min_font_pt,
        )
        all_results.extend(contrast_checks)

        # 4. Logo check
        logo_checks = run_logo_check(
            spec=spec,
            context=context,
            dom_boxes=dom_boxes,
        )
        all_results.extend(logo_checks)

        blocking = [r for r in all_results if r.severity == "blocking"]
        warnings = [r for r in all_results if r.severity == "warning"]

        passed = len(blocking) == 0

        summary_parts = []
        if passed:
            summary_parts.append(f"PASS: All quality gates passed ({len(warnings)} warnings).")
        else:
            summary_parts.append(f"FAIL: {len(blocking)} blocking failures, {len(warnings)} warnings.")
            for b in blocking:
                summary_parts.append(f"  - [{b.check_name}]: {b.detail}")

        summary = "\n".join(summary_parts)

        return CheckReport(
            passed=passed,
            blocking_count=len(blocking),
            warning_count=len(warnings),
            results=all_results,
            summary=summary,
        )
