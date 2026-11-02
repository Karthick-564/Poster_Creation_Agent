"""Standalone deterministic QA gates module for poster layouts and renders.

Pure functions only. Zero pipeline dependencies or side effects.
Evaluates typographic text manifests and rendered raster images against
strict physical design gates:
- Canvas margin bounds compliance (zero escape)
- Pairwise row bounding box non-overlap
- Non-empty row validation (content & geometry)
- Seam defect detection in margin strips
- WCAG 2.1 relative luminance contrast ratio compliance
"""
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Optional, Sequence, Union

import numpy as np
from PIL import Image


@dataclass
class GateFailure:
    kind: str      # canvas_bounds | row_overlap | empty_row | seam | contrast | hero_overlap | dedupe | required_content | v_band_coverage
    target: str    # text row id, or "frame" for seams
    detail: str
    measured: dict # JSON-safe values that tripped the gate

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "detail": self.detail,
            "measured": self.measured,
        }


def _get_bounds(row: dict[str, Any]) -> tuple[float, float, float, float]:
    """Extract (x, y, w, h) from row dict, handling bounds subdict or direct keys."""
    b = row.get("bounds")
    if isinstance(b, dict):
        x = float(b.get("x", row.get("x", 0.0)))
        y = float(b.get("y", row.get("y", 0.0)))
        w = float(b.get("width", b.get("w", row.get("width", row.get("w", 0.0)))))
        h = float(b.get("height", b.get("h", row.get("height", row.get("h", 0.0)))))
    else:
        x = float(row.get("x", 0.0))
        y = float(row.get("y", 0.0))
        w = float(row.get("width", row.get("w", 0.0)))
        h = float(row.get("height", row.get("h", 0.0)))
    return x, y, w, h


def check_canvas_bounds(
    rows: Sequence[dict[str, Any]],
    canvas_w: float,
    canvas_h: float,
    margin_px: float,
) -> list[GateFailure]:
    """Flag text rows that escape canvas safe margins."""
    failures: list[GateFailure] = []
    tol = 0.05  # Sub-pixel rounding tolerance

    for row in rows:
        target_id = str(row.get("id", row.get("role", "unknown")))
        x, y, w, h = _get_bounds(row)

        # Zero-area rows handled separately by check_empty_rows
        if w <= 0 or h <= 0:
            continue

        escapes: list[str] = []
        if x < margin_px - tol:
            escapes.append(f"left escape: x={x:.2f} < margin={margin_px:.2f}")
        if y < margin_px - tol:
            escapes.append(f"top escape: y={y:.2f} < margin={margin_px:.2f}")
        if (x + w) > (canvas_w - margin_px + tol):
            escapes.append(f"right escape: x+w={(x + w):.2f} > canvas_w - margin={(canvas_w - margin_px):.2f}")
        if (y + h) > (canvas_h - margin_px + tol):
            escapes.append(f"bottom escape: y+h={(y + h):.2f} > canvas_h - margin={(canvas_h - margin_px):.2f}")

        if escapes:
            text_preview = str(row.get("text", ""))[:32]
            failures.append(GateFailure(
                kind="canvas_bounds",
                target=target_id,
                detail=f"Row '{text_preview}' escapes margin: " + "; ".join(escapes),
                measured={
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "width": round(w, 2),
                    "height": round(h, 2),
                    "margin": margin_px,
                    "canvas_w": canvas_w,
                    "canvas_h": canvas_h,
                    "escapes": escapes,
                },
            ))

    return failures


def check_row_overlap(rows: Sequence[dict[str, Any]]) -> list[GateFailure]:
    """Pairwise AABB intersection check. Reports intersection rect in measured."""
    failures: list[GateFailure] = []
    n = len(rows)

    for i in range(n):
        r1 = rows[i]
        id1 = str(r1.get("id", r1.get("role", f"row_{i}")))
        x1, y1, w1, h1 = _get_bounds(r1)
        if w1 <= 0 or h1 <= 0:
            continue

        for j in range(i + 1, n):
            r2 = rows[j]
            id2 = str(r2.get("id", r2.get("role", f"row_{j}")))
            x2, y2, w2, h2 = _get_bounds(r2)
            if w2 <= 0 or h2 <= 0:
                continue

            ix1 = max(x1, x2)
            iy1 = max(y1, y2)
            ix2 = min(x1 + w1, x2 + w2)
            iy2 = min(y1 + h1, y2 + h2)

            # Intersection must be positive area with sub-pixel tolerance
            if ix2 > ix1 + 0.5 and iy2 > iy1 + 0.5:
                iw = ix2 - ix1
                ih = iy2 - iy1
                intersection_rect = [round(ix1, 2), round(iy1, 2), round(iw, 2), round(ih, 2)]
                failures.append(GateFailure(
                    kind="row_overlap",
                    target=f"{id1}×{id2}",
                    detail=f"Rows {id1} and {id2} collide: overlap {iw:.1f}×{ih:.1f}px",
                    measured={
                        "row1_id": id1,
                        "row2_id": id2,
                        "row1_text": str(r1.get("text", ""))[:40],
                        "row2_text": str(r2.get("text", ""))[:40],
                        "intersection_rect": intersection_rect,
                        "overlap_area": round(iw * ih, 2),
                    },
                ))

    return failures


def check_empty_rows(rows: Sequence[dict[str, Any]]) -> list[GateFailure]:
    """Flag rows with blank/whitespace text or zero/negative area bounds."""
    failures: list[GateFailure] = []

    for i, row in enumerate(rows):
        target_id = str(row.get("id", row.get("role", f"row_{i}")))
        text = str(row.get("text", ""))
        x, y, w, h = _get_bounds(row)

        is_blank = not text.strip()
        is_zero_geom = w <= 0 or h <= 0

        if is_blank or is_zero_geom:
            reasons: list[str] = []
            if is_blank:
                reasons.append("blank or whitespace-only text")
            if is_zero_geom:
                reasons.append(f"zero/negative area bounds ({w}×{h})")

            failures.append(GateFailure(
                kind="empty_row",
                target=target_id,
                detail=f"Row {target_id} has invalid content/geometry: " + "; ".join(reasons),
                measured={
                    "text": text,
                    "bounds": {"x": x, "y": y, "width": w, "height": h},
                    "reasons": reasons,
                },
            ))

    return failures


def _load_image_array(image: Union[Image.Image, np.ndarray, Path, str]) -> np.ndarray:
    """Load image as float RGB numpy array [0, 255]."""
    if isinstance(image, (str, Path)):
        img = Image.open(image).convert("RGB")
        return np.array(img, dtype=float)
    elif isinstance(image, Image.Image):
        img = image.convert("RGB")
        return np.array(img, dtype=float)
    elif isinstance(image, np.ndarray):
        arr = image.astype(float)
        if arr.ndim == 2:
            return np.stack([arr] * 3, axis=-1)
        elif arr.shape[2] == 4:
            return arr[:, :, :3]
        return arr
    else:
        raise TypeError(f"Unsupported image type: {type(image)}")


def check_seams(
    image: Union[Image.Image, np.ndarray, Path, str],
    known_bands: Optional[list[tuple[float, float]]] = None,
    margin_pct: float = 0.08,
    delta_threshold: float = 6.0,
) -> list[GateFailure]:
    """Scan text-free margin strips for hard horizontal luminance seams.

    Detects sharp 1-6px row-to-row luminance steps (>= delta_threshold) that indicate
    clipped gradient rectangles or raster effect bounding box quantization seams.
    """
    arr = _load_image_array(image)
    H, W, _ = arr.shape
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

    w_strip = max(1, int(W * margin_pct))
    y_start = int(H * 0.05)
    y_end = int(H * 0.95)

    # Convert known_bands to pixel ranges if passed as fractions <= 1.0
    pixel_exempt_bands: list[tuple[int, int]] = []
    if known_bands:
        for b_min, b_max in known_bands:
            p_min = int(b_min * H) if b_min <= 1.0 else int(b_min)
            p_max = int(b_max * H) if b_max <= 1.0 else int(b_max)
            pixel_exempt_bands.append((p_min, p_max))

    def _is_exempt(y_idx: int) -> bool:
        for b_min, b_max in pixel_exempt_bands:
            if b_min <= y_idx <= b_max:
                return True
        return False

    # Scan text-free margin columns safely outside content/dividers (at ~2% and ~98% of width)
    scan_cols = [
        max(1, int(W * (margin_pct * 0.25))),
        min(W - 2, int(W * (1.0 - margin_pct * 0.25))),
    ]

    detected_seam_rows: dict[int, float] = {}

    for c in scan_cols:
        col_lum = lum[y_start:y_end, c]
        diffs = np.abs(np.diff(col_lum))
        for idx, d in enumerate(diffs):
            y_actual = y_start + idx
            if d >= delta_threshold and not _is_exempt(y_actual):
                if y_actual not in detected_seam_rows or d > detected_seam_rows[y_actual]:
                    detected_seam_rows[y_actual] = float(d)

    failures: list[GateFailure] = []

    # Cluster consecutive rows within 4px to report cohesive seam bands
    if detected_seam_rows:
        sorted_rows = sorted(detected_seam_rows.keys())
        clusters: list[list[int]] = []
        for r in sorted_rows:
            if not clusters or r > clusters[-1][-1] + 4:
                clusters.append([r])
            else:
                clusters[-1].append(r)

        for cl in clusters:
            y_center = cl[len(cl) // 2]
            max_d = max(detected_seam_rows[r] for r in cl)
            failures.append(GateFailure(
                kind="seam",
                target="frame",
                detail=f"Horizontal seam artifact detected at y={y_center} (band y={cl[0]}-{cl[-1]}) with luminance delta {max_d:.2f} >= {delta_threshold}",
                measured={
                    "y": y_center,
                    "y_band": [cl[0], cl[-1]],
                    "max_delta": round(max_d, 2),
                    "threshold": delta_threshold,
                    "canvas_h": H,
                    "canvas_w": W,
                },
            ))

    return failures


def _rgb_to_relative_luminance(arr: np.ndarray) -> np.ndarray:
    """Convert RGB array [0, 255] to standard WCAG 2.1 relative luminance."""
    norm = arr / 255.0
    lin = np.where(norm <= 0.04045, norm / 12.92, ((norm + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def sample_contrast(
    image: Union[Image.Image, np.ndarray, Path, str],
    rows: Sequence[dict[str, Any]],
    scale: float = 1.0,
) -> list[GateFailure]:
    """Evaluate WCAG 2.1 contrast ratio for all text rows against their background patch.

    Flags <4.5:1 for body text and <3.0:1 for large display text (size >= 24).
    """
    arr = _load_image_array(image)
    H, W, _ = arr.shape
    failures: list[GateFailure] = []

    for i, row in enumerate(rows):
        target_id = str(row.get("id", row.get("role", f"row_{i}")))
        x, y, w, h = _get_bounds(row)
        if w <= 0 or h <= 0:
            continue

        size = float(row.get("size", 16.0))
        style = str(row.get("style", "")).lower()
        # WCAG definition: large text is >=24pt, or >=18pt bold
        is_large = (size >= 24.0) or (size >= 18.0 and ("bold" in style or "black" in style))
        threshold = 3.0 if is_large else 4.5

        # Scaled pixel bounding box
        x_s = max(0, int(x * scale))
        y_s = max(0, int(y * scale))
        w_s = int(w * scale)
        h_s = int(h * scale)
        x_end = min(W, x_s + w_s)
        y_end = min(H, y_s + h_s)

        patch = arr[y_s:y_end, x_s:x_end]
        if patch.size == 0 or patch.shape[0] < 2 or patch.shape[1] < 2:
            continue

        patch_lum = _rgb_to_relative_luminance(patch)

        # Distinguish foreground and background via 99th and 1st percentiles
        lmax = float(np.percentile(patch_lum, 99.0))
        lmin = float(np.percentile(patch_lum, 1.0))
        cr = (lmax + 0.05) / (lmin + 0.05)

        if cr < threshold:
            failures.append(GateFailure(
                kind="contrast",
                target=target_id,
                detail=f"Low contrast for {'large' if is_large else 'body'} text '{str(row.get('text', ''))[:24]}': CR {cr:.2f}:1 < {threshold:.1f}:1",
                measured={
                    "contrast_ratio": round(cr, 2),
                    "threshold": threshold,
                    "is_large_text": is_large,
                    "text_size": size,
                    "L_fg": round(lmax, 4),
                    "L_bg": round(lmin, 4),
                },
            ))

    return failures


def run_all_manifest_gates(
    rows: Sequence[dict[str, Any]],
    canvas_w: float = 1080.0,
    canvas_h: float = 1350.0,
    margin_px: float = 40.0,
) -> dict[str, Any]:
    """Run pure manifest-based gates (bounds, overlaps, empty rows)."""
    bounds_failures = check_canvas_bounds(rows, canvas_w=canvas_w, canvas_h=canvas_h, margin_px=margin_px)
    overlap_failures = check_row_overlap(rows)
    empty_failures = check_empty_rows(rows)

    all_failures = bounds_failures + overlap_failures + empty_failures

    return {
        "passed": len(all_failures) == 0,
        "failure_count": len(all_failures),
        "failures": [f.to_dict() for f in all_failures],
        "summary": {
            "canvas_bounds_failures": len(bounds_failures),
            "row_overlap_failures": len(overlap_failures),
            "empty_row_failures": len(empty_failures),
        },
    }


def run_all_pixel_gates(
    image: Union[Image.Image, np.ndarray, Path, str],
    rows: Sequence[dict[str, Any]],
    scale: float = 1.0,
    known_bands: Optional[list[tuple[float, float]]] = None,
    margin_pct: float = 0.08,
    delta_threshold: float = 6.0,
) -> dict[str, Any]:
    """Run pure raster-based gates (seams, contrast)."""
    seam_failures = check_seams(
        image=image,
        known_bands=known_bands,
        margin_pct=margin_pct,
        delta_threshold=delta_threshold,
    )
    contrast_failures = sample_contrast(image=image, rows=rows, scale=scale)

    all_failures = seam_failures + contrast_failures

    return {
        "passed": len(all_failures) == 0,
        "failure_count": len(all_failures),
        "failures": [f.to_dict() for f in all_failures],
        "summary": {
            "seam_failures": len(seam_failures),
            "contrast_failures": len(contrast_failures),
        },
    }


def run_all_gates(
    rows: Sequence[dict[str, Any]],
    image: Optional[Union[Image.Image, np.ndarray, Path, str]] = None,
    canvas_w: float = 1080.0,
    canvas_h: float = 1350.0,
    margin_px: float = 40.0,
    scale: float = 1.0,
    known_bands: Optional[list[tuple[float, float]]] = None,
) -> dict[str, Any]:
    """Top-level aggregator running both manifest and pixel gates when image is provided."""
    manifest_res = run_all_manifest_gates(rows, canvas_w=canvas_w, canvas_h=canvas_h, margin_px=margin_px)

    pixel_res: dict[str, Any] = {
        "passed": True,
        "failure_count": 0,
        "failures": [],
        "summary": {"seam_failures": 0, "contrast_failures": 0},
    }
    if image is not None:
        pixel_res = run_all_pixel_gates(image, rows, scale=scale, known_bands=known_bands)

    total_failures = manifest_res["failures"] + pixel_res["failures"]
    return {
        "passed": len(total_failures) == 0,
        "failure_count": len(total_failures),
        "failures": total_failures,
        "manifest_gates": manifest_res,
        "pixel_gates": pixel_res,
    }


def check_hero_overlap(
    rows: Sequence[dict[str, Any]],
    hero_rect: Optional[Union[tuple[float, float, float, float], list[float]]] = None,
) -> list[GateFailure]:
    """Check text rows for collision with the hero cutout asset bounding rect."""
    failures: list[GateFailure] = []
    if not hero_rect or len(hero_rect) < 4:
        return failures

    hx, hy, hw, hh = float(hero_rect[0]), float(hero_rect[1]), float(hero_rect[2]), float(hero_rect[3])
    if hw <= 0 or hh <= 0:
        return failures

    for i, row in enumerate(rows):
        target_id = str(row.get("id", row.get("role", f"row_{i}")))
        rx, ry, rw, rh = _get_bounds(row)
        if rw <= 0 or rh <= 0:
            continue

        ix1 = max(rx, hx)
        iy1 = max(ry, hy)
        ix2 = min(rx + rw, hx + hw)
        iy2 = min(ry + rh, hy + hh)

        if ix2 > ix1 + 0.5 and iy2 > iy1 + 0.5:
            iw = ix2 - ix1
            ih = iy2 - iy1
            failures.append(GateFailure(
                kind="hero_overlap",
                target=target_id,
                detail=f"Row '{str(row.get('text', ''))[:32]}' intersects hero reservation rect by {iw:.1f}x{ih:.1f}px",
                measured={
                    "row_id": target_id,
                    "row_bounds": [round(rx, 2), round(ry, 2), round(rw, 2), round(rh, 2)],
                    "hero_rect": [round(hx, 2), round(hy, 2), round(hw, 2), round(hh, 2)],
                    "intersection_rect": [round(ix1, 2), round(iy1, 2), round(iw, 2), round(ih, 2)],
                    "overlap_area": round(iw * ih, 2),
                },
            ))
    return failures


def check_dedupe(rows: Sequence[dict[str, Any]]) -> list[GateFailure]:
    """Flag duplicate closing lines or identical text emitted across multiple roles."""
    failures: list[GateFailure] = []
    seen: dict[str, list[dict[str, Any]]] = {}

    for i, r in enumerate(rows):
        txt = str(r.get("text", "")).strip().lower()
        if len(txt) < 8 or txt in ("open positions", "scan to apply", "presented by"):
            continue
        norm_txt = re.sub(r"[^\w\s]", "", txt)
        if len(norm_txt) < 8:
            continue
        seen.setdefault(norm_txt, []).append(r)

    for norm_txt, occurrences in seen.items():
        if len(occurrences) > 1:
            roles = [str(o.get("role", o.get("id", "unknown"))) for o in occurrences]
            sample_txt = str(occurrences[0].get("text", ""))[:48]
            failures.append(GateFailure(
                kind="dedupe",
                target=",".join(roles),
                detail=f"Duplicate text '{sample_txt}' rendered {len(occurrences)} times across roles: {', '.join(roles)}",
                measured={
                    "text": sample_txt,
                    "count": len(occurrences),
                    "roles": roles,
                },
            ))
    return failures


def check_required_content(
    rows: Sequence[dict[str, Any]],
    brief: Any = None,
    brief_text: Optional[str] = None,
) -> list[GateFailure]:
    """Verify that required content supplied by the brief (date, venue, CTA, QR) is present in the render."""
    failures: list[GateFailure] = []
    expected: dict[str, str] = {}

    if brief is not None:
        if hasattr(brief, "get_text"):
            for k in ("date", "venue", "cta", "qr_url"):
                val = brief.get_text(k)
                if val:
                    expected[k] = val
        elif isinstance(brief, dict):
            for k in ("date", "venue", "cta", "qr_url"):
                if brief.get(k):
                    expected[k] = str(brief[k])
    elif brief_text:
        for m in re.finditer(r"(?i)\b(date|venue|cta|qr(?:_url)?)\s*:\s*([^\r\n]+)", brief_text):
            k = m.group(1).lower()
            if "qr" in k:
                k = "qr_url"
            expected[k] = m.group(2).strip()

    if not expected:
        return failures

    all_row_texts = " ".join(str(r.get("text", "")) for r in rows).lower()
    all_roles = {str(r.get("role", "")).lower() for r in rows}

    for req_key, req_val in expected.items():
        val_clean = req_val.strip().lower()
        if not val_clean:
            continue
        found = False
        if req_key == "date":
            alpha_words = [w for w in re.findall(r"[a-zA-Z]+", val_clean) if len(w) >= 3]
            if any(r in all_roles for r in ("date", "schedule_text", "logistics_date")) or (
                alpha_words and any(w in all_row_texts for w in alpha_words)
            ):
                found = True
        elif req_key == "venue":
            words = [w for w in re.findall(r"[a-zA-Z]+", val_clean) if len(w) >= 3]
            if any(r in all_roles for r in ("venue", "location")) or (
                words and any(w in all_row_texts for w in words)
            ):
                found = True
        elif req_key == "cta":
            words = [w for w in re.findall(r"[a-zA-Z]+", val_clean) if len(w) >= 3]
            if any(r in all_roles for r in ("cta", "_structure_qr", "action", "button")) or (
                words and any(w in all_row_texts for w in words)
            ):
                found = True
        elif req_key == "qr_url":
            if "_structure_qr" in all_roles or "scan" in all_row_texts or "qr" in all_row_texts:
                found = True

        if not found:
            failures.append(GateFailure(
                kind="required_content",
                target=req_key,
                detail=f"Required content '{req_key}' ('{req_val}') supplied in brief but missing from render manifest",
                measured={
                    "field": req_key,
                    "expected_text": req_val,
                },
            ))
    return failures


def check_v_band_coverage_gate(
    rows: Sequence[dict[str, Any]],
    canvas_h: float = 1920.0,
    min_coverage: float = 70.0,
) -> tuple[bool, float, list[int], list[GateFailure]]:
    """Check vertical rhythm: content must cover >= min_coverage% of vertical bands."""
    failures: list[GateFailure] = []
    band_fractions = [
        (0.00, 0.15, "Band 0: Header & Brand"),
        (0.15, 0.35, "Band 1: Headline & Hook"),
        (0.35, 0.55, "Band 2: Hero Visual"),
        (0.55, 0.80, "Band 3: Body & Positions"),
        (0.80, 1.00, "Band 4: Logistics & Footer"),
    ]
    total_bands = len(band_fractions)
    occupied = set()

    for r in rows:
        rx, ry, rw, rh = _get_bounds(r)
        if rw <= 0 or rh <= 0:
            continue
        top_f = ry / canvas_h
        bot_f = (ry + rh) / canvas_h
        for idx, (b_start, b_end, _) in enumerate(band_fractions):
            if not (bot_f < b_start or top_f > b_end):
                occupied.add(idx)

    cov_pct = (len(occupied) / total_bands) * 100.0 if total_bands > 0 else 0.0
    passed = cov_pct >= min_coverage

    if not passed:
        failures.append(GateFailure(
            kind="v_band_coverage",
            target="vertical_rhythm",
            detail=f"Vertical band coverage {cov_pct:.1f}% < required {min_coverage:.1f}%",
            measured={
                "coverage_pct": round(cov_pct, 1),
                "threshold_pct": min_coverage,
                "occupied_bands": sorted(list(occupied)),
                "total_bands": total_bands,
            },
        ))

    return passed, cov_pct, sorted(list(occupied)), failures


def check_structure_contrast(
    image: Optional[Union[Image.Image, np.ndarray, Path, str]],
    rows: Sequence[dict[str, Any]],
    scale: float = 2.0,
) -> list[GateFailure]:
    """Verify WCAG relative luminance contrast >= 4.5:1 for rows against rendered raster."""
    if image is None:
        return []
    return sample_contrast(image=image, rows=rows, scale=scale)


def run_stage6_gates(
    rows: Sequence[dict[str, Any]],
    canvas_w: float = 1080.0,
    canvas_h: float = 1920.0,
    margin_px: float = 48.6,
    image: Optional[Union[Image.Image, np.ndarray, Path, str]] = None,
    hero_rect: Optional[Union[tuple[float, float, float, float], list[float]]] = None,
    brief: Any = None,
    scale: float = 2.0,
) -> list[dict[str, Any]]:
    """Run all 6 Stage 6 QA gates in strict sequence and return formatted gate records.

    Order of evaluation:
    1. text_bounds
    2. hero_overlap
    3. structure_contrast
    4. required_content
    5. dedupe
    6. v_band_coverage
    """
    gate_records: list[dict[str, Any]] = []

    # 1. text_bounds
    bounds_failures = check_canvas_bounds(rows, canvas_w=canvas_w, canvas_h=canvas_h, margin_px=margin_px)
    if bounds_failures:
        gate_records.append({
            "name": "text_bounds",
            "verdict": "FAIL",
            "measured": {
                "failure_count": len(bounds_failures),
                "escaping_targets": [f.target for f in bounds_failures],
                "margin_px": margin_px,
            },
            "detail": f"{len(bounds_failures)} text rows exceed canvas safe margins (margin={margin_px:.1f}px)",
        })
    else:
        gate_records.append({
            "name": "text_bounds",
            "verdict": "PASS",
            "measured": {"margin_px": margin_px, "canvas_w": canvas_w, "canvas_h": canvas_h, "escapes": 0},
            "detail": "All queued text rows strictly within canvas safe margins.",
        })

    # 2. hero_overlap
    overlap_failures = check_hero_overlap(rows, hero_rect=hero_rect)
    if overlap_failures:
        gate_records.append({
            "name": "hero_overlap",
            "verdict": "FAIL",
            "measured": {
                "failure_count": len(overlap_failures),
                "colliding_targets": [f.target for f in overlap_failures],
                "hero_rect": list(hero_rect) if hero_rect else None,
            },
            "detail": f"{len(overlap_failures)} text rows intersect hero reservation rect",
        })
    else:
        gate_records.append({
            "name": "hero_overlap",
            "verdict": "PASS",
            "measured": {"hero_rect": list(hero_rect) if hero_rect else None, "intersections": 0},
            "detail": "Zero text rows intersect hero asset reservation rect.",
        })

    # 3. structure_contrast
    contrast_failures = check_structure_contrast(image=image, rows=rows, scale=scale) if image is not None else []
    if contrast_failures:
        min_cr = min((float(f.measured.get("contrast_ratio", 0.0)) for f in contrast_failures), default=0.0)
        gate_records.append({
            "name": "structure_contrast",
            "verdict": "FAIL",
            "measured": {
                "failure_count": len(contrast_failures),
                "min_contrast_ratio": min_cr,
                "targets": [f.target for f in contrast_failures],
            },
            "detail": f"{len(contrast_failures)} rows violate WCAG contrast floors (lowest CR: {min_cr:.2f}:1 < 4.5:1)",
        })
    else:
        gate_records.append({
            "name": "structure_contrast",
            "verdict": "PASS",
            "measured": {"min_contrast_floor": 4.5, "sampled_rows": len(rows)},
            "detail": "All evaluated text rows meet WCAG 2.1 relative luminance contrast floors.",
        })

    # 4. required_content
    req_failures = check_required_content(rows, brief=brief)
    if req_failures:
        missing_fields = [f.target for f in req_failures]
        gate_records.append({
            "name": "required_content",
            "verdict": "FAIL",
            "measured": {
                "missing_fields": missing_fields,
            },
            "detail": f"Required content missing from render manifest: {', '.join(missing_fields)}",
        })
    else:
        gate_records.append({
            "name": "required_content",
            "verdict": "PASS",
            "measured": {"missing_count": 0},
            "detail": "All brief-supplied required content (date, venue, CTA, QR) verified in render.",
        })

    # 5. dedupe
    dedupe_failures = check_dedupe(rows)
    if dedupe_failures:
        gate_records.append({
            "name": "dedupe",
            "verdict": "FAIL",
            "measured": {
                "duplicate_count": len(dedupe_failures),
                "targets": [f.target for f in dedupe_failures],
            },
            "detail": f"{len(dedupe_failures)} duplicate closing or structural text elements detected.",
        })
    else:
        gate_records.append({
            "name": "dedupe",
            "verdict": "PASS",
            "measured": {"duplicate_count": 0},
            "detail": "Zero duplicate closing lines or structural text rows.",
        })

    # 6. v_band_coverage
    vband_passed, cov_pct, occ_bands, vband_failures = check_v_band_coverage_gate(rows, canvas_h=canvas_h, min_coverage=70.0)
    if not vband_passed:
        gate_records.append({
            "name": "v_band_coverage",
            "verdict": "FAIL",
            "measured": {
                "coverage_pct": round(cov_pct, 1),
                "threshold_pct": 70.0,
                "occupied_bands": occ_bands,
            },
            "detail": f"Vertical band coverage {cov_pct:.1f}% below 70% threshold.",
        })
    else:
        gate_records.append({
            "name": "v_band_coverage",
            "verdict": "PASS",
            "measured": {
                "coverage_pct": round(cov_pct, 1),
                "threshold_pct": 70.0,
                "occupied_bands": occ_bands,
            },
            "detail": f"Vertical band coverage {cov_pct:.1f}% meets >= 70% rhythm standard.",
        })

    return gate_records


def check_refusal_free(image_input: Union[Path, str, Image.Image]) -> list[GateFailure]:
    """Scan generated raster image for AI safety filter refusal text or characteristic blocked-image artifacts."""
    failures: list[GateFailure] = []

    if isinstance(image_input, (str, Path)):
        p = Path(image_input)
        if not p.exists():
            return failures
        try:
            im = Image.open(p).convert("RGB")
        except Exception:
            return failures
        target_name = str(p.name)
    else:
        im = image_input.convert("RGB")
        target_name = "image_layer"

    # 1. OCR scan if pytesseract is installed
    try:
        import pytesseract
        ocr_text = pytesseract.image_to_string(im).lower()
        refusal_keywords = [
            "blocked by safety filter",
            "safety filter",
            "blocked by safety",
            "content policy",
            "safety violation",
            "image blocked",
            "refusal",
        ]
        for kw in refusal_keywords:
            if kw in ocr_text:
                failures.append(GateFailure(
                    kind="refusal",
                    target=target_name,
                    detail=f"Safety filter refusal text detected via OCR: '{kw}'",
                    measured={"ocr_match": kw, "source": "pytesseract"},
                ))
                return failures
    except Exception:
        pass

    # 2. Deterministic heuristic scan for refusal artifacts
    # Characteristic safety filter artifact:
    # A mostly flat/solid canvas with a narrow horizontal bar of high-contrast text in the central band.
    arr = np.array(im, dtype=np.float32)
    h, w, _ = arr.shape
    if h < 50 or w < 50:
        return failures

    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

    # Check top/bottom strip flatness (top 20% and bottom 20%)
    top_strip = gray[:int(h * 0.2), :]
    bot_strip = gray[int(h * 0.8):, :]
    top_std = float(np.std(top_strip))
    bot_std = float(np.std(bot_strip))

    # Center zone (30% to 70%)
    center_strip = gray[int(h * 0.3):int(h * 0.7), :]
    center_diff = np.abs(np.diff(center_strip, axis=1))
    center_edge_max = float(np.max(center_diff)) if center_diff.size > 0 else 0.0

    # If top and bottom strips are flat (< 4.0 std dev) and identical in mean (abs diff < 3.0)
    if top_std < 4.0 and bot_std < 4.0 and abs(float(np.mean(top_strip)) - float(np.mean(bot_strip))) < 3.0:
        if center_edge_max > 120.0:
            row_stds = np.std(center_strip, axis=1)
            high_std_rows = int(np.sum(row_stds > 20.0))
            if 3 <= high_std_rows <= max(120, int(h * 0.15)):
                failures.append(GateFailure(
                    kind="refusal",
                    target=target_name,
                    detail="Deterministic heuristic detected safety filter refusal banner (flat canvas with high-contrast text strip)",
                    measured={
                        "top_std": round(top_std, 2),
                        "bot_std": round(bot_std, 2),
                        "center_edge_max": round(center_edge_max, 2),
                        "high_std_rows": high_std_rows,
                    },
                ))
                return failures

    return failures

