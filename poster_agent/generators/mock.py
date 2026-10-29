"""Mock generator for development, testing, and Step 1-4 pipeline execution."""
import json
import random
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw

from poster_agent.spec.models import PosterSpec
from .base import GeneratorAdapter, GeneratedArt


class MockGenerator(GeneratorAdapter):
    """Generates synthetic background art images using PIL for deterministic testing."""

    def __init__(self, default_output_dir: Path | str = "temp_mock_art"):
        self.default_output_dir = Path(default_output_dir)

    def generate(
        self,
        spec: PosterSpec,
        count: int = 1,
        base_seed: int | None = None,
        output_dir: Path | str | None = None,
        strategy: str | None = None,
    ) -> list[GeneratedArt]:
        out_path = Path(output_dir) if output_dir else self.default_output_dir
        out_path.mkdir(parents=True, exist_ok=True)

        w = spec.canvas_width_px
        h = spec.canvas_height_px

        # Extract palette colors
        bg_hex = spec.palette[0] if spec.palette else "#0B132B"
        accent_hex = spec.palette[1] if len(spec.palette) > 1 else "#00F5D4"
        secondary_hex = spec.palette[2] if len(spec.palette) > 2 else "#7209B7"

        bg_rgb = tuple(int(bg_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        accent_rgb = tuple(int(accent_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        secondary_rgb = tuple(int(secondary_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

        results: list[GeneratedArt] = []

        start_seed = base_seed if base_seed is not None else random.randint(100000, 999999)

        for i in range(count):
            seed = start_seed + i
            # Create a rich vertical gradient
            img = Image.new("RGB", (w, h), bg_rgb)
            draw = ImageDraw.Draw(img)

            # Draw ambient gradient and glow circles
            for y in range(0, h, 4):
                ratio = y / float(h)
                r = int(bg_rgb[0] * (1 - ratio * 0.5) + secondary_rgb[0] * (ratio * 0.4))
                g = int(bg_rgb[1] * (1 - ratio * 0.5) + secondary_rgb[1] * (ratio * 0.4))
                b = int(bg_rgb[2] * (1 - ratio * 0.5) + secondary_rgb[2] * (ratio * 0.4))
                draw.line([(0, y), (w, y)], fill=(r, g, b), width=4)

            # Draw glowing backdrop accents in the middle art region (y: 35% - 65%)
            art_center_x = w // 2
            art_center_y = int(h * 0.48)
            radius = int(min(w, h) * 0.28)
            draw.ellipse(
                [(art_center_x - radius, art_center_y - radius), (art_center_x + radius, art_center_y + radius)],
                outline=accent_rgb,
                width=6,
            )
            inner_radius = int(radius * 0.7)
            draw.ellipse(
                [(art_center_x - inner_radius, art_center_y - inner_radius), (art_center_x + inner_radius, art_center_y + inner_radius)],
                outline=secondary_rgb,
                width=4,
            )

            # Draw subtle geometric accent shapes matching art slots if any
            for art_slot in spec.art_slots:
                l, t, r_b, b = art_slot.box.to_pixels(w, h)
                draw.rounded_rectangle([(l, t), (r_b, b)], radius=20, outline=accent_rgb, width=4)

            file_path = out_path / f"mock_art_seed_{seed}.png"
            img.save(file_path, "PNG")

            payload = {
                "generator": "MockGenerator",
                "seed": seed,
                "canvas_w": w,
                "canvas_h": h,
                "palette": spec.palette,
                "art_slots_count": len(spec.art_slots),
            }

            prompt_desc = spec.art_slots[0].prompt if spec.art_slots else "Thematic poster background"

            results.append(
                GeneratedArt(
                    image_path=file_path,
                    seed=seed,
                    payload=payload,
                    prompt_used=prompt_desc,
                )
            )

        return results

