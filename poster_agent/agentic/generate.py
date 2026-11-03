"""Stage 3: Layer Asset Generation and Measurement.

Executes diffusion model calls (Ideogram 4.0 / Flux 3 Klein for background,
Qwen-Image 2.1 for transparent RGBA hero) only when Stage 2 resolves to 'generated'.

Features:
1. Driven by unified model-neutral ArtDirectionSpec from ArtDirector.
2. Single source of truth for spatial zones across Ideogram, Qwen, and VectorCraft.
3. Zero conflict: central hero zone in background is a soft glow / light pool, not a competing object.
4. Generates 3 hero candidates, scores them using deterministic physical hero gates (sharpness,
   coverage, perimeter contact, halo ratio), and selects the best candidate before compositing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import shutil
import time
from typing import Any, Optional

from poster_agent.agentic.art_director import ArtDirector, ArtDirectionResult
from poster_agent.agentic.art_direction_spec import ArtDirectionSpec
from poster_agent.checks.hero_gates import evaluate_hero_quality, HeroGateResult
from poster_agent.generators.comfyui_client import ComfyUIClient
from poster_agent.qa.gates import check_refusal_free
from poster_agent.vision.art_measurer import ArtMeasurer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class GenerationResult:
    layers: dict[str, str] = field(default_factory=dict)  # slot -> file path
    seeds: dict[str, int] = field(default_factory=dict)
    measured_bg: dict[str, Any] = field(default_factory=dict)
    measured_hero: dict[str, Any] = field(default_factory=dict)
    refusal_clean: bool = True
    refusal_reason: Optional[str] = None
    art_spec: Optional[dict[str, Any]] = None
    hero_quality: Optional[dict[str, Any]] = None


class GenerationStage:
    """Manages layer generation, prompt synthesis, and raster measurement."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8188",
        project_root: Optional[Path] = None,
        bg_model: str = "ideogram",
        art_director_backend: Optional[Any] = None,
        num_hero_candidates: int = 3,
    ):
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.client = ComfyUIClient(endpoint=endpoint)
        self.measurer = ArtMeasurer()
        self.bg_model = bg_model
        self.art_director = ArtDirector(backend=art_director_backend)
        self.num_hero_candidates = num_hero_candidates

    def run(
        self,
        asset_decisions: Any,
        run_dir: Path,
        palette: list[str],
        canvas_w: float = 1080.0,
        canvas_h: float = 1920.0,
        brief_title: str = "Event",
        brief_fields: Optional[dict[str, Any]] = None,
    ) -> GenerationResult:
        """Generate requested layers with single-spec art direction and deterministic hero gates."""
        layers: dict[str, str] = {}
        seeds: dict[str, int] = {}
        measured_bg: dict[str, Any] = {}
        measured_hero: dict[str, Any] = {}
        hero_quality_dict: Optional[dict[str, Any]] = None

        # 0. Synthesize Model-Neutral Art Direction Spec
        art_result: ArtDirectionResult = self.art_director.direct(
            brief_title=brief_title,
            brief_fields=brief_fields or {},
            school_palette=palette,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
        )
        spec_dict = art_result.spec.model_dump()

        # 1. Background Generation
        bg_decision = asset_decisions.slots.get("background")
        if bg_decision and bg_decision.source == "generated":
            bg_seed = int(time.time() * 1000) % 1_000_000_000
            seeds["background"] = bg_seed
            out_bg = run_dir / f"layer0_bg_{bg_seed}.png"

            if self.client.is_alive():
                if self.bg_model == "flux":
                    self.client.generate_flux_background(
                        prompt=art_result.flux_prompt,
                        output_path=out_bg,
                        width=int(canvas_w) if canvas_w <= 1024 else 768,
                        height=int(canvas_h) if canvas_h <= 1024 else 1024,
                    )
                else:
                    self.client.generate_ideogram_background(
                        description="",  # Payload provides full canonical structure
                        palette=palette,
                        output_path=out_bg,
                        canvas_w=canvas_w,
                        canvas_h=canvas_h,
                        payload=art_result.ideogram_payload,
                    )
                layers["background"] = str(out_bg)
                refusal_fails = check_refusal_free(out_bg)
                if refusal_fails:
                    return GenerationResult(
                        layers=layers,
                        seeds=seeds,
                        refusal_clean=False,
                        refusal_reason=f"Safety filter / refusal artifact detected in generated background: {refusal_fails[0].detail if hasattr(refusal_fails[0], 'detail') else 'refusal artifact'}",
                        art_spec=spec_dict,
                    )
            else:
                layers["background"] = ""
        elif bg_decision and bg_decision.source in ("supplied", "archive") and bg_decision.path:
            layers["background"] = bg_decision.path

        # 2. Hero Cutout Generation (Multi-Candidate Evaluation)
        hero_decision = asset_decisions.slots.get("hero")
        if hero_decision and hero_decision.source == "generated":
            out_hero = run_dir / "layer3_hero.png"

            if self.client.is_alive():
                candidates: list[tuple[float, Path, int, HeroGateResult]] = []
                cands_to_run = max(1, self.num_hero_candidates)

                for c_idx in range(cands_to_run):
                    c_seed = (int(time.time() * 1000) ^ (0x5EED * (c_idx + 1))) % 1_000_000
                    cand_path = run_dir / f"layer3_hero_cand{c_idx}_{c_seed}.png"
                    self.client.generate_qwen_rgba(
                        prompt=art_result.qwen_positive_prompt,
                        negative_prompt=art_result.qwen_negative_prompt,
                        output_path=cand_path,
                        width=768,
                        height=768,
                        seed=c_seed,
                    )
                    gate_eval = evaluate_hero_quality(cand_path)
                    candidates.append((gate_eval.score, cand_path, c_seed, gate_eval))

                # Sort by score descending and keep the best candidate
                candidates.sort(key=lambda item: item[0], reverse=True)
                best_score, best_path, best_seed, best_gate = candidates[0]

                # Promote best candidate to layer3_hero.png
                shutil.copyfile(best_path, out_hero)
                seeds["hero"] = best_seed
                layers["hero"] = str(out_hero)
                hero_quality_dict = {
                    "score": best_gate.score,
                    "sharpness": best_gate.sharpness,
                    "coverage_pct": best_gate.coverage_pct,
                    "touches_border": best_gate.touches_border,
                    "halo_ratio": best_gate.halo_ratio,
                    "passed": best_gate.passed,
                    "reason": best_gate.reason,
                    "candidates_evaluated": len(candidates),
                }

                # Check refusal
                refusal_fails = check_refusal_free(out_hero)
                if refusal_fails:
                    return GenerationResult(
                        layers=layers,
                        seeds=seeds,
                        refusal_clean=False,
                        refusal_reason=f"Safety filter / refusal artifact detected in generated hero: {refusal_fails[0].detail if hasattr(refusal_fails[0], 'detail') else 'refusal artifact'}",
                        art_spec=spec_dict,
                        hero_quality=hero_quality_dict,
                    )

                # Honest halting if hero quality failed all gates
                if not best_gate.passed and best_gate.score < 40.0:
                    return GenerationResult(
                        layers=layers,
                        seeds=seeds,
                        refusal_clean=False,
                        refusal_reason=f"Hero candidate failed quality gates: {best_gate.reason} (score {best_gate.score}/100)",
                        art_spec=spec_dict,
                        hero_quality=hero_quality_dict,
                    )

                # Measure hero alpha cutout
                try:
                    m = self.measurer.measure(out_hero)
                    measured_hero = {
                        "bbox": m.bbox,
                        "center": m.center,
                        "halo_score": m.halo_score,
                    }
                except Exception:
                    pass
            else:
                layers["hero"] = ""
        elif hero_decision and hero_decision.source in ("supplied", "archive") and hero_decision.path:
            layers["hero"] = hero_decision.path
            try:
                m = self.measurer.measure(Path(hero_decision.path))
                measured_hero = {"bbox": m.bbox, "center": m.center, "halo_score": m.halo_score}
            except Exception:
                pass

        return GenerationResult(
            layers=layers,
            seeds=seeds,
            measured_bg=measured_bg,
            measured_hero=measured_hero,
            refusal_clean=True,
            art_spec=spec_dict,
            hero_quality=hero_quality_dict,
        )
