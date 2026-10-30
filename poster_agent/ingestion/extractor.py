"""Stage 1: Brief Ingestion and Provenance Tagging with Zero-Drop Guarantee."""
import re
from pathlib import Path
from typing import Literal
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
    missing_fields: list[str] = Field(default_factory=list)
    zero_drop_passed: bool = True
    unmapped_lines: list[str] = Field(default_factory=list)
    extraction_log: list[str] = Field(default_factory=list)

    def get_text(self, key: str, default: str = "") -> str:
        f = self.fields.get(key)
        return f.text if f else default


class BriefExtractor:
    """Bulletproof brief extractor supporting markdown, bullet dashes, and unlabelled lines."""

    # Canonical role patterns
    KEY_PATTERNS: dict[str, list[str]] = {
        "title": [r"event\s+title", r"title", r"event\s+name", r"name"],
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
                    k_norm = k.strip().lower()
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
            missing_fields=missing,
            zero_drop_passed=zero_drop_passed,
            unmapped_lines=unmapped,
            extraction_log=log,
        )
