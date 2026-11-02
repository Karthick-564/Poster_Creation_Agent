"""Standalone deterministic QA gates module for poster layouts and renders."""
from poster_agent.qa.gates import (
    GateFailure,
    check_background_ocr,
    check_canvas_bounds,
    check_empty_rows,
    check_refusal_free,
    check_row_overlap,
    check_seams,
    run_all_gates,
    run_all_manifest_gates,
    run_all_pixel_gates,
    sample_contrast,
)
from poster_agent.qa.design import (
    asymmetry_index,
    evaluate_design_quality,
    focal_count,
    hero_presence,
    palette_coverage,
    type_scale_contrast,
    whitespace_balance,
)

__all__ = [
    "GateFailure",
    "check_canvas_bounds",
    "check_row_overlap",
    "check_empty_rows",
    "check_seams",
    "sample_contrast",
    "run_all_manifest_gates",
    "run_all_pixel_gates",
    "run_all_gates",
    "check_refusal_free",
    "check_background_ocr",
    "palette_coverage",
    "type_scale_contrast",
    "asymmetry_index",
    "hero_presence",
    "whitespace_balance",
    "focal_count",
    "evaluate_design_quality",
]
