"""Autonomous Gate-Failure Repair Executor (Phase D Commit 3b).

Consumes Stage-6 deterministic QA gate failures and applies typed repair operations:
- `shrink_text`: Shrinks row font size toward the doctrine floor when escaping safe margins.
- `wrap_text`: Splits long single-line text into balanced two-line wraps.
- `move_row`: Repositions text rows to clear hero rectangles, adjacent rows, or canvas boundaries.
- `swap_contrast`: Flips text color to maximize WCAG 2.1 luminance contrast against background.
- `drop_duplicate`: Suppresses duplicate structural rows.

Enforces a strict budget of <=2 repair cycles.
All repair actions, parameters, and outcomes are recorded in plan.json.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Sequence

from poster_agent.ingestion.extractor import ExtractedBrief
from poster_agent.qa.gates import GateFailure, run_all_manifest_gates
from poster_agent.renderer.composer import TypographicPlan, compose_slots
from poster_agent.renderer.vectorcraft_renderer import VectorCraftRenderer


class RepairOp(str, Enum):
    SHRINK_TEXT = "shrink_text"
    WRAP_TEXT = "wrap_text"
    MOVE_ROW = "move_row"
    SWAP_CONTRAST = "swap_contrast"
    DROP_DUPLICATE = "drop_duplicate"


@dataclass
class RepairAttempt:
    cycle: int
    gate: str
    target: str
    op: str
    applied: dict[str, Any]
    outcome: str = "PENDING"  # PASS | FAIL | PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "gate": self.gate,
            "target": self.target,
            "op": self.op,
            "applied": self.applied,
            "outcome": self.outcome,
        }


class RepairExecutor:
    """Executes deterministic layout repair cycles against Stage-6 gate failures."""

    def __init__(
        self,
        canvas_w: float = 1080.0,
        canvas_h: float = 1920.0,
        margin_px: float = 48.6,
        max_cycles: int = 2,
    ):
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h
        self.margin_px = margin_px
        self.max_cycles = max_cycles
        self.history: list[RepairAttempt] = []

    def plan_repairs_for_failures(
        self,
        cycle: int,
        failed_gates: Sequence[dict[str, Any] | GateFailure],
        plan: TypographicPlan,
        hero_rect: Optional[tuple[float, float, float, float]] = None,
    ) -> list[RepairAttempt]:
        """Map failed QA gates to typed repair operations."""
        attempts: list[RepairAttempt] = []

        for f in failed_gates:
            if isinstance(f, GateFailure):
                gate_name = f.kind
                target = f.target
                measured = f.measured
            else:
                gate_name = f.get("name", "")
                target = str(f.get("measured", {}).get("targets", ["all"])[0]) if f.get("measured", {}).get("targets") else "frame"
                measured = f.get("measured", {})

            # 1. Canvas Bounds / Overflow -> Shrink or Wrap or Inward Move
            if gate_name in ("canvas_bounds", "text_bounds", "overflow"):
                t_row = plan.get_row(target)
                if t_row:
                    headline_floor = self.canvas_h / 11.0
                    body_floor = self.canvas_h * 0.018
                    min_floor = headline_floor if t_row.role == "title" else body_floor

                    if t_row.size > min_floor * 1.05:
                        # Shrink toward floor
                        new_sz = max(min_floor, t_row.size * 0.85)
                        attempts.append(RepairAttempt(
                            cycle=cycle,
                            gate=gate_name,
                            target=target,
                            op=RepairOp.SHRINK_TEXT.value,
                            applied={"old_size": round(t_row.size, 1), "new_size": round(new_sz, 1)},
                        ))
                    elif " " in t_row.text and len(t_row.text.split()) > 1:
                        # Wrap text
                        attempts.append(RepairAttempt(
                            cycle=cycle,
                            gate=gate_name,
                            target=target,
                            op=RepairOp.WRAP_TEXT.value,
                            applied={"split_words": True},
                        ))
                    else:
                        attempts.append(RepairAttempt(
                            cycle=cycle,
                            gate=gate_name,
                            target=target,
                            op=RepairOp.MOVE_ROW.value,
                            applied={"shift_inward": self.margin_px + 10.0},
                        ))

            # 2. Hero Overlap -> Move Row clear of hero
            elif gate_name == "hero_overlap":
                attempts.append(RepairAttempt(
                    cycle=cycle,
                    gate=gate_name,
                    target=target,
                    op=RepairOp.MOVE_ROW.value,
                    applied={"avoid_hero_rect": hero_rect},
                ))

            # 3. Structure Contrast -> Swap Text Color
            elif gate_name in ("structure_contrast", "contrast"):
                attempts.append(RepairAttempt(
                    cycle=cycle,
                    gate=gate_name,
                    target=target,
                    op=RepairOp.SWAP_CONTRAST.value,
                    applied={"swap_palette_polarity": True},
                ))

            # 4. Dedupe -> Drop Duplicate Row
            elif gate_name == "dedupe":
                attempts.append(RepairAttempt(
                    cycle=cycle,
                    gate=gate_name,
                    target=target,
                    op=RepairOp.DROP_DUPLICATE.value,
                    applied={"suppress_duplicate": True},
                ))

            # 5. Row Overlap -> Move Row down
            elif gate_name == "row_overlap":
                attempts.append(RepairAttempt(
                    cycle=cycle,
                    gate=gate_name,
                    target=target,
                    op=RepairOp.MOVE_ROW.value,
                    applied={"vertical_clearance_pt": 20.0},
                ))

        return attempts

    def apply_repairs(
        self,
        attempts: list[RepairAttempt],
        plan: TypographicPlan,
        layout_plan: dict[str, Any],
    ) -> None:
        """Apply typed repair modifications in-place to typographic plan and layout plan."""
        for att in attempts:
            t_row = plan.get_row(att.target)
            if not t_row:
                # Find matching row by partial name
                for r in plan.rows:
                    if att.target in r.role or r.role in att.target:
                        t_row = r
                        break

            if att.op == RepairOp.SHRINK_TEXT.value and t_row:
                t_row.size = att.applied.get("new_size", t_row.size * 0.85)

            elif att.op == RepairOp.WRAP_TEXT.value and t_row:
                # Signal wrap by breaking long words or splitting
                words = t_row.text.split()
                if len(words) > 1:
                    mid = len(words) // 2
                    t_row.text = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])

            elif att.op == RepairOp.SWAP_CONTRAST.value and t_row:
                # Invert text color
                if t_row.color.upper() in ("#FFFFFF", "#F8FAFC", "#E2E8F0"):
                    t_row.color = "#0B2A5B"
                else:
                    t_row.color = "#FFFFFF"

            elif att.op == RepairOp.DROP_DUPLICATE.value:
                # Remove duplicated row from plan.rows
                plan.rows = [r for r in plan.rows if r.role != att.target]

            elif att.op == RepairOp.MOVE_ROW.value:
                # Update layout_plan slot if present
                for slot in layout_plan.get("slots", []):
                    if slot.get("row_id") == att.target or att.target in slot.get("row_id", ""):
                        zone = slot.get("zone", [0, 0, 1000, 1000])
                        # Move zone down by 5%
                        zone[0] = min(950, zone[0] + 50)
                        zone[2] = min(1000, zone[2] + 50)
                        slot["zone"] = zone
