"""Standalone deterministic QA gates module for poster layouts and renders."""
from poster_agent.qa.gates import (
    GateFailure,
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
]

