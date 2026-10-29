"""Verbatim string verifier and missing field guard."""
from pydantic import BaseModel
from poster_agent.spec.models import PosterSpec, TextElement
from poster_agent.context.loader import ContextBundle


class VerbatimViolationError(Exception):
    """Raised when planner generates strings not present verbatim in source inputs."""
    def __init__(self, violations: list[str]):
        super().__init__(f"Verbatim text violation: strings not found in source: {violations}")
        self.violations = violations


class MissingFieldsError(Exception):
    """Raised when critical required event details are missing from the brief."""
    def __init__(self, missing_fields: list[str]):
        super().__init__(f"Missing required fields in brief: {missing_fields}")
        self.missing_fields = missing_fields


def verify_verbatim_strings(
    spec: PosterSpec,
    brief_text: str,
    context: ContextBundle,
) -> list[str]:
    """Verify that every text element appears verbatim in its declared source (brief or context).
    Returns list of offending element ids/texts if any.
    """
    violations: list[str] = []

    for elem in spec.elements:
        clean_text = elem.text.strip()
        if not clean_text:
            continue

        if elem.source == "brief":
            # Must appear verbatim in user requirements brief
            if clean_text not in brief_text:
                # Also check case-insensitive match for helpful error message
                if clean_text.lower() in brief_text.lower():
                    # Case differs
                    violations.append(
                        f"Element '{elem.id}' casing mismatch: '{elem.text}' (expected exact match in brief)"
                    )
                else:
                    violations.append(
                        f"Element '{elem.id}' invented or rewritten text: '{elem.text}' not in brief"
                    )
        elif elem.source == "context":
            # Must appear verbatim in context.md
            if not context.contains_verbatim(clean_text):
                violations.append(
                    f"Element '{elem.id}' context text: '{elem.text}' not in context.md"
                )

    return violations


def verify_spec(
    spec: PosterSpec,
    brief_text: str,
    context: ContextBundle,
) -> None:
    """Full verification: raises MissingFieldsError if missing_fields is non-empty,
    and raises VerbatimViolationError if any verbatim check fails.
    """
    if spec.missing_fields:
        raise MissingFieldsError(spec.missing_fields)

    violations = verify_verbatim_strings(spec=spec, brief_text=brief_text, context=context)
    if violations:
        raise VerbatimViolationError(violations)

