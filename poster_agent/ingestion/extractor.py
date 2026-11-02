"""Stage 1: Brief Ingestion and Provenance Tagging with Zero-Drop Guarantee."""
import re
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

ProvenanceType = Literal["brief", "context", "decorative"]


class VerbatimField(BaseModel):
    """A verbatim text string extracted from the brief or context with provenance."""
    model_config = ConfigDict(extra="forbid")
    key: str
    text: str
    source: ProvenanceType
    raw_source_line: str = ""


class ExtractedBrief(BaseModel):
    """Complete, self-contained extraction from the user brief and brand context."""
    model_config = ConfigDict(extra="forbid")
    fields: dict[str, VerbatimField]
    asset_references: dict[str, str] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    zero_drop_passed: bool = True
    unmapped_lines: list[str] = Field(default_factory=list)
    extraction_log: list[str] = Field(default_factory=list)

    def get_text(self, key: str, default: str = "") -> str:
        f = self.fields.get(key)
        return f.text if f else default

    def get_asset_ref(self, key: str, default: str = "") -> str:
        return self.asset_references.get(key, default)

    def validate_assets(self, project_root: Optional[Path] = None) -> list[str]:
        """Check existence of local file paths in asset_references. Return list of missing path errors."""
        if project_root is None:
            project_root = Path.cwd()
        errors: list[str] = []
        file_keys = ["hero_path", "background_path", "logo_path"]
        for k, v in self.asset_references.items():
            if k in file_keys or any(v.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".svg"]):
                # Split comma separated if multiple (e.g. logos)
                paths = [p.strip() for p in v.split(",") if p.strip()]
                for p_str in paths:
                    p = Path(p_str)
                    if not p.is_absolute():
                        p = project_root / p
                    if not p.exists():
                        errors.append(f"Supplied asset not found: '{p_str}' (field '{k}')")
        return errors

    def get_positions(self) -> list[dict]:
        """Extract structured list of positions if present."""
        positions = []
        pos_idx = 1
        while True:
            title_field = self.fields.get(f"position_{pos_idx}")
            if not title_field:
                break
            tagline_field = self.fields.get(f"position_{pos_idx}_tagline")
            points = []
            pt_idx = 1
            while True:
                pt_field = self.fields.get(f"position_{pos_idx}_point_{pt_idx}")
                if not pt_field:
                    break
                points.append(pt_field.text)
                pt_idx += 1
            positions.append({
                "index": pos_idx,
                "title": title_field.text,
                "tagline": tagline_field.text if tagline_field else "",
                "points": points,
            })
            pos_idx += 1
        return positions


class BriefExtractor:
    """Bulletproof brief extractor supporting markdown, bullet dashes, and unlabelled lines."""

    ASSET_PATTERNS: dict[str, list[str]] = {
        "hero_path": [r"hero[\s_]*path", r"hero[\s_]*image", r"hero[\s_]*asset"],
        "background_path": [r"background[\s_]*path", r"bg[\s_]*path", r"background[\s_]*image", r"bg[\s_]*image"],
        "qr_link": [r"qr[\s_]*(?:link|code|url)?", r"form[\s_]*link"],
        "logo_path": [r"logo[\s_]*path", r"logo[\s_]*image"],
        "logos": [r"logos?", r"brand[\s_]*assets?"],
    }

    # Canonical role patterns
    KEY_PATTERNS: dict[str, list[str]] = {
        "title": [r"event\s+title", r"title", r"event\s+name", r"name", r"event"],
        "eyebrow": [r"eyebrow", r"kicker", r"header\s+label"],
        "tagline": [r"tagline", r"theme", r"motto"],
        "subtitle": [r"subtitle", r"sub-title", r"fest\s+type"],
        "date": [r"date", r"when", r"dates", r"timing\s+dates"],
        "time": [r"time", r"schedule", r"timings", r"hours"],
        "venue": [r"venue", r"location", r"where", r"place", r"auditorium"],
        "events": [r"events", r"tracks", r"highlights", r"competitions", r"categories"],
        "prize": [r"prize\s*(?:pool|line)?", r"prizes", r"awards", r"cash\s+prize"],
        "entry": [r"entry", r"tickets", r"fees", r"registration\s+fee"],
        "team_size": [r"team\s*size", r"team", r"teams"],
        "cta": [r"cta", r"register", r"action", r"link", r"registration\s+link", r"join"],
        "contact": [r"contact", r"email", r"queries", r"phone"],
        "hashtag": [r"hashtag", r"tag"],
        "organizer": [r"organizer", r"presented\s*by", r"organized\s*by", r"club", r"host"],
        "partner": [r"partner", r"institution", r"partner\s*institution", r"college", r"powered\s*by"],
        "section": [r"section", r"heading", r"open\s+positions"],
        "deadline_label": [r"deadline\s+label", r"time\s+to\s+fill\s+label"],
        "deadline": [r"deadline", r"apply\s+by", r"time\s+to\s+fill"],
        "deadline_note": [r"deadline\s+note", r"eligibility\s+note"],
        "closing": [r"closing\s*(?:line)?", r"footer\s*(?:line)?", r"signoff", r"closing"],
        "dress_code": [r"dress\s*code", r"attire"],
        "venue_tamil": [r"venue\s*\(tamil\)", r"venue_tamil", r"location\s*\(tamil\)"],
        "blurb": [r"blurb", r"description", r"about", r"story"],
        "palette": [r"palette", r"colors", r"color\s+palette", r"hex\s+palette"],
        "palette_use": [r"palette\s*use", r"color\s*rules?"],
        "mood": [r"mood", r"aesthetic", r"visual\s+style", r"style"],
        "art": [r"art", r"artwork", r"illustration"],
        "format": [r"format", r"dimensions", r"aspect\s+ratio"],
    }

    def __init__(self, required_keys: list[str] | None = None):
        self.required_keys = required_keys or ["title", "date", "venue"]

    def extract(self, raw_brief: str, context_text: str = "") -> ExtractedBrief:
        """Parse raw brief text into structured verbatim fields with zero-drop audit."""
        clean = (
            raw_brief.replace("\\n", "\n")
            .replace("`n", "\n")
            .replace("\r", "")
            .strip()
        )

        extracted: dict[str, VerbatimField] = {}
        asset_refs: dict[str, str] = {}
        unmapped: list[str] = []
        log: list[str] = []

        lines = [line.strip() for line in clean.splitlines() if line.strip()]

        for line in lines:
            # Strip leading bullet dashes, asterisks, numbers
            stripped = re.sub(r"^[-*•\d\.\s]+", "", line).strip()
            if not stripped:
                continue

            matched = False
            # Check for Key: Value pattern
            if ":" in stripped:
                key_part, val_part = stripped.split(":", 1)
                key_norm = key_part.strip().lower()
                val_clean = val_part.strip()

                if val_clean:
                    for asset_key, aliases in self.ASSET_PATTERNS.items():
                        if any(re.fullmatch(alias, key_norm) or key_norm == alias for alias in aliases):
                            asset_refs[asset_key] = val_clean
                            log.append(f"Mapped asset reference '{asset_key}': '{val_clean}' (from '{line}')")
                            matched = True
                            break

                    if not matched:
                        for canonical_key, aliases in self.KEY_PATTERNS.items():
                            if any(re.fullmatch(alias, key_norm) or key_norm == alias for alias in aliases):
                                extracted[canonical_key] = VerbatimField(
                                    key=canonical_key,
                                    text=val_clean,
                                    source="brief",
                                    raw_source_line=line,
                                )
                                log.append(f"Mapped brief field '{canonical_key}': '{val_clean}' (from '{line}')")
                                matched = True
                                break

                    if not matched:
                        m_pos = re.match(r"^position\s*(\d+)(?:\s*(tagline|point\s*\d+|role|desc.*))?$", key_norm)
                        if m_pos:
                            p_idx = m_pos.group(1)
                            sub = m_pos.group(2)
                            if not sub:
                                p_key = f"position_{p_idx}"
                            elif "tagline" in sub:
                                p_key = f"position_{p_idx}_tagline"
                            else:
                                pt_m = re.search(r"\d+", sub)
                                p_key = f"position_{p_idx}_point_{pt_m.group(0)}" if pt_m else f"position_{p_idx}_{re.sub(r'[^a-z0-9]+', '_', sub).strip('_')}"
                            extracted[p_key] = VerbatimField(
                                key=p_key,
                                text=val_clean,
                                source="brief",
                                raw_source_line=line,
                            )
                            log.append(f"Mapped position field '{p_key}': '{val_clean}' (from '{line}')")
                            matched = True
                        else:
                            slug = re.sub(r"[^a-z0-9]+", "_", key_norm).strip("_")
                            if slug:
                                extracted[slug] = VerbatimField(
                                    key=slug,
                                    text=val_clean,
                                    source="brief",
                                    raw_source_line=line,
                                )
                                log.append(f"Mapped structured field '{slug}': '{val_clean}' (from '{line}')")
                                matched = True

            if not matched:
                # Check if it's an unlabelled title (often the first line or capitalized header)
                if "title" not in extracted and not any(k in stripped.lower() for k in ["http", "www", "@", "presented"]):
                    extracted["title"] = VerbatimField(
                        key="title",
                        text=stripped,
                        source="brief",
                        raw_source_line=line,
                    )
                    log.append(f"Heuristically mapped unlabelled line to 'title': '{stripped}'")
                    matched = True
                else:
                    unmapped.append(line)
                    log.append(f"Unmapped raw line preserved: '{line}'")

        # Ingest context.md if available
        if context_text:
            for line in context_text.splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    k_norm = re.sub(r"[\*\_\-\#]+", "", k).strip().lower()
                    v_clean = v.strip()
                    if v_clean:
                        for canonical_key, aliases in self.KEY_PATTERNS.items():
                            if canonical_key not in extracted and any(re.fullmatch(alias, k_norm) for alias in aliases):
                                extracted[canonical_key] = VerbatimField(
                                    key=canonical_key,
                                    text=v_clean,
                                    source="context",
                                    raw_source_line=line,
                                )
                                log.append(f"Ingested institutional context '{canonical_key}': '{v_clean}'")

        # Zero-Drop Guarantee check: verify required keys
        missing: list[str] = []
        for req in self.required_keys:
            if req not in extracted:
                missing.append(req)

        zero_drop_passed = len(missing) == 0

        return ExtractedBrief(
            fields=extracted,
            asset_references=asset_refs,
            missing_fields=missing,
            zero_drop_passed=zero_drop_passed,
            unmapped_lines=unmapped,
            extraction_log=log,
        )

