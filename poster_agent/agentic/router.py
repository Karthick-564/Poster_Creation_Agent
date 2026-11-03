"""Stage 6: Failure Router.

Routes defects discovered during Stage 5 review back to the stage that can fix them:
- Overlap / contrast / margin / hierarchy / spacing -> S4 Designer Loop
- Baked or garbled text in background / busy background -> S3 Regeneration (new seed)
- Hero missing / too dark / cropped -> S3 Regeneration or S4 adjustment
- Missing or wrong logo / mandatory locked item -> Halt honestly (cannot generate logos)
- Missing brief details -> S1 clarifying question
- Cycle limit: Maximum 3 cycles per run before halting honestly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RerouteAction:
    cycle: int
    failing_check: str
    target_stage: str
    action: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "failing_check": self.failing_check,
            "target_stage": self.target_stage,
            "action": self.action,
            "details": self.details,
        }


@dataclass
class RouterDecision:
    should_reroute: bool
    target_stage: str  # "S1", "S2", "S3", "S4", "HALT", "NONE"
    reroute_action: Optional[RerouteAction] = None
    halt_reason: Optional[str] = None


class Router:
    """Manages failure triage and stage redirection."""

    MAX_CYCLES = 3

    def route(
        self,
        cycle: int,
        gate_results: dict[str, Any],
        ocr_results: dict[str, Any],
        critic_results: Optional[dict[str, Any]] = None,
        locked_status: Optional[dict[str, Any]] = None,
    ) -> RouterDecision:
        """Analyze review findings and decide next target stage."""
        # 1. Check cycle limits
        if cycle >= self.MAX_CYCLES:
            return RouterDecision(
                should_reroute=False,
                target_stage="HALT",
                halt_reason=f"Exceeded maximum review cycles ({self.MAX_CYCLES}) without full convergence.",
                reroute_action=RerouteAction(
                    cycle=cycle,
                    failing_check="cycle_limit",
                    target_stage="HALT",
                    action=f"Halt honestly: defects remain after {self.MAX_CYCLES} cycles.",
                ),
            )

        # 2. Check for missing or broken institutional logo (Strict Rule: never generate logos)
        failures = gate_results.get("failures", [])
        for f in failures:
            target = str(f.get("target", ""))
            if "logo" in target or "locked_header" in target:
                return RouterDecision(
                    should_reroute=False,
                    target_stage="HALT",
                    halt_reason="Institutional logo missing or obstructed. Halting honestly (logos cannot be diffusion-generated).",
                    reroute_action=RerouteAction(
                        cycle=cycle,
                        failing_check="institutional_logo",
                        target_stage="HALT",
                        action="Halt: logo placement defect.",
                        details=f,
                    ),
                )

        # 3. Check OCR on background layer (baked pseudo-text / unmapped letters)
        if not ocr_results.get("passed", True):
            unmapped = ocr_results.get("bg_unmapped_tokens", [])
            return RouterDecision(
                should_reroute=True,
                target_stage="S3",
                reroute_action=RerouteAction(
                    cycle=cycle,
                    failing_check="background_ocr",
                    target_stage="S3",
                    action="Regenerate background layer with a fresh seed and prompt without text-like structures.",
                    details={"unmapped_tokens": unmapped, "ocr_failures": ocr_results.get("failures", [])},
                ),
            )

        # 4. Check Critic Checklist for S3 generation failures
        if critic_results:
            critic_items = critic_results.get("items", {})
            for item_name, item_data in critic_items.items():
                if not item_data.get("passed", True) and item_data.get("target_stage") == "S3":
                    return RouterDecision(
                        should_reroute=True,
                        target_stage="S3",
                        reroute_action=RerouteAction(
                            cycle=cycle,
                            failing_check=item_name,
                            target_stage="S3",
                            action=f"Regenerate asset layer: {item_data.get('evidence', '')}",
                            details=item_data,
                        ),
                    )

        # 5. Check Physical Deterministic Gate Failures (all route to S4 Designer)
        if not gate_results.get("passed", False):
            failing_kinds = [f.get("kind") for f in failures]
            first_fail = failures[0] if failures else {}
            return RouterDecision(
                should_reroute=True,
                target_stage="S4",
                reroute_action=RerouteAction(
                    cycle=cycle,
                    failing_check=str(failing_kinds[0]) if failing_kinds else "deterministic_gate",
                    target_stage="S4",
                    action=f"Adjust layout/typography to resolve {len(failures)} gate failure(s): {', '.join(failing_kinds)}",
                    details={"gate_failures": failures},
                ),
            )

        # 6. Check Critic Checklist for S4 layout failures
        if critic_results:
            critic_items = critic_results.get("items", {})
            for item_name, item_data in critic_items.items():
                if not item_data.get("passed", True) and item_data.get("target_stage") == "S4":
                    return RouterDecision(
                        should_reroute=True,
                        target_stage="S4",
                        reroute_action=RerouteAction(
                            cycle=cycle,
                            failing_check=item_name,
                            target_stage="S4",
                            action=f"Refine composition: {item_data.get('evidence', '')}",
                            details=item_data,
                        ),
                    )

        # 7. Everything passed cleanly
        return RouterDecision(
            should_reroute=False,
            target_stage="NONE",
            reroute_action=None,
        )

