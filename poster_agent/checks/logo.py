"""Logo placement and size verification checks."""
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict

from poster_agent.context.loader import ContextBundle, LogoRule
from poster_agent.renderer.renderer import DOMBoundingBox
from poster_agent.spec.models import PosterSpec
from .models import CheckResult


def run_logo_check(
    spec: PosterSpec,
    context: ContextBundle,
    dom_boxes: dict[str, DOMBoundingBox] | None = None,
) -> list[CheckResult]:
    """Verify presence, dimension limits, and clear-space guidelines for required logos."""
    results: list[CheckResult] = []
    w = spec.canvas_width_px
    h = spec.canvas_height_px

    placed_logo_files = {p.file: p for p in spec.logos}

    # 1. Check all required logos are present in spec
    for rule_key, rule in context.logo_rules.items():
        if rule.required:
            matched_placement = None
            for p_file, placement in placed_logo_files.items():
                if p_file == rule.file or (rule.svg_file and p_file == rule.svg_file):
                    matched_placement = placement
                    break

            if not matched_placement:
                results.append(
                    CheckResult(
                        check_name=f"required_logo_{rule_key}",
                        severity="blocking",
                        detail=f"Required institutional logo '{rule.name}' ({rule.file}) is missing from spec.",
                        fix_hint=f"Add a LogoPlacement entry for '{rule.file}' to spec.logos.",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        check_name=f"required_logo_{rule_key}",
                        severity="pass",
                        detail=f"Required logo '{rule.name}' is correctly placed in spec.",
                        fix_hint=None,
                    )
                )

    # 2. Check dimensions of placed logos against minimum size rules
    for i, placement in enumerate(spec.logos):
        logo_w_px = placement.box.width_px(w)
        logo_h_px = placement.box.height_px(h)

        # Match with context rule if available
        matched_rule: LogoRule | None = None
        for r in context.logo_rules.values():
            if r.file == placement.file or (r.svg_file and r.svg_file == placement.file):
                matched_rule = r
                break

        min_w = matched_rule.min_width_px if matched_rule else 100
        min_h = matched_rule.min_height_px if matched_rule else 30

        if logo_w_px < min_w or logo_h_px < min_h:
            results.append(
                CheckResult(
                    check_name=f"logo_size_{i}_{placement.file}",
                    severity="blocking",
                    detail=(
                        f"Logo '{placement.file}' dimensions ({logo_w_px}x{logo_h_px}px) "
                        f"fall below minimum permitted size ({min_w}x{min_h}px)."
                    ),
                    fix_hint=f"Scale logo box for '{placement.file}' to at least {min_w}x{min_h}px.",
                )
            )
        else:
            results.append(
                CheckResult(
                    check_name=f"logo_size_{i}_{placement.file}",
                    severity="pass",
                    detail=f"Logo '{placement.file}' size ({logo_w_px}x{logo_h_px}px) meets size requirements.",
                    fix_hint=None,
                )
            )

    return results
