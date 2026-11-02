"""House Style System loader and resolver (Stage 2b).

Resolves brand data per school, canvas dimensions from brief (default 1080x1920 9:16 story),
genre taxonomy policies, and structural row allowances.
"""
import re
from pathlib import Path
from typing import Any, Optional
import yaml

from poster_agent.ingestion.extractor import ExtractedBrief

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_house_style(config_path: Optional[Path | str] = None) -> dict[str, Any]:
    """Load house style system config."""
    cfg_p = Path(config_path) if config_path else (PROJECT_ROOT / "configs" / "house_style.yaml")
    if cfg_p.exists():
        with open(cfg_p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def resolve_canvas_dimensions(
    brief_or_format: str | ExtractedBrief,
    house_style: Optional[dict[str, Any]] = None,
) -> tuple[float, float]:
    """Resolve canvas dimensions from brief 'format' string or ExtractedBrief.
    
    Default when absent: 1080x1920 (9:16 story).
    """
    if house_style is None:
        house_style = load_house_style()

    format_str = ""
    if isinstance(brief_or_format, ExtractedBrief):
        format_str = brief_or_format.get_text("format")
    elif isinstance(brief_or_format, str):
        format_str = brief_or_format

    format_norm = format_str.lower().strip()
    formats_cfg = house_style.get("formats", {
        "story": [1080, 1920],
        "square": [1080, 1080],
        "fourfive": [1080, 1350],
        "A3": [842, 1191],
        "A4": [595, 842],
    })

    if not format_norm:
        # Default when absent: 1080x1920 (9:16 story)
        dims = formats_cfg.get("story", [1080, 1920])
        return float(dims[0]), float(dims[1])

    # Check named formats
    if "a3" in format_norm:
        dims = formats_cfg.get("A3", [842, 1191])
        return float(dims[0]), float(dims[1])
    if "a4" in format_norm:
        dims = formats_cfg.get("A4", [595, 842])
        return float(dims[0]), float(dims[1])
    if "square" in format_norm or "1:1" in format_norm:
        dims = formats_cfg.get("square", [1080, 1080])
        return float(dims[0]), float(dims[1])
    if "4:5" in format_norm or "fourfive" in format_norm or "1080x1350" in format_norm or "1080 x 1350" in format_norm:
        dims = formats_cfg.get("fourfive", [1080, 1350])
        return float(dims[0]), float(dims[1])
    if "story" in format_norm or "9:16" in format_norm or "1080x1920" in format_norm or "1080 x 1920" in format_norm:
        dims = formats_cfg.get("story", [1080, 1920])
        return float(dims[0]), float(dims[1])

    # Check explicit WxH dimensions
    m_dim = re.search(r"(\d+)\s*[xX*×]\s*(\d+)", format_norm)
    if m_dim:
        return float(m_dim.group(1)), float(m_dim.group(2))

    # Fallback to 1080x1920 (9:16 story)
    dims = formats_cfg.get("story", [1080, 1920])
    return float(dims[0]), float(dims[1])


def resolve_school(
    brief: ExtractedBrief,
    house_style: Optional[dict[str, Any]] = None,
) -> tuple[str, dict[str, Any]]:
    """Resolve school brand data based on brief text matches."""
    if house_style is None:
        house_style = load_house_style()

    schools = house_style.get("schools", {})
    corpus = " ".join([
        brief.get_text("organizer"),
        brief.get_text("partner"),
        brief.get_text("title"),
        brief.get_text("subtitle"),
    ]).upper()

    # Prioritize specific sub-schools before general KCT/KI
    if "KCTBS" in corpus or "BUSINESS STUDIES" in corpus:
        return "KCTBS", schools.get("KCTBS", {})
    if "KCLAS" in corpus or "LIBERAL ARTS" in corpus:
        return "KCLAS", schools.get("KCLAS", {})
    if "KIA" in corpus or "AGRICULTURE" in corpus:
        return "KIA", schools.get("KIA", {})
    if "KCT" in corpus or "TECHNOLOGY" in corpus:
        return "KCT", schools.get("KCT", {})
    if "KUMARAGURU" in corpus or "INSTITUTIONS" in corpus:
        return "KI", schools.get("KI", {})

    # Default anchor school: KCT
    return "KCT", schools.get("KCT", {})


def resolve_genre(
    brief: ExtractedBrief,
    house_style: Optional[dict[str, Any]] = None,
) -> tuple[str, dict[str, Any]]:
    """Map brief keywords to corpus genre taxonomy and structural policies."""
    if house_style is None:
        house_style = load_house_style()

    genres = house_style.get("genres", {})
    policies = house_style.get("structural_policies", {})

    corpus = " ".join([
        brief.get_text("section"),
        brief.get_text("title"),
        brief.get_text("tagline"),
        brief.get_text("subtitle"),
        brief.get_text("events"),
        brief.get_text("mood"),
    ]).lower()

    # Score each genre by keyword matches; prioritize specific genres over generic 'event'
    best_genre = None
    best_score = 0
    for g_name, g_info in genres.items():
        kws = g_info.get("keywords", [])
        match_count = sum(1 for k in kws if re.search(rf"\b{re.escape(k)}\b", corpus))
        if match_count > 0:
            weight = 1 if g_name == "event" else 2
            score = match_count * weight
            if score > best_score:
                best_score = score
                best_genre = g_name

    matched_genre = best_genre if best_genre is not None else "general"

    policy_name = genres.get(matched_genre, {}).get("policy", "institutional")
    policy_dict = policies.get(policy_name, {
        "allow_cards": True,
        "allow_pills": True,
        "allow_banner_tab": True,
        "allow_footer_bar": True,
        "allow_qr": True,
    })

    return matched_genre, policy_dict


def select_house_exemplars(
    genre: str,
    format_name: Optional[str] = None,
    catalog_path: Optional[Path | str] = None,
    max_exemplars: int = 3,
    max_chars: int = 2000,
) -> list[dict[str, str]]:
    """Select up to max_exemplars from poster_catalog.csv matching genre and format.

    Deterministic selection:
    1. Score: 2 * (genre keyword match) + 1 * (format keyword match)
    2. Tie-break: alphabetical by filename
    3. Return compact dicts with 'file', 'layout', 'typography', 'palette', 'standout'
    4. If no matches, returns empty list [].
    """
    csv_p = Path(catalog_path) if catalog_path else (PROJECT_ROOT / "Examples" / "extracted" / "Posters" / "poster_catalog.csv")
    if not csv_p.exists():
        return []

    import csv
    with open(csv_p, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    house_style = load_house_style()
    genre_kws = house_style.get("genres", {}).get(genre, {}).get("keywords", [genre])
    fmt_norm = (format_name or "").lower().strip()

    scored = []
    for r in rows:
        type_corpus = (r.get("type", "") + " " + r.get("details_shown", "")).lower()
        genre_score = 0
        if any(kw in type_corpus for kw in genre_kws):
            genre_score = 2
        elif genre.lower() in type_corpus:
            genre_score = 2

        if genre_score == 0:
            continue

        format_score = 0
        r_fmt = r.get("format", "").lower()
        if fmt_norm:
            if fmt_norm in r_fmt:
                format_score = 1
            elif fmt_norm in ("story", "9:16", "1080x1920") and ("1080x1920" in r_fmt or "story" in r_fmt):
                format_score = 1

        total_score = genre_score + format_score
        filename = r.get("file", "")
        scored.append((total_score, filename.lower(), r))

    if not scored:
        return []

    scored.sort(key=lambda x: (-x[0], x[1]))
    selected = []
    for _, _, r in scored[:max_exemplars]:
        selected.append({
            "file": r.get("file", ""),
            "layout": r.get("layout", "").strip(),
            "typography": r.get("typography", "").strip(),
            "palette": r.get("palette", "").strip(),
            "standout": r.get("standout", "").strip(),
        })

    return selected


def format_exemplars_for_prompt(exemplars: list[dict[str, str]], max_chars: int = 2000) -> str:
    """Format selected exemplars into a prompt block, respecting token budget (~500 tokens)."""
    if not exemplars:
        return ""

    lines = [
        "HOUSE STYLE REFERENCES (Reference only — facts still come only from the brief):"
    ]
    for i, ex in enumerate(exemplars, 1):
        lines.append(f"- Exemplar {i} ({ex.get('file', '')}):")
        if ex.get("layout"):
            lines.append(f"  • Layout: {ex['layout']}")
        if ex.get("typography"):
            lines.append(f"  • Typography: {ex['typography']}")
        if ex.get("palette"):
            lines.append(f"  • Palette: {ex['palette']}")
        if ex.get("standout"):
            lines.append(f"  • Standout: {ex['standout']}")

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars].rsplit("\n", 1)[0]
    return result
