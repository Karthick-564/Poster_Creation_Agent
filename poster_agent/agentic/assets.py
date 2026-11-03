"""Stage 2: Deterministic Asset Decisions.

Applies the 4-tier resolver ladder (supplied -> archive -> native -> generated)
per visual asset slot. Institution logos and mandatory elements are never
generated; they come strictly from supplied/archive assets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from poster_agent.assets.resolver import AssetResolver, ResolvedAsset
from poster_agent.house_style import load_house_style, resolve_school
from poster_agent.ingestion.extractor import ExtractedBrief

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class AssetDecisions:
    slots: dict[str, ResolvedAsset] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def get_path(self, slot: str) -> Optional[str]:
        if slot in self.slots:
            return self.slots[slot].path
        return None

    def get_source(self, slot: str) -> str:
        if slot in self.slots:
            return self.slots[slot].source
        return "native"


class AssetDecisionStage:
    """Decides source and provenance for all poster visual layers."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.resolver = AssetResolver(project_root=self.project_root)
        self.house_style = load_house_style()

    def decide(
        self,
        brief: ExtractedBrief,
        school_id: Optional[str] = None,
        allow_generation: bool = True,
    ) -> AssetDecisions:
        """Resolve all slots through the ladder."""
        actual_school, school_info = resolve_school(brief, house_style=self.house_style)
        if school_id and school_id in self.house_style.get("schools", {}):
            actual_school = school_id
            school_info = self.house_style["schools"][school_id]

        slots: dict[str, ResolvedAsset] = {}
        provenance: dict[str, Any] = {}
        warnings: list[str] = []

        # 1. Logo Slot (STRICT: NEVER GENERATED)
        school_logo_rel = school_info.get("logo", "assets/logo_kumaraguru.png")
        logo_path = self.project_root / school_logo_rel
        if logo_path.exists():
            slots["logo"] = ResolvedAsset(
                slot="logo",
                source="supplied",
                path=str(logo_path),
                why=f"Official {actual_school} institutional logo from house style.",
            )
        else:
            warnings.append(f"Official logo missing at {logo_path}")
            slots["logo"] = ResolvedAsset(
                slot="logo",
                source="native",
                path="",
                why="Logo file missing; will render native vector placeholder card.",
            )

        # Concept plan shim for the asset ladder
        concept_plan = {
            "asset_plan": [
                {"slot": "background", "source": "generated" if allow_generation else "native"},
                {"slot": "hero", "source": "generated" if allow_generation else "native"},
            ]
        }

        # 2. Background Slot
        bg_resolved = self.resolver.resolve_slot("background", brief, concept_plan)
        if not allow_generation and bg_resolved.source == "generated":
            slots["background"] = ResolvedAsset(
                slot="background",
                source="native",
                path="",
                why="Generation disabled for this run; VectorCraft renders native background substrate.",
            )
        else:
            slots["background"] = bg_resolved

        # 3. Hero Slot
        hero_resolved = self.resolver.resolve_slot("hero", brief, concept_plan)
        if not allow_generation and hero_resolved.source == "generated":
            slots["hero"] = ResolvedAsset(
                slot="hero",
                source="native",
                path="",
                why="Generation disabled for this run; composition uses typography-as-hero.",
            )
        else:
            slots["hero"] = hero_resolved

        # Compile provenance audit
        for slot_name, item in slots.items():
            provenance[slot_name] = {
                "source": item.source,
                "path": str(Path(item.path).relative_to(self.project_root)) if item.path and Path(item.path).is_relative_to(self.project_root) else item.path,
                "why": item.why,
            }

        return AssetDecisions(
            slots=slots,
            provenance=provenance,
            warnings=warnings,
        )

