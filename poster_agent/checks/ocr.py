"""Deterministic OCR checks comparing detected text with spec strings."""
import difflib
import re
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.spec.models import PosterSpec, TextElement
from .models import CheckResult


class DetectedLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    confidence: float
    bbox: list[list[float]]  # 4 corner points [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    center_y: float
    center_x: float
    top: float
    bottom: float


class OCRResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[DetectedLine]
    full_text: str


_OCR_ENGINE_INSTANCE = None


def get_ocr_engine():
    """Load RapidOCR or PaddleOCR engine singleton."""
    global _OCR_ENGINE_INSTANCE
    if _OCR_ENGINE_INSTANCE is not None:
        return _OCR_ENGINE_INSTANCE

    try:
        from rapidocr_onnxruntime import RapidOCR
        _OCR_ENGINE_INSTANCE = RapidOCR()
        return _OCR_ENGINE_INSTANCE
    except Exception:
        pass

    try:
        from paddleocr import PaddleOCR
        _OCR_ENGINE_INSTANCE = PaddleOCR(use_angle_cls=True, lang="en")
        return _OCR_ENGINE_INSTANCE
    except Exception:
        pass

    return None


def extract_text_from_image(image_path: str | Path) -> OCRResult:
    """Run OCR engine on image and extract ordered lines with coordinates."""
    path_str = str(image_path)
    engine = get_ocr_engine()

    detected_lines: list[DetectedLine] = []

    if engine is not None:
        try:
            # Check if RapidOCR
            if hasattr(engine, "__call__"):
                result, elapse = engine(path_str)
                if result:
                    for item in result:
                        # item is [bbox, text, score]
                        pts = item[0]
                        txt = item[1].strip()
                        score = float(item[2])
                        all_y = [p[1] for p in pts]
                        all_x = [p[0] for p in pts]
                        center_y = sum(all_y) / len(all_y)
                        center_x = sum(all_x) / len(all_x)
                        top = min(all_y)
                        bottom = max(all_y)

                        detected_lines.append(
                            DetectedLine(
                                text=txt,
                                confidence=score,
                                bbox=[[float(p[0]), float(p[1])] for p in pts],
                                center_y=center_y,
                                center_x=center_x,
                                top=top,
                                bottom=bottom,
                            )
                        )
        except Exception:
            pass

    # Sort lines strictly top-to-bottom (center_y)
    detected_lines.sort(key=lambda l: (l.center_y, l.center_x))
    full_text = "\n".join(l.text for l in detected_lines)

    return OCRResult(lines=detected_lines, full_text=full_text)


def normalize_str(s: str) -> str:
    """Normalize text for robust comparison."""
    # Remove excessive punctuation, multiple whitespaces, lower
    s = s.strip().lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def string_similarity(s1: str, s2: str) -> float:
    """Sequence matcher ratio."""
    return difflib.SequenceMatcher(None, normalize_str(s1), normalize_str(s2)).ratio()


def run_ocr_check(
    spec: PosterSpec,
    image_path: str | Path,
    ocr_result: OCRResult | None = None,
) -> list[CheckResult]:
    """Execute deterministic OCR checks:
    - Missing text
    - Duplicated lines
    - Ordering / role hierarchy violation
    - Spelling differences
    """
    results: list[CheckResult] = []

    if ocr_result is None:
        ocr_result = extract_text_from_image(image_path)

    detected_lines = ocr_result.lines
    normalized_detected = [normalize_str(l.text) for l in detected_lines]

    matched_indices_per_element: dict[str, list[int]] = {}

    for elem in spec.elements:
        norm_expected = normalize_str(elem.text)
        expected_words = norm_expected.split()

        # Find matching detected lines
        matches: list[int] = []
        for idx, norm_det in enumerate(normalized_detected):
            # Exact or substantial substring match or high fuzzy similarity
            if norm_expected == norm_det or norm_expected in norm_det:
                matches.append(idx)
            elif len(norm_det) >= 0.75 * len(norm_expected) and norm_det in norm_expected:
                matches.append(idx)
            elif string_similarity(norm_expected, norm_det) >= 0.82:
                matches.append(idx)
            elif len(expected_words) >= 3:
                det_words = set(norm_det.split())
                overlap_count = sum(1 for w in expected_words if w in det_words)
                if overlap_count >= max(2, len(expected_words) - 1):
                    matches.append(idx)

        # Multi-line wrapping check: check consecutive windows of lines (e.g. 2, 3, or 4 lines)
        if not matches:
            expected_nospaces = norm_expected.replace(" ", "")
            for window_size in (2, 3, 4):
                if matches:
                    break
                for start_idx in range(len(normalized_detected) - window_size + 1):
                    win_lines = normalized_detected[start_idx : start_idx + window_size]
                    win_text = " ".join(win_lines)
                    win_nospaces = win_text.replace(" ", "")
                    
                    if (
                        expected_nospaces in win_nospaces
                        or win_nospaces in expected_nospaces
                        or string_similarity(expected_nospaces, win_nospaces) >= 0.82
                        or string_similarity(norm_expected, win_text) >= 0.80
                    ):
                        matches = list(range(start_idx, start_idx + window_size))
                        break

        # Also check if multi-line text is split across non-adjacent lines (e.g. reading order interrupted)
        if not matches:
            part_indices = []
            for idx, norm_det in enumerate(normalized_detected):
                matching_words = [w for w in expected_words if w in norm_det.split()]
                if len(matching_words) >= 2 or (len(expected_words) <= 2 and len(matching_words) >= 1):
                    part_indices.append(idx)
            if part_indices:
                matches = part_indices

        matched_indices_per_element[elem.id] = sorted(list(set(matches)))

        # 1. Missing text check
        if not matches:
            results.append(
                CheckResult(
                    check_name=f"ocr_text_missing_{elem.id}",
                    severity="blocking",
                    detail=f"Expected text '{elem.text}' (role: {elem.role}) was not found in poster OCR output.",
                    fix_hint=f"Ensure '{elem.text}' is rendered with high legibility and appropriate size.",
                )
            )
        else:
            # 2. Text duplication check
            # A true duplication occurs when multiple lines EACH independently contain
            # or closely resemble the full text, OR have strong mutual overlap.
            is_duplicated = False
            if len(matches) > 1:
                full_matches = []
                for m_idx in matches:
                    m_norm = normalized_detected[m_idx]
                    if string_similarity(m_norm, norm_expected) >= 0.70 or norm_expected in m_norm:
                        full_matches.append(m_idx)
                if len(full_matches) > 1:
                    is_duplicated = True
                else:
                    # Check if any two distinct matching lines are near-duplicates of each other
                    for i in range(len(matches)):
                        for j in range(i + 1, len(matches)):
                            line_i = normalized_detected[matches[i]]
                            line_j = normalized_detected[matches[j]]
                            if len(line_i) >= 6 and len(line_j) >= 6 and string_similarity(line_i, line_j) >= 0.75:
                                is_duplicated = True
                                break

            if is_duplicated:
                results.append(
                    CheckResult(
                        check_name=f"ocr_text_duplicated_{elem.id}",
                        severity="blocking",
                        detail=f"Text line '{elem.text}' is duplicated across the poster.",
                        fix_hint="Remove duplicate rendering of text element.",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        check_name=f"ocr_text_presence_{elem.id}",
                        severity="pass",
                        detail=f"Text '{elem.text}' correctly detected by OCR.",
                        fix_hint=None,
                    )
                )

    # 3. Extra text / Hallucinated text check
    # Any detected line that does not match ANY expected element in the spec or context
    # is hallucinated diffusion text or unwanted clutter.
    all_matched_line_indices = set()
    for indices in matched_indices_per_element.values():
        all_matched_line_indices.update(indices)

    brand_tokens = [
        "apex", "institute", "technology", "tech", "aims", "robotics",
        "summit", "hackathon", "symposium", "annual", "showcase", "show",
        "college", "club", "auditorium", "hall", "ticket", "qr",
        "event", "date", "venue", "location", "scan", "details", "register", "presents"
    ]

    for idx, line in enumerate(detected_lines):
        if idx in all_matched_line_indices:
            continue
        clean_det = normalize_str(line.text)
        # Skip trivial single characters or noise
        if len(clean_det) < 3:
            continue

        # Check against all spec elements
        is_known = False
        for elem in spec.elements:
            norm_e = normalize_str(elem.text)
            if clean_det in norm_e or norm_e in clean_det or string_similarity(clean_det, norm_e) > 0.65:
                is_known = True
                break

        if not is_known:
            # Check against brand and context tokens (substring or word-level fuzzy match)
            det_words = clean_det.split()
            for tok in brand_tokens:
                if tok in clean_det or clean_det in tok:
                    is_known = True
                    break
                if any(string_similarity(w, tok) >= 0.70 for w in det_words):
                    is_known = True
                    break

        if is_known:
            continue

        results.append(
            CheckResult(
                check_name=f"ocr_extra_text_line_{idx}",
                severity="blocking",
                detail=f"Unauthorized/hallucinated extra text '{line.text}' detected on poster by OCR.",
                fix_hint="Regenerate background artwork with zero text, or remove unwanted DOM text.",
            )
        )

    # 4. Hierarchy and Order Check
    # Verify that roles follow expected vertical visual flow
    # e.g. headline should appear before (above) subheadline, date/venue after subheadline
    role_order_priority = {
        "label": 0,
        "headline": 1,
        "subheadline": 2,
        "date": 3,
        "venue": 3,
        "body": 4,
        "footer": 5,
    }

    # Find headlines and subheadlines in spec
    headline_elems = [e for e in spec.elements if e.role == "headline"]
    subhead_elems = [e for e in spec.elements if e.role == "subheadline"]

    for h_elem in headline_elems:
        h_indices = matched_indices_per_element.get(h_elem.id, [])
        if not h_indices:
            continue
        h_pos = min(h_indices)

        for s_elem in subhead_elems:
            s_indices = matched_indices_per_element.get(s_elem.id, [])
            if not s_indices:
                continue
            s_pos = min(s_indices)

            # If subheadline is physically placed above headline or in the middle of headline lines
            if s_pos < h_pos:
                results.append(
                    CheckResult(
                        check_name=f"ocr_order_violation_{s_elem.id}_{h_elem.id}",
                        severity="blocking",
                        detail=(
                            f"Reading order violation: subheadline '{s_elem.text}' (line {s_pos}) "
                            f"appears before headline '{h_elem.text}' (line {h_pos})."
                        ),
                        fix_hint="Move subheadline below headline in the visual hierarchy.",
                    )
                )
            elif len(h_indices) > 1 and min(h_indices) < s_pos < max(h_indices):
                results.append(
                    CheckResult(
                        check_name=f"ocr_order_interrupted_{s_elem.id}_{h_elem.id}",
                        severity="blocking",
                        detail=(
                            f"Reading order violation: subheadline '{s_elem.text}' is inserted "
                            f"in the middle of headline '{h_elem.text}' lines."
                        ),
                        fix_hint="Keep headline lines contiguous; place subheadline underneath.",
                    )
                )

    return results
