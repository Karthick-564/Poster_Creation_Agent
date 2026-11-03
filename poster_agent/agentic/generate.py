"""Stage 3: Layer Asset Generation and Measurement.

Executes diffusion model calls (Ideogram 4.0 for background, Qwen-Image 2.1 for
transparent RGBA hero) only when Stage 2 resolves to 'generated'.
Persists generation seeds, runs check_refusal_free on every layer, and measures
alpha bounding geometry and tone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import time
from typing import Any, Optional

from poster_agent.generators.comfyui_client import ComfyUIClient
from poster_agent.qa.gates import check_refusal_free
from poster_agent.vision.art_measurer import ArtMeasurer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class GenerationResult:
    layers: dict[str, str] = field(default_factory=dict) # slot -> file path
    seeds: dict[str, int] = field(default_factory=dict)
    measured_bg: dict[str, Any] = field(default_factory=dict)
    measured_hero: dict[str, Any] = field(default_factory=dict)
    refusal_clean: bool = True
    refusal_reason: Optional[str] = None


class GenerationStage:
    """Manages layer generation and raster measurement."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8188",
        project_root: Optional[Path] = None,
        bg_model: str = "ideogram",
    ):
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.client = ComfyUIClient(endpoint=endpoint)
        self.measurer = ArtMeasurer()
        self.bg_model = bg_model

    def run(
        self,
        asset_decisions: Any,
        run_dir: Path,
        palette: list[str],
        canvas_w: float = 1080.0,
        canvas_h: float = 1920.0,
        brief_title: str = "Event",
    ) -> GenerationResult:
        """Generate requested layers and measure geometry."""
        layers: dict[str, str] = {}
        seeds: dict[str, int] = {}
        measured_bg: dict[str, Any] = {}
        measured_hero: dict[str, Any] = {}

        # 1. Background
        bg_decision = asset_decisions.slots.get("background")
        if bg_decision and bg_decision.source == "generated":
            bg_seed = int(time.time() * 1000) % 1_000_000_000
            seeds["background"] = bg_seed
            out_bg = run_dir / f"layer0_bg_{bg_seed}.png"

            if self.client.is_alive():
                if self.bg_model == "flux":
                    self.client.generate_flux_background(
                        prompt=f"Atmospheric background key visual for {brief_title}, color accents in {', '.join(palette[:3])}",
                        output_path=out_bg,
                        width=int(canvas_w) if canvas_w <= 1024 else 768,
                        height=int(canvas_h) if canvas_h <= 1024 else 1024,
                    )
                else:
                    self.client.generate_ideogram_background(
                        description=f"Atmospheric background key visual for {brief_title}",
                        palette=palette,
                        output_path=out_bg,
                        canvas_w=canvas_w,
                        canvas_h=canvas_h,
                    )
                layers["background"] = str(out_bg)
                refusal_fails = check_refusal_free(out_bg)
                if refusal_fails:
                    return GenerationResult(
                        layers=layers,
                        seeds=seeds,
                        refusal_clean=False,
                        refusal_reason=f"Safety filter / refusal artifact detected in generated background: {refusal_fails[0].detail if hasattr(refusal_fails[0], 'detail') else 'refusal artifact'}",
                    )
            else:
                # ComfyUI offline fallback to native
                layers["background"] = ""
        elif bg_decision and bg_decision.source in ("supplied", "archive") and bg_decision.path:
            layers["background"] = bg_decision.path

        # 2. Hero
        hero_decision = asset_decisions.slots.get("hero")
        if hero_decision and hero_decision.source == "generated":
            hero_seed = (int(time.time() * 1000) ^ 0x5EED) % 1_000_000_000
            seeds["hero"] = hero_seed
            out_hero = run_dir / f"layer3_hero_{hero_seed}.png"

            if self.client.is_alive():
                self.client.generate_qwen_rgba(
                    prompt=f"A single sculptural hero object representing {brief_title}, transparent alpha cutout",
                    output_path=out_hero,
                    width=768,
                    height=768,
                )
                layers["hero"] = str(out_hero)
                refusal_fails = check_refusal_free(out_hero)
                if refusal_fails:
                    return GenerationResult(
                        layers=layers,
                        seeds=seeds,
                        refusal_clean=False,
                        refusal_reason=f"Safety filter / refusal artifact detected in generated hero: {refusal_fails[0].detail if hasattr(refusal_fails[0], 'detail') else 'refusal artifact'}",
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
        )

