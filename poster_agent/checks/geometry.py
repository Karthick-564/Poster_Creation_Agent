"""Geometry and layout checks based on DOM bounding boxes."""
from typing import Literal
from pydantic import BaseModel, ConfigDict

from poster_agent.renderer.renderer import DOMBoundingBox
from poster_agent.spec.models import PosterSpec
from .models import CheckResult


def compute_overlap_area(box1: DOMBoundingBox, box2: DOMBoundingBox) -> float:
    """Compute overlapping area in px^2."""
    x_overlap = max(0.0, min(box1.right, box2.right) - max(box1.left, box2.left))
    y_overlap = max(0.0, min(box1.bottom, box2.bottom) - max(box1.top, box2.top))
    return x_overlap * y_overlap


def compute_linear_overlap(box1: DOMBoundingBox, box2: DOMBoundingBox) -> float:
    """Compute the minimum linear penetrating distance of overlap between two boxes in px."""
    x_overlap = min(box1.right, box2.right) - max(box1.left, box2.left)
    y_overlap = min(box1.bottom, box2.bottom) - max(box1.top, box2.top)
    if x_overlap > 0 and y_overlap > 0:
        return min(x_overlap, y_overlap)
    return 0.0


def run_geometry_check(
    spec: PosterSpec,
    dom_boxes: dict[str, DOMBoundingBox],
    max_allowed_overlap_px: float = 5.0,
    min_margin_px: float = 40.0,
) -> list[CheckResult]:
    """Perform deterministic DOM-level geometry checks."""
    results: list[CheckResult] = []
    w = float(spec.canvas_width_px)
    h = float(spec.canvas_height_px)

    # 1. Canvas Boundary Overflow Check
    for eid, box in dom_boxes.items():
        if box.role in ("art", "background"):
            continue

        overflows = []
        if box.left < 0:
            overflows.append(f"left ({box.left:.1f}px < 0)")
        if box.top < 0:
            overflows.append(f"top ({box.top:.1f}px < 0)")
        if box.right > w:
            overflows.append(f"right ({box.right:.1f}px > {w:.1f}px)")
        if box.bottom > h:
            overflows.append(f"bottom ({box.bottom:.1f}px > {h:.1f}px)")

        if overflows:
            results.append(
                CheckResult(
                    check_name=f"overflow_{eid}",
                    severity="blocking",
                    detail=f"Element '{eid}' overflows canvas bounds: {', '.join(overflows)}.",
                    fix_hint=f"Shift element '{eid}' inward or reduce its dimensions.",
                )
            )
        else:
            results.append(
                CheckResult(
                    check_name=f"bounds_{eid}",
                    severity="pass",
                    detail=f"Element '{eid}' is fully inside canvas boundaries.",
                    fix_hint=None,
                )
            )

        # 2. Canvas Edge Margin Check (Warning if too close to border)
        margin_violations = []
        if box.left < min_margin_px:
            margin_violations.append(f"left margin {box.left:.1f}px < {min_margin_px}px")
        if box.top < min_margin_px:
            margin_violations.append(f"top margin {box.top:.1f}px < {min_margin_px}px")
        if (w - box.right) < min_margin_px:
            margin_violations.append(f"right margin {(w - box.right):.1f}px < {min_margin_px}px")
        if (h - box.bottom) < min_margin_px:
            margin_violations.append(f"bottom margin {(h - box.bottom):.1f}px < {min_margin_px}px")

        if margin_violations:
            results.append(
                CheckResult(
                    check_name=f"margin_{eid}",
                    severity="warning",
                    detail=f"Element '{eid}' violates edge margin safety: {', '.join(margin_violations)}.",
                    fix_hint=f"Add padding or move '{eid}' at least {min_margin_px}px away from canvas edges.",
                )
            )
        else:
            results.append(
                CheckResult(
                    check_name=f"margin_{eid}",
                    severity="pass",
                    detail=f"Element '{eid}' respects the {min_margin_px}px edge margin.",
                    fix_hint=None,
                )
            )

    # 3. Inter-Element Overlap Check
    box_list = list(dom_boxes.values())
    for i in range(len(box_list)):
        for j in range(i + 1, len(box_list)):
            b1 = box_list[i]
            b2 = box_list[j]

            # Don't check art vs text (art is meant to be in background)
            if "art" in (b1.role, b2.role):
                continue

            overlap_dist = compute_linear_overlap(b1, b2)
            if overlap_dist > max_allowed_overlap_px:
                results.append(
                    CheckResult(
                        check_name=f"overlap_{b1.element_id}_{b2.element_id}",
                        severity="blocking",
                        detail=(
                            f"Collision detected between '{b1.element_id}' and '{b2.element_id}': "
                            f"overlapping by {overlap_dist:.1f}px (threshold is {max_allowed_overlap_px}px)."
                        ),
                        fix_hint=(
                            f"Reposition or adjust sizes of '{b1.element_id}' and '{b2.element_id}' "
                            f"to prevent visual collision."
                        ),
                    )
                )

    return results
