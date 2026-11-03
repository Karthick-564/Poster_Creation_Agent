"""Deterministic v2 gates. These are the referee, not a suggestion engine.

The suite reuses the proven pure gates from ``poster_agent.qa.gates`` for
bounds, overlap, contrast, dedupe and vertical rhythm, then adds the brand
checks the legacy pipeline never wired: logo presence/aspect/clear-space/
solid-field, hero alpha, palette, output integrity and OCR.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image

from poster_agent.checks.ocr import normalize_str, string_similarity
from poster_agent.qa.design import palette_coverage
from poster_agent.qa.gates import (
    check_canvas_bounds,
    check_dedupe,
    check_hero_overlap,
    check_row_overlap,
    check_v_band_coverage_gate,
    sample_contrast,
)
from poster_agent.qa.gates import GateFailure

from .contracts import (
    AssetBundle,
    BrandContract,
    GateIssue,
    GateReport,
    PosterSpec,
    RenderResult,
)


def _issue(
    code: str,
    gate: str,
    stage: str,
    message: str,
    target: str = "",
    severity: str = "blocking",
    fix_hint: str | None = None,
    measured: dict[str, Any] | None = None,
) -> GateIssue:
    return GateIssue(
        code=code,
        gate=gate,
        stage=stage,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        message=message,
        target=target,
        fix_hint=fix_hint,
        measured=measured or {},
    )


def _from_failure(failure: GateFailure, stage: str = "plan") -> GateIssue:
    return _issue(
        code=failure.kind,
        gate=failure.kind,
        stage=stage,
        message=failure.detail,
        target=failure.target,
        measured=failure.measured,
    )


def _row_dicts(render: RenderResult) -> list[dict[str, Any]]:
    return [row.as_gate_row() for row in render.rows]


def _rect_intersection(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> tuple[float, float, float, float] | None:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2 - x1, y2 - y1


def _logo_exclusion(
    spec: PosterSpec, brand: BrandContract
) -> tuple[float, float, float, float] | None:
    if not spec.logo_slots:
        return None
    fmt = spec.format
    x, y, w, h = spec.logo_slots[0].box.to_px(fmt.width, fmt.height)
    pad = brand.clear_space_px(fmt)
    return x - pad, y - pad, w + 2 * pad, h + 2 * pad


def _field_rect(
    spec: PosterSpec, brand: BrandContract
) -> tuple[float, float, float, float] | None:
    if not spec.logo_slots:
        return None
    fmt = spec.format
    x, y, w, h = spec.logo_slots[0].box.to_px(fmt.width, fmt.height)
    # The solid field only needs to cover the mark and a small optical margin.
    # The contracted 10 mm clear space is separate: it must stay empty, but it
    # may be the brand background rather than a white card.
    pad = min(brand.clear_space_px(fmt), max(12.0, 0.2 * w))
    return max(0.0, x - pad), max(0.0, y - pad), min(fmt.width, x + w + pad), min(fmt.height, y + h + pad)


def _check_output(spec: PosterSpec, render: RenderResult) -> list[GateIssue]:
    issues: list[GateIssue] = []
    if not render.output_png:
        return [_issue("output_missing", "output", "compose", "Renderer produced no raster output.", fix_hint="Re-run compose.")]
    path = Path(render.output_png)
    if not path.exists():
        return [_issue("output_missing", "output", "compose", f"Rendered file does not exist: {path}", fix_hint="Re-run compose.")]
    try:
        with Image.open(path) as image:
            width, height = image.size
    except Exception as exc:
        return [_issue("output_unreadable", "output", "compose", f"Rendered file is not decodable: {exc}", fix_hint="Re-run compose.")]
    if (width, height) != (spec.format.width, spec.format.height):
        issues.append(
            _issue(
                "output_dimensions",
                "output",
                "compose",
                f"Output is {width}x{height}, expected {spec.format.width}x{spec.format.height}.",
                fix_hint="Check renderer canvas size and export scale.",
            )
        )
    return issues


def _check_safe_area(spec: PosterSpec, brand: BrandContract, render: RenderResult) -> list[GateIssue]:
    issues: list[GateIssue] = []
    fmt = spec.format
    margin = brand.safe_margin_px(fmt)

    def check_rect(name: str, rect: tuple[float, float, float, float] | None, stage: str) -> None:
        if not rect:
            return
        x, y, w, h = rect
        if x < margin - 0.5 or y < margin - 0.5 or x + w > fmt.width - margin + 0.5 or y + h > fmt.height - margin + 0.5:
            issues.append(
                _issue(
                    "safe_area_escape",
                    "safe_area",
                    stage,
                    f"{name} escapes the {brand.safe_margin_pct:.1f}% safe margin ({margin:.1f}px).",
                    target=name,
                    measured={"rect": [round(v, 1) for v in rect], "margin_px": round(margin, 1)},
                    fix_hint="Move the element inward or reduce its size.",
                )
            )

    check_rect("logo", render.logo_rect, "plan")
    check_rect("hero", render.hero_rect, "plan")
    for key, rect in render.image_rects.items():
        check_rect(key, rect, "plan")
    return issues


def _check_logo(
    spec: PosterSpec,
    brand: BrandContract,
    assets: AssetBundle,
    render: RenderResult,
) -> list[GateIssue]:
    issues: list[GateIssue] = []
    if brand.logo.required and (not assets.logo or not render.logo_rect):
        issues.append(
            _issue(
                "logo_missing",
                "logo",
                "assets",
                "Required institutional logo is missing from the render.",
                target="brand_logo",
                fix_hint=f"Provide the official logo at {brand.logo.asset!r}.",
            )
        )
        return issues

    if assets.logo and assets.logo.placeholder:
        issues.append(
            _issue(
                "logo_placeholder",
                "logo",
                "assets",
                "A marked placeholder logo is in use; the poster is not brand-ready.",
                target="brand_logo",
                severity="warning",
                fix_hint="Replace the placeholder with the official asset.",
            )
        )

    if not spec.logo_slots or not render.logo_rect:
        return issues

    x, y, w, h = render.logo_rect
    exclusion = _logo_exclusion(spec, brand)
    rows = _row_dicts(render)

    if exclusion:
        for row in rows:
            rect = (row["x"], row["y"], row["width"], row["height"])
            hit = _rect_intersection(exclusion, rect)
            if hit:
                issues.append(
                    _issue(
                        "logo_clear_space",
                        "logo",
                        "plan",
                        f"Text {row['id']!r} enters the logo clear-space zone.",
                        target=row["id"],
                        measured={"intersection": [round(v, 1) for v in hit]},
                        fix_hint="Shorten or move the text block away from the top-right corner.",
                    )
                )
        if render.hero_rect:
            hit = _rect_intersection(exclusion, render.hero_rect)
            if hit:
                issues.append(
                    _issue(
                        "logo_clear_space",
                        "logo",
                        "plan",
                        "Hero art enters the logo clear-space zone.",
                        target="hero",
                        measured={"intersection": [round(v, 1) for v in hit]},
                        fix_hint="Scale or move the hero away from the logo field.",
                    )
                )

    # Placement quadrant.
    cx, cy = x + w / 2, y + h / 2
    placement = spec.logo_slots[0].placement
    quadrants = {
        "top-right": (cx >= 0.6 * spec.format.width, cy <= 0.4 * spec.format.height),
        "top-left": (cx <= 0.4 * spec.format.width, cy <= 0.4 * spec.format.height),
        "bottom-right": (cx >= 0.6 * spec.format.width, cy >= 0.6 * spec.format.height),
        "bottom-left": (cx <= 0.4 * spec.format.width, cy >= 0.6 * spec.format.height),
    }
    if not all(quadrants[placement]):
        issues.append(
            _issue(
                "logo_placement",
                "logo",
                "plan",
                f"Logo is not in the required {placement} placement.",
                target="brand_logo",
                measured={"center": [round(cx, 1), round(cy, 1)]},
                fix_hint="Reposition the logo to the contracted corner.",
            )
        )

    # Intrinsic aspect ratio.
    if brand.logo.preserve_aspect and assets.logo and assets.logo.height > 0 and h > 0:
        asset_ratio = assets.logo.width / assets.logo.height
        placed_ratio = w / h
        delta = abs(placed_ratio - asset_ratio) / max(0.01, asset_ratio)
        if delta > 0.03:
            issues.append(
                _issue(
                    "logo_aspect",
                    "logo",
                    "compose",
                    f"Logo aspect ratio changed from {asset_ratio:.3f} to {placed_ratio:.3f}.",
                    target="brand_logo",
                    measured={"asset_ratio": round(asset_ratio, 3), "placed_ratio": round(placed_ratio, 3)},
                    fix_hint="Rescale the logo box from the intrinsic asset ratio.",
                )
            )

    # Solid field: sample the ring between the field edge and the mark.
    field = _field_rect(spec, brand)
    if brand.logo.solid_field_only and render.output_png and Path(render.output_png).exists() and field:
        image = np.asarray(Image.open(render.output_png).convert("RGB"), dtype=np.float32)
        fx1, fy1, fx2, fy2 = field
        lx, ly, lw, lh = render.logo_rect
        x1, y1 = max(0, int(fx1)), max(0, int(fy1))
        x2, y2 = min(image.shape[1], int(fx2)), min(image.shape[0], int(fy2))
        mx1, my1 = max(0, int(lx)), max(0, int(ly))
        mx2, my2 = min(image.shape[1], int(lx + lw)), min(image.shape[0], int(ly + lh))
        ring = image[y1:y2, x1:x2].copy()
        mask = np.ones(ring.shape[:2], dtype=bool)
        mask[max(0, my1 - y1) : max(0, my2 - y1), max(0, mx1 - x1) : max(0, mx2 - x1)] = False
        pixels = ring[mask]
        if pixels.size:
            luminance = 0.299 * pixels[:, 0] + 0.587 * pixels[:, 1] + 0.114 * pixels[:, 2]
            channel_spreads = [
                float(np.percentile(pixels[:, channel], 99) - np.percentile(pixels[:, channel], 1))
                for channel in range(3)
            ]
            spread = max(channel_spreads)
            std = float(np.std(luminance))
            if spread > 22.0 or std > 9.0:
                issues.append(
                    _issue(
                        "logo_solid_field",
                        "logo",
                        "compose",
                        f"Logo clear-space is not a solid field (spread {spread:.1f}, std {std:.1f}).",
                        target="brand_logo",
                        measured={"spread": round(spread, 1), "std": round(std, 1)},
                        fix_hint="Paint a solid brand field behind the logo; remove gradients and art.",
                    )
                )

    return issues


def _check_hero_alpha(spec: PosterSpec, assets: AssetBundle) -> list[GateIssue]:
    issues: list[GateIssue] = []
    hero = spec.image("hero")
    if not hero:
        return issues
    asset = assets.get(hero.id)
    if not asset or not Path(asset.path).exists():
        if hero.required:
            issues.append(
                _issue(
                    "hero_missing",
                    "hero_alpha",
                    "assets",
                    "Required hero asset is missing.",
                    target=hero.id,
                    fix_hint="Generate the Qwen RGBA cutout or supply a hero asset.",
                )
            )
        return issues

    if not hero.transparent:
        return issues

    try:
        with Image.open(asset.path) as image:
            if image.mode not in ("RGBA", "LA"):
                issues.append(
                    _issue(
                        "hero_not_alpha",
                        "hero_alpha",
                        "assets",
                        f"Hero is {image.mode}, not an alpha cutout.",
                        target=hero.id,
                        fix_hint="Generate with Qwen-Image 2.1 native RGBA.",
                    )
                )
                return issues
            rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    except Exception as exc:
        issues.append(
            _issue(
                "hero_unreadable",
                "hero_alpha",
                "assets",
                f"Hero asset is not decodable: {exc}",
                target=hero.id,
            )
        )
        return issues

    alpha = rgba[:, :, 3]
    transparent_share = float(np.mean(alpha < 250))
    if transparent_share < 0.02 or transparent_share > 0.995:
        issues.append(
            _issue(
                "hero_alpha_coverage",
                "hero_alpha",
                "assets",
                f"Hero alpha coverage is {transparent_share:.1%}; expected a real cutout.",
                target=hero.id,
                measured={"transparent_share": round(transparent_share, 4)},
                fix_hint="Regenerate the hero with a transparent background prompt.",
            )
        )

    visible = rgba[:, :, :3][alpha > 10]
    if visible.size:
        mean_luminance = float(np.mean(0.299 * visible[:, 0] + 0.587 * visible[:, 1] + 0.114 * visible[:, 2]))
        if mean_luminance < 18.0:
            issues.append(
                _issue(
                    "hero_void",
                    "hero_alpha",
                    "assets",
                    f"Opaque hero pixels are near-black (mean luminance {mean_luminance:.1f}); it will disappear.",
                    target=hero.id,
                    measured={"mean_luminance": round(mean_luminance, 1)},
                    fix_hint="Regenerate with visible midtones or a lighter subject.",
                )
            )
    return issues


def _check_palette(spec: PosterSpec, render: RenderResult) -> list[GateIssue]:
    if not render.output_png or not Path(render.output_png).exists():
        return []
    report = palette_coverage(render.output_png, spec.palette, tolerance=52.0, min_pixel_share=0.002)
    issues: list[GateIssue] = []
    missing = set(report["missing_colors"])
    primary = spec.palette[0] if spec.palette else None
    surface = spec.palette[-1] if spec.palette else None
    if primary and primary in missing:
        issues.append(
            _issue(
                "palette_primary_missing",
                "palette",
                "assets",
                f"Brand primary {primary} is not represented in the render.",
                measured=report,
                fix_hint="Regenerate the background with the brand palette.",
            )
        )
    elif surface and surface in missing:
        issues.append(
            _issue(
                "palette_surface_missing",
                "palette",
                "assets",
                f"Brand surface {surface} is not represented in the render.",
                severity="warning",
                measured=report,
                fix_hint="Add a clean surface field for the logo or a text band.",
            )
        )
    if report["coverage_ratio"] < 0.6:
        issues.append(
            _issue(
                "palette_coverage",
                "palette",
                "assets",
                f"Only {report['coverage_ratio']:.0%} of the brand palette is represented.",
                severity="warning",
                measured=report,
                fix_hint="Pull the background and accents toward the contracted palette.",
            )
        )
    return issues


def _check_required(spec: PosterSpec, assets: AssetBundle, render: RenderResult) -> list[GateIssue]:
    issues: list[GateIssue] = []
    roles = {block.role for block in spec.text_blocks}
    row_text = " ".join(row.text for row in render.rows).lower()
    aliases = {"title": "headline", "qr": "qr"}
    for element in spec.required_elements:
        if element == "logo":
            if not assets.logo or not render.logo_rect:
                issues.append(
                    _issue(
                        "required_logo",
                        "required_content",
                        "assets",
                        "Mandatory element 'logo' is absent.",
                        target="logo",
                    )
                )
            continue
        if element == "qr":
            if not spec.qr or "qr" not in render.image_rects:
                issues.append(
                    _issue(
                        "required_qr",
                        "required_content",
                        "plan",
                        "Mandatory element 'qr' is absent.",
                        target="qr",
                    )
                )
            continue
        role = aliases.get(element, element)
        if role not in roles:
            issues.append(
                _issue(
                    "required_content",
                    "required_content",
                    "plan",
                    f"Mandatory element {element!r} is absent from the plan.",
                    target=element,
                    fix_hint="Add the field to the brief or choose a template with room for it.",
                )
            )
        elif role != "qr":
            block = spec.text(role)
            if block and normalize_str(block.text) not in normalize_str(row_text):
                # Fall back to a fuzzy check because OCR/renderers may wrap text.
                if string_similarity(block.text, row_text) < 0.5:
                    issues.append(
                        _issue(
                            "required_text_missing",
                            "required_content",
                            "compose",
                            f"Mandatory element {element!r} is not present in the rendered text.",
                            target=element,
                        )
                    )
    return issues


def _check_ocr(
    spec: PosterSpec,
    render: RenderResult,
    ocr_lines: Iterable[str] | None,
) -> list[GateIssue]:
    lines = [normalize_str(line) for line in (ocr_lines or []) if normalize_str(line)]
    if not lines:
        return [
            _issue(
                "ocr_unavailable",
                "ocr",
                "compose",
                "No OCR engine or OCR lines supplied; text presence was checked from the render manifest only.",
                severity="warning",
                fix_hint="Install RapidOCR/PaddleOCR or pass OCR lines to run the pixel text gate.",
            )
        ]

    joined = " ".join(lines)
    issues: list[GateIssue] = []
    for block in spec.text_blocks:
        expected = normalize_str(block.text)
        if not expected:
            continue
        best = max((string_similarity(expected, line) for line in lines), default=0.0)
        if expected in joined or best >= 0.82:
            continue
        issues.append(
            _issue(
                "ocr_text_mismatch",
                "ocr",
                "compose",
                f"OCR could not find planned text {block.text[:48]!r} (best similarity {best:.2f}).",
                target=block.id,
                measured={"best_similarity": round(best, 3)},
                fix_hint="Re-render the text or check font fallback/glyph coverage.",
            )
        )
    return issues


def run_gates(
    spec: PosterSpec,
    assets: AssetBundle,
    brand: BrandContract,
    render: RenderResult,
    ocr_lines: Iterable[str] | None = None,
) -> GateReport:
    """Run every deterministic gate and return a stage-routable report."""
    issues: list[GateIssue] = []
    checks: list[dict[str, Any]] = []
    rows = _row_dicts(render)

    def record(name: str, stage: str, found: list[GateIssue]) -> None:
        blocking = [i for i in found if i.severity == "blocking"]
        checks.append(
            {
                "name": name,
                "stage": stage,
                "verdict": "FAIL" if blocking else ("WARN" if found else "PASS"),
                "issue_count": len(found),
                "detail": "; ".join(i.message for i in found)[:500] if found else "",
            }
        )
        issues.extend(found)

    record("output", "compose", _check_output(spec, render))

    fmt = spec.format
    margin = brand.safe_margin_px(fmt)
    bounds = check_canvas_bounds(rows, canvas_w=fmt.width, canvas_h=fmt.height, margin_px=margin)
    record("text_bounds", "plan", [_from_failure(f, "plan") for f in bounds])
    overlaps = check_row_overlap(rows)
    record("text_overlap", "plan", [_from_failure(f, "plan") for f in overlaps])
    hero_overlaps = check_hero_overlap(rows, hero_rect=render.hero_rect)
    record("hero_overlap", "plan", [_from_failure(f, "plan") for f in hero_overlaps])
    dedupe = check_dedupe(rows)
    record("dedupe", "plan", [_from_failure(f, "plan") for f in dedupe])

    if render.output_png and Path(render.output_png).exists():
        contrast = sample_contrast(render.output_png, rows)
        record("contrast", "plan", [_from_failure(f, "plan") for f in contrast])
    else:
        record(
            "contrast",
            "compose",
            [
                _issue(
                    "contrast_not_run",
                    "contrast",
                    "compose",
                    "Contrast was not evaluated because no raster output exists.",
                    severity="warning",
                )
            ],
        )

    passed_band, coverage, bands, band_failures = check_v_band_coverage_gate(
        rows, canvas_h=fmt.height, min_coverage=70.0
    )
    record("v_band_coverage", "plan", [_from_failure(f, "plan") for f in band_failures])

    record("safe_area", "plan", _check_safe_area(spec, brand, render))
    record("logo", "plan", _check_logo(spec, brand, assets, render))
    record("hero_alpha", "assets", _check_hero_alpha(spec, assets))
    record("palette", "assets", _check_palette(spec, render))
    record("required_content", "plan", _check_required(spec, assets, render))
    record("ocr", "compose", _check_ocr(spec, render, ocr_lines))

    blocking = [i for i in issues if i.severity == "blocking"]
    return GateReport(passed=not blocking, issues=issues, checks=checks)
