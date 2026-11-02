"""Deterministic asset resolution layer (Stage 2b).

Resolver ladder per slot — first match wins, every decision logged:
1. supplied: brief carries asset path. Verify exists, decodable, min size >= 20000B.
2. archive: tag match against configs/asset_sources.yaml keywords x brief keywords. Alphabetical tie-break.
3. native: no raster image; VectorCraft builds background or no hero layer.
4. generated: only reached if concept says source: generated and 1-3 empty.
"""
import os
import re
from pathlib import Path
from typing import Any, Literal, Optional
import yaml
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.ingestion.extractor import ExtractedBrief

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

AssetSourceType = Literal["supplied", "archive", "native", "generated"]


class ResolvedAsset(BaseModel):
    """Provenance and resolution outcome for a single visual asset slot."""
    model_config = ConfigDict(extra="forbid")
    slot: str
    source: AssetSourceType
    path: str
    why: str


class AssetResolver:
    """Deterministic, pure-code asset resolution ladder."""

    DEFAULT_CONFIG: dict[str, Any] = {
        "archive_roots": ["assets/photos", "assets"],
        "min_file_size": 20000,
        "allowed_extensions": [".png", ".jpg", ".jpeg", ".webp"],
        "tag_keywords": {
            "campus": ["campus", "building", "atrium", "architecture", "ground", "hall", "dome"],
            "students": ["students", "student", "peers", "team", "people", "community", "collaborate", "recruitment"],
            "sports": ["sports", "athlete", "run", "marathon", "fitness", "racing"],
            "tech": ["tech", "hackathon", "robot", "pcb", "coding", "developer", "gdg", "ctf"],
            "lab": ["lab", "biotech", "research", "science", "experiment"],
            "cultural": ["cultural", "concert", "drama", "music", "dance", "fest"],
        },
    }

    def __init__(
        self,
        config_path: Optional[Path | str] = None,
        project_root: Optional[Path] = None,
    ):
        self.project_root = Path(project_root or PROJECT_ROOT)
        cfg_file = Path(config_path) if config_path else (self.project_root / "configs" / "asset_sources.yaml")
        if cfg_file.exists():
            with open(cfg_file, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or self.DEFAULT_CONFIG
        else:
            self.config = self.DEFAULT_CONFIG

        self.archive_roots = [
            self.project_root / r for r in self.config.get("archive_roots", ["assets/photos", "assets"])
        ]
        self.min_file_size = int(self.config.get("min_file_size", 20000))
        self.allowed_extensions = set(self.config.get("allowed_extensions", [".png", ".jpg", ".jpeg", ".webp"]))
        self.tag_keywords = self.config.get("tag_keywords", {})
        self.logs: list[str] = []

    def _log(self, msg: str):
        self.logs.append(msg)

    def _verify_image(self, path: Path) -> tuple[bool, str]:
        """Verify image exists, is >= min_file_size, and is decodable."""
        if not path.exists():
            return False, f"File does not exist: {path}"
        try:
            sz = path.stat().st_size
            if sz < self.min_file_size:
                return False, f"File size {sz}B below min_file_size {self.min_file_size}B"
            with Image.open(path) as img:
                img.verify()
            return True, ""
        except Exception as e:
            return False, f"Image decoding failed: {e}"

    def resolve_slot(
        self,
        slot: str,
        brief: ExtractedBrief,
        concept_plan: dict[str, Any],
    ) -> ResolvedAsset:
        """Resolve a single slot through the 4-stage deterministic ladder."""
        self._log(f"--- Resolving slot: '{slot}' ---")

        # Extract concept asset plan item for this slot if present
        concept_asset_plan = concept_plan.get("asset_plan", [])
        slot_plan_entry = next((item for item in concept_asset_plan if item.get("slot") == slot), None)
        declared_source = slot_plan_entry.get("source") if slot_plan_entry else None
        declared_ref = slot_plan_entry.get("ref", "") if slot_plan_entry else ""

        # Check if concept or brief explicitly forbids art / requests plain native
        art_desc = (brief.get_text("art") or brief.get_text("mood") or "").lower()
        slot_text = (brief.get_text(slot) or "").lower()
        forbid_art = any(w in art_desc for w in ["no art", "no image", "plain text", "plain wishes", "commemorative wishes", "forbid art", "native"]) or slot_text == "native"
        if declared_source == "native" or forbid_art:
            self._log(f"[Ladder Step 3: native] Chosen directly: declared={declared_source}, forbid_art={forbid_art}")
            return ResolvedAsset(
                slot=slot,
                source="native",
                path="native",
                why=f"Native requested (declared={declared_source}, forbid_art={forbid_art})",
            )

        # -----------------------------------------------------------------
        # STEP 1: SUPPLIED
        # -----------------------------------------------------------------
        supplied_candidate = None
        # Check brief asset references
        if slot == "hero" and brief.get_asset_ref("hero_path"):
            supplied_candidate = brief.get_asset_ref("hero_path")
        elif slot == "background" and brief.get_asset_ref("background_path"):
            supplied_candidate = brief.get_asset_ref("background_path")
        elif brief.get_asset_ref(f"{slot}_path"):
            supplied_candidate = brief.get_asset_ref(f"{slot}_path")
        elif declared_source == "supplied" and declared_ref:
            supplied_candidate = declared_ref

        if supplied_candidate:
            cand_p = Path(supplied_candidate)
            if not cand_p.is_absolute():
                cand_p = self.project_root / cand_p

            ok, err = self._verify_image(cand_p)
            if ok:
                rel_path = str(cand_p.relative_to(self.project_root)).replace("\\", "/")
                self._log(f"[Ladder Step 1: supplied] MATCH: {rel_path} ({cand_p.stat().st_size} bytes)")
                return ResolvedAsset(
                    slot=slot,
                    source="supplied",
                    path=rel_path,
                    why="Supplied asset verified on disk",
                )
            else:
                banner = (
                    "*" * 80 + "\n"
                    f">>> [ASSET RESOLVER] Supplied asset validation FAILED for slot '{slot}': {err}\n"
                    f">>> Falling through to archive search.\n" +
                    "*" * 80
                )
                print(banner)
                self._log(f"[Ladder Step 1: supplied] FAILED ({err}) -> fallthrough to archive")

        # -----------------------------------------------------------------
        # STEP 2: ARCHIVE
        # -----------------------------------------------------------------
        # Compile brief text for keyword extraction
        brief_corpus = " ".join([
            brief.get_text("title"),
            brief.get_text("organizer"),
            brief.get_text("partner"),
            brief.get_text("mood"),
            brief.get_text("events"),
            brief.get_text("tagline"),
            brief.get_text("subtitle"),
            brief.get_text("art"),
        ]).lower()

        matched_tags: list[str] = []
        for tag, kw_list in self.tag_keywords.items():
            if any(re.search(rf"\b{re.escape(kw)}\b", brief_corpus) for kw in kw_list):
                matched_tags.append(tag)

        # Look in archive roots
        candidates: list[Path] = []
        for root in self.archive_roots:
            if not root.exists():
                continue
            for f in root.rglob("*"):
                if f.is_file() and f.suffix.lower() in self.allowed_extensions:
                    # Match slot type in filename or parent
                    f_name_lower = f.name.lower()
                    parent_lower = f.parent.name.lower()
                    # Check if file relates to the slot and matched tags
                    tag_match = any(t in f_name_lower or t in parent_lower for t in matched_tags)
                    slot_match = slot in f_name_lower or slot in parent_lower or (slot == "hero" and "photo" in parent_lower)
                    if tag_match or (matched_tags and slot_match):
                        ok, _ = self._verify_image(f)
                        if ok:
                            candidates.append(f)

        if candidates:
            candidates.sort(key=lambda p: str(p).lower())
            chosen = candidates[0]
            rel_path = str(chosen.relative_to(self.project_root)).replace("\\", "/")
            self._log(f"[Ladder Step 2: archive] MATCH: {rel_path} (tag match: {matched_tags})")
            return ResolvedAsset(
                slot=slot,
                source="archive",
                path=rel_path,
                why=f"Archive match for tags: {matched_tags}",
            )
        else:
            self._log(f"[Ladder Step 2: archive] MISS: No archive candidates found for tags: {matched_tags}")

        # -----------------------------------------------------------------
        # STEP 3: NATIVE
        # -----------------------------------------------------------------
        if declared_source is None or declared_source != "generated":
            self._log(f"[Ladder Step 3: native] Source '{declared_source}' is not 'generated'; resolving native for '{slot}'")
            return ResolvedAsset(
                slot=slot,
                source="native",
                path="native",
                why=f"Declared source '{declared_source}' resolved to native",
            )

        # -----------------------------------------------------------------
        # STEP 4: GENERATED
        # -----------------------------------------------------------------
        # Only reached if concept's asset_plan says source: generated AND steps 1–3 came up empty.
        model_name = "qwen-image-2.1" if slot == "hero" else "ideogram-4.0"
        self._log(f"[Ladder Step 4: generated] Reached generation tool for slot '{slot}' (model={model_name})")
        return ResolvedAsset(
            slot=slot,
            source="generated",
            path=f"generated:{model_name}",
            why="Concept requested generation and no supplied/archive match found",
        )

    def resolve_all(
        self,
        brief: ExtractedBrief,
        concept_plan: dict[str, Any],
    ) -> dict[str, ResolvedAsset]:
        """Resolve all required slots (hero, background, plus any extra in asset_plan)."""
        slots = ["hero", "background"]
        for item in concept_plan.get("asset_plan", []):
            s = item.get("slot")
            if s and s not in slots:
                slots.append(s)

        results: dict[str, ResolvedAsset] = {}
        for s in slots:
            results[s] = self.resolve_slot(s, brief, concept_plan)
        return results

