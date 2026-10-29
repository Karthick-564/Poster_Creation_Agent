"""Qwen-Image Generator Adapter (Second generator implementation)."""
import random
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw

from poster_agent.spec.models import PosterSpec
from .base import GeneratorAdapter, GeneratedArt


class QwenImageGenerator(GeneratorAdapter):
    """Adapter for Qwen Image models (e.g. Qwen 2.1 Image in ComfyUI)."""

    def __init__(self, endpoint: str = "http://127.0.0.1:8188", mode: str = "stub"):
        self.endpoint = endpoint
        self.mode = mode

    def build_prompt(self, spec: PosterSpec) -> str:
        """Construct detailed natural language prompt for Qwen Image."""
        art_prompt = spec.art_slots[0].prompt if spec.art_slots else "Futuristic graphic design event poster"
        style = spec.assumptions[0] if spec.assumptions else "Modern digital art"
        palette_str = ", ".join(spec.palette[:5]) if spec.palette else "#0B132B, #00F5D4"

        return (
            f"{art_prompt}. Style: {style}. Color theme: {palette_str}. "
            f"High resolution, sharp composition, cinematic lighting, masterpiece poster graphic."
        )

    def generate(
        self,
        spec: PosterSpec,
        count: int = 1,
        base_seed: int | None = None,
        output_dir: Path | str | None = None,
    ) -> list[GeneratedArt]:
        out_dir = Path(output_dir) if output_dir else Path("runs/temp_qwen")
        out_dir.mkdir(parents=True, exist_ok=True)

        prompt_text = self.build_prompt(spec)
        start_seed = base_seed if base_seed is not None else random.randint(100000, 999999)
        results: list[GeneratedArt] = []

        w = 1024
        h = max(256, (int(round(spec.canvas_height_px * 1024 / spec.canvas_width_px)) // 16) * 16)

        bg_hex = spec.palette[0] if spec.palette else "#0B132B"
        bg_rgb = tuple(int(bg_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        accent_hex = spec.palette[1] if len(spec.palette) > 1 else "#00F5D4"
        accent_rgb = tuple(int(accent_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

        for i in range(count):
            seed = start_seed + i
            img_path = out_dir / f"qwen_art_{seed}.png"

            # Create high-quality placeholder graphic
            img = Image.new("RGB", (w, h), bg_rgb)
            draw = ImageDraw.Draw(img)
            draw.ellipse([(100, 100), (w - 100, h - 100)], outline=accent_rgb, width=4)
            img.save(img_path, "PNG")

            payload = {
                "model": "qwen_image_2.1",
                "prompt": prompt_text,
                "seed": seed,
                "width": w,
                "height": h,
            }

            results.append(
                GeneratedArt(
                    image_path=img_path,
                    seed=seed,
                    payload=payload,
                    prompt_used=prompt_text,
                )
            )

        return results
