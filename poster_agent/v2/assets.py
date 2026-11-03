"""Asset brokers for the v2 pipeline.

Two implementations share one contract:

* ``MockAssetBroker`` renders deterministic placeholder art with Pillow so the
  full pipeline can be exercised on any host, including WSL where the Windows
  VectorCraft binary cannot run.
* ``ComfyUIAssetBroker`` calls the proven ComfyUI client: Ideogram 4.0 for the
  background and Qwen-Image 2.1 for the transparent hero.

The broker never invents an institutional logo silently. If the official file
is missing it either returns a clearly marked placeholder (opt-in) or no logo
at all, which becomes a blocking brand gate.
"""
from __future__ import annotations

import hashlib
import math
import random
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .contracts import AssetBundle, BrandContract, ImageSlot, PosterSpec, ResolvedImage

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


class AssetBroker(Protocol):
    def provide(self, spec: PosterSpec, brand: BrandContract, force: bool = False) -> AssetBundle:
        ...


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(str(path), size=size)
    except Exception:
        return ImageFont.load_default()


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def _image_info(path: Path, slot: ImageSlot, source: str, seed: int, prompt: str, placeholder: bool = False) -> ResolvedImage:
    with Image.open(path) as image:
        width, height = image.size
        transparent = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    return ResolvedImage(
        slot_id=slot.id,
        role=slot.role,
        path=str(path),
        source=source,  # type: ignore[arg-type]
        width=width,
        height=height,
        transparent=transparent,
        generator=source,
        seed=seed,
        prompt=prompt,
        placeholder=placeholder,
    )


def make_placeholder_logo(path: str | Path, brand: BrandContract) -> Path:
    """Draw a clearly marked 3:1 placeholder mark. Never claims to be official."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    width, height = 900, 300
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    primary = _hex(brand.color("primary"))
    tertiary = _hex(brand.color("tertiary"))
    draw.rounded_rectangle((8, 8, width - 8, height - 8), radius=26, outline=(*primary, 90), width=3)
    draw.text((54, 58), "KCT", font=_font(150, True), fill=(*primary, 255))
    draw.text((58, 218), "PLACEHOLDER — OFFICIAL LOGO MISSING", font=_font(28, True), fill=(*tertiary, 230))
    image.save(out)
    return out


def resolve_logo(
    brand: BrandContract,
    output_dir: Path,
    allow_placeholder: bool,
    warnings: list[str],
) -> ResolvedImage | None:
    if brand.logo.asset:
        candidate = Path(brand.logo.asset)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        if candidate.exists():
            with Image.open(candidate) as image:
                width, height = image.size
                transparent = image.mode in ("RGBA", "LA")
            return ResolvedImage(
                slot_id="brand_logo",
                role="decoration",
                path=str(candidate),
                source="supplied",
                width=width,
                height=height,
                transparent=transparent,
                generator="official-asset",
            )
        warnings.append(f"Official logo missing at {candidate}")

    if not allow_placeholder:
        warnings.append("No logo asset resolved; brand gate will block delivery.")
        return None

    placeholder = output_dir / f"{_slug(brand.school_id)}_logo_placeholder.png"
    make_placeholder_logo(placeholder, brand)
    warnings.append("Using a marked placeholder logo; deliverable is not brand-ready.")
    with Image.open(placeholder) as image:
        width, height = image.size
    return ResolvedImage(
        slot_id="brand_logo",
        role="decoration",
        path=str(placeholder),
        source="supplied",
        width=width,
        height=height,
        transparent=True,
        generator="placeholder",
        placeholder=True,
    )


class MockAssetBroker:
    """Deterministic Pillow art so the pipeline is testable offline."""

    def __init__(self, output_dir: str | Path, allow_placeholder_logo: bool = True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.allow_placeholder_logo = allow_placeholder_logo

    def provide(self, spec: PosterSpec, brand: BrandContract, force: bool = False) -> AssetBundle:
        warnings: list[str] = []
        images: dict[str, ResolvedImage] = {}
        for slot in spec.image_slots:
            if slot.role == "background":
                path = self._background(spec, brand, slot)
            elif slot.role == "hero":
                path = self._hero(spec, brand, slot)
            else:
                path = self._decoration(spec, brand, slot)
            images[slot.id] = _image_info(
                path=path,
                slot=slot,
                source="supplied" if slot.source == "supplied" else slot.source,
                seed=spec.seed,
                prompt=slot.prompt,
            )

        logo = resolve_logo(
            brand=brand,
            output_dir=self.output_dir,
            allow_placeholder=self.allow_placeholder_logo,
            warnings=warnings,
        )
        return AssetBundle(images=images, logo=logo, warnings=warnings)

    # ------------------------------------------------------------------
    def _background(self, spec: PosterSpec, brand: BrandContract, slot: ImageSlot) -> Path:
        width, height = spec.format.width, spec.format.height
        rng = random.Random(spec.seed)
        primary = _hex(brand.color("primary"))
        tertiary = _hex(brand.color("tertiary"))
        secondary = _hex(brand.color("secondary"))
        neutral = _hex(brand.color("neutral"))

        image = Image.new("RGB", (width, height), primary)
        draw = ImageDraw.Draw(image, "RGBA")

        # Large atmospheric fields; the logo corner is repainted with a solid
        # field by the composer, so gradients are allowed elsewhere.
        for _ in range(7):
            cx = rng.uniform(0.25, 0.85) * width
            cy = rng.uniform(0.08, 0.85) * height
            rx = rng.uniform(0.22, 0.55) * width
            ry = rng.uniform(0.12, 0.38) * height
            color = tertiary if rng.random() < 0.55 else secondary
            alpha = rng.randint(28, 64)
            draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(*color, alpha))

        # A calm lower-left typography field.
        scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(scrim)
        sdraw.ellipse(
            (-0.25 * width, 0.55 * height, 0.75 * width, 1.15 * height),
            fill=(*primary, 200),
        )
        scrim = scrim.filter(ImageFilter.GaussianBlur(radius=max(8, width // 45)))
        image = Image.alpha_composite(image.convert("RGBA"), scrim).convert("RGB")

        # Fine institutional grid, kept very low contrast.
        draw = ImageDraw.Draw(image, "RGBA")
        step = max(24, width // 30)
        for x in range(0, width, step):
            draw.line((x, 0, x, height), fill=(*neutral, 10), width=1)
        for y in range(0, height, step):
            draw.line((0, y, width, y), fill=(*neutral, 10), width=1)

        # Secondary accent arc on the right, away from the logo field.
        draw.arc(
            (width * 0.58, height * 0.26, width * 1.18, height * 0.98),
            start=118,
            end=292,
            fill=(*secondary, 120),
            width=max(3, width // 220),
        )

        out = self.output_dir / f"bg_{spec.candidate_id}_{spec.seed}.png"
        image.save(out)
        return out

    def _hero(self, spec: PosterSpec, brand: BrandContract, slot: ImageSlot) -> Path:
        size = 1000
        rng = random.Random(spec.seed ^ 0x5EED)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        secondary = _hex(brand.color("secondary"))
        neutral = _hex(brand.color("neutral"))
        surface = _hex(brand.color("surface"))
        tertiary = _hex(brand.color("tertiary"))

        # Glow layer.
        glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        for radius, alpha in ((330, 40), (260, 55), (190, 70)):
            gdraw.ellipse(
                (size / 2 - radius, size / 2 - radius, size / 2 + radius, size / 2 + radius),
                fill=(*secondary, alpha),
            )
        glow = glow.filter(ImageFilter.GaussianBlur(radius=55))
        canvas = Image.alpha_composite(canvas, glow)

        draw = ImageDraw.Draw(canvas, "RGBA")

        # Sculptural stacked forms: readable at poster scale, clearly a cutout.
        cx, cy = size / 2, size / 2
        body_w, body_h = 300, 430
        draw.rounded_rectangle(
            (cx - body_w / 2 - 12, cy - body_h / 2 + 18, cx + body_w / 2 + 12, cy + body_h / 2 + 30),
            radius=90,
            fill=(*neutral, 120),
        )
        draw.rounded_rectangle(
            (cx - body_w / 2, cy - body_h / 2, cx + body_w / 2, cy + body_h / 2),
            radius=78,
            fill=(*secondary, 245),
        )
        draw.rounded_rectangle(
            (cx - body_w / 2 + 26, cy - body_h / 2 + 22, cx + body_w / 2 - 26, cy + body_h / 2 - 26),
            radius=58,
            fill=(*tertiary, 235),
        )

        # A bright diagonal shard and orbit rings give the hero a designed,
        # non-black silhouette.
        angle = rng.uniform(-22, 22)
        shard = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shard)
        sdraw.polygon(
            [
                (cx - 190, cy + 120),
                (cx + 40, cy - 235),
                (cx + 210, cy - 150),
                (cx - 20, cy + 205),
            ],
            fill=(*surface, 225),
        )
        shard = shard.rotate(angle, resample=Image.Resampling.BICUBIC, center=(cx, cy))
        canvas = Image.alpha_composite(canvas, shard)

        draw = ImageDraw.Draw(canvas, "RGBA")
        draw.ellipse((cx - 320, cy - 320, cx + 320, cy + 320), outline=(*secondary, 190), width=10)
        draw.ellipse((cx - 255, cy - 255, cx + 255, cy + 255), outline=(*neutral, 120), width=4)
        draw.arc(
            (cx - 300, cy - 300, cx + 300, cy + 300),
            start=200,
            end=340,
            fill=(*surface, 210),
            width=8,
        )

        # Stray sparks, still attached to the subject so alpha stays clean.
        for _ in range(9):
            ang = rng.uniform(0, math.tau)
            dist = rng.uniform(300, 420)
            sx, sy = cx + math.cos(ang) * dist, cy + math.sin(ang) * dist
            r = rng.uniform(5, 13)
            draw.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(*secondary, rng.randint(120, 220)))

        out = self.output_dir / f"hero_{spec.candidate_id}_{spec.seed}.png"
        canvas.save(out)
        return out

    def _decoration(self, spec: PosterSpec, brand: BrandContract, slot: ImageSlot) -> Path:
        width = max(64, int(slot.box.w * spec.format.width / 1000))
        height = max(64, int(slot.box.h * spec.format.height / 1000))
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((4, 4, width - 4, height - 4), fill=(*_hex(brand.color("secondary")), 200))
        out = self.output_dir / f"deco_{slot.id}_{spec.seed}.png"
        image.save(out)
        return out


class ComfyUIAssetBroker:
    """Live Ideogram 4.0 + Qwen-Image 2.1 broker."""

    def __init__(
        self,
        output_dir: str | Path,
        endpoint: str = "http://127.0.0.1:8188",
        client=None,
        allow_placeholder_logo: bool = False,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.allow_placeholder_logo = allow_placeholder_logo
        if client is None:
            from poster_agent.generators.comfyui_client import ComfyUIClient

            client = ComfyUIClient(endpoint=endpoint)
        self.client = client

    def provide(self, spec: PosterSpec, brand: BrandContract, force: bool = False) -> AssetBundle:
        warnings: list[str] = []
        images: dict[str, ResolvedImage] = {}
        for slot in spec.image_slots:
            if slot.source == "supplied":
                path = Path(slot.prompt)
            elif slot.role == "background":
                path = self._background(spec, brand, slot, force=force)
            elif slot.role == "hero":
                path = self._hero(spec, brand, slot, force=force)
            else:
                continue
            images[slot.id] = _image_info(
                path=path,
                slot=slot,
                source=slot.source,
                seed=spec.seed,
                prompt=slot.prompt,
            )

        logo = resolve_logo(
            brand=brand,
            output_dir=self.output_dir,
            allow_placeholder=self.allow_placeholder_logo,
            warnings=warnings,
        )
        return AssetBundle(images=images, logo=logo, warnings=warnings)

    def _cache_path(self, spec: PosterSpec, kind: str) -> Path:
        digest = hashlib.sha256(
            f"{spec.school_id}|{spec.candidate_id}|{spec.seed}|{kind}".encode("utf-8")
        ).hexdigest()[:12]
        return self.output_dir / f"{kind}_{spec.candidate_id}_{digest}.png"

    def _background(self, spec: PosterSpec, brand: BrandContract, slot: ImageSlot, force: bool = False) -> Path:
        out = self._cache_path(spec, "ideogram_bg")
        if out.exists():
            if not force:
                return out
            out.unlink()
        return self.client.generate_ideogram_background(
            description=slot.prompt,
            palette=spec.palette,
            output_path=out,
            prefix=f"v2_{brand.school_id.lower()}_bg",
            canvas_w=spec.format.width,
            canvas_h=spec.format.height,
        )

    def _hero(self, spec: PosterSpec, brand: BrandContract, slot: ImageSlot, force: bool = False) -> Path:
        out = self._cache_path(spec, "qwen_hero")
        if out.exists():
            if not force:
                return out
            out.unlink()
        side = max(768, min(1280, int(spec.format.height * 0.55)))
        return self.client.generate_qwen_rgba(
            prompt=slot.prompt,
            output_path=out,
            prefix=f"v2_{brand.school_id.lower()}_hero",
            width=side,
            height=side,
        )
