"""Stage 1: Intake & Verbatim Ingestion.

Extracts brief fields verbatim. Required details are flexible: generates
at most ONE concise clarifying question if details needed for a sensible
poster are missing (e.g. event title, date/time, or venue). Never invents details.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from poster_agent.ingestion.extractor import BriefExtractor, ExtractedBrief


@dataclass
class IntakeResult:
    brief: ExtractedBrief
    raw_text: str
    fields: dict[str, str] = field(default_factory=dict)
    missing_critical: list[str] = field(default_factory=list)
    clarifying_question: Optional[str] = None
    is_valid: bool = True

    def summary(self) -> dict[str, Any]:
        return {
            "title": self.fields.get("title", ""),
            "field_count": len(self.fields),
            "missing_critical": self.missing_critical,
            "clarifying_question": self.clarifying_question,
            "is_valid": self.is_valid,
        }


class IntakeStage:
    """Extracts brief fields verbatim and checks for essential event viability."""

    def __init__(self):
        self.extractor = BriefExtractor()

    def process(self, brief_input: str | Path) -> IntakeResult:
        """Process raw brief text or file path into an IntakeResult."""
        if isinstance(brief_input, Path) or (isinstance(brief_input, str) and "\n" not in brief_input and Path(brief_input).exists()):
            raw_text = Path(brief_input).read_text(encoding="utf-8")
        else:
            raw_text = str(brief_input)

        brief = self.extractor.extract(raw_text)
        fields = {k: f.text for k, f in brief.fields.items() if f.text}

        # Flexible viability check:
        # A sensible poster must at minimum have an event name/title.
        # It also strongly needs date/time or venue.
        missing = []
        if not fields.get("title"):
            missing.append("title (event name)")

        date_val = fields.get("date") or fields.get("time")
        venue_val = fields.get("venue")
        if not date_val and not venue_val:
            missing.append("date/time or venue")

        question = None
        is_valid = True
        if missing:
            is_valid = False
            if "title (event name)" in missing:
                question = "What is the official title or name of this event?"
            elif "date/time or venue" in missing:
                question = "When (date/time) and where (venue) will this event take place?"

        return IntakeResult(
            brief=brief,
            raw_text=raw_text,
            fields=fields,
            missing_critical=missing,
            clarifying_question=question,
            is_valid=is_valid,
        )

