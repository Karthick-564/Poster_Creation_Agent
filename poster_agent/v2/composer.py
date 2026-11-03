"""Renderers for v2 specs.

``MockRenderer`` is a full Pillow implementation used for offline verification.
``VectorCraftComposer`` is the live Windows path: it translates the same spec
into VectorCraft commands, preserving native text, vector shapes and logo
intrinsic aspect ratio.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .contracts import (
    AssetBundle,
    BrandContract,
    ManifestRow,
    PosterSpec,
    RenderResult,
)
from .qr import make_qr_image
from .typography import fit_text

_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(size: float, weight: int) -> ImageFont.FreeTypeFont:
    path = _FONT_BOLD if weight >= 600 else _FONT_REGULAR
    try:
        return ImageFont.truetype(path, max(6, int(round(size))))
    except Exception:
        return ImageFont.load_default()


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _field_rect(
    spec: PosterSpec,
    brand: BrandContract,
) -> tuple[float, float, float, float] | None:
    if not spec.logo_slots:
        return None
    fmt = spec.format
    logo = spec.logo_slots[0]
    x, y, w, h = logo.box.to_px(fmt.width, fmt.height)
    pad = min(brand.clear_space_px(fmt), max(12.0, 0.2 * w))
    return (
        max(0.0, x - pad),
        max(0.0, y - pad),
        min(fmt.width, x + w + pad),
        min(fmt.height, y + h + pad),
    )


class MockRenderer:
    """Pillow renderer that measures exactly what it draws."""

    engine = "mock"

    def render(
        self,
        spec: PosterSpec,
        assets: AssetBundle,
        brand: BrandContract,
        output_path: str | Path,
        work_dir: str | Path | None = None,
    ) -> RenderResult:
        fmt = spec.format
        width, height = fmt.width, fmt.height
        warnings: list[str] = []
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        background = assets.get("background")
        if background and Path(background.path).exists():
            canvas = Image.open(background.path).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        else:
            canvas = Image.new("RGB", (width, height), _hex(spec.background_color))
            warnings.append("Background asset missing; using brand primary field.")

        image_rects: dict[str, tuple[float, float, float, float]] = {}
        hero_rect: tuple[float, float, float, float] | None = None

        # Hero and decoration layers.
        for slot in spec.image_slots:
            if slot.role == "background":
                continue
            image = assets.get(slot.id)
            if not image or not Path(image.path).exists():
                warnings.append(f"Image slot {slot.id!r} has no asset.")
                continue
            x, y, w, h = slot.box.to_px(width, height)
            image_rects[slot.id] = (x, y, w, h)
            if slot.role == "hero":
                hero_rect = (x, y, w, h)
            layer = Image.open(image.path).convert("RGBA")
            layer = layer.resize((max(1, int(w)), max(1, int(h))), Image.Resampling.LANCZOS)
            if slot.opacity < 1.0:
                alpha = layer.getchannel("A").point(lambda a: int(a * slot.opacity))
                layer.putalpha(alpha)
            canvas.paste(layer, (int(x), int(y)), layer)

        # Solid logo field, painted after art so no gradient can sit behind the mark.
        field = _field_rect(spec, brand)
        if field and spec.logo_slots:
            fx1, fy1, fx2, fy2 = field
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((fx1, fy1, fx2, fy2), fill=_hex(spec.logo_slots[0].solid_field))
            accent = _hex(brand.color("secondary"))
            draw.rectangle((fx1, fy2, fx2, fy2 + max(4, int(height * 0.004))), fill=accent)

        # Logo, preserving its intrinsic aspect ratio inside the planned box.
        logo_rect: tuple[float, float, float, float] | None = None
        if spec.logo_slots and assets.logo and Path(assets.logo.path).exists():
            logo_slot = spec.logo_slots[0]
            x, y, w, h = logo_slot.box.to_px(width, height)
            logo_rect = (x, y, w, h)
            mark = Image.open(assets.logo.path).convert("RGBA")
            ratio = mark.width / max(1, mark.height)
            if logo_slot.preserve_aspect:
                if w / h > ratio:
                    draw_w, draw_h = h * ratio, h
                else:
                    draw_w, draw_h = w, w / ratio
                x += (w - draw_w) / 2
                y += (h - draw_h) / 2
                w, h = draw_w, draw_h
            mark = mark.resize((max(1, int(w)), max(1, int(h))), Image.Resampling.LANCZOS)
            canvas.paste(mark, (int(x), int(y)), mark)
        elif spec.logo_slots:
            warnings.append("Logo asset missing; composer skipped the mark.")

        # Typography.
        draw = ImageDraw.Draw(canvas)
        rows: list[ManifestRow] = []
        for block in spec.text_blocks:
            x, y, w, h = block.box.to_px(width, height)
            lines, size = fit_text(
                text=block.text,
                target_size=block.size,
                min_size=max(10.0, block.size * 0.55),
                max_width=w,
                max_lines=block.max_lines,
                uppercase=block.text.isupper(),
                tracking=block.tracking,
            )
            if not lines:
                continue
            font = _font(size, block.weight)
            line_height = size * block.line_height
            block_top = y
            min_x, min_y, max_x, max_y = x, y, x, y
            for index, line in enumerate(lines):
                anchor = {"left": "la", "center": "ma", "right": "ra"}[block.align]
                draw_x = x if block.align == "left" else (x + w / 2 if block.align == "center" else x + w)
                draw_y = block_top + index * line_height
                draw.text((draw_x, draw_y), line, font=font, fill=_hex(block.color), anchor=anchor)
                bbox = draw.textbbox((draw_x, draw_y), line, font=font, anchor=anchor)
                min_x = min(min_x, bbox[0])
                min_y = min(min_y, bbox[1])
                max_x = max(max_x, bbox[2])
                max_y = max(max_y, bbox[3])
            rows.append(
                ManifestRow(
                    id=block.id,
                    role=block.role,
                    text=block.text,
                    x=min_x,
                    y=min_y,
                    width=max(1.0, max_x - min_x),
                    height=max(1.0, max_y - min_y),
                    size=size,
                    font=f"mock:{'bold' if block.weight >= 600 else 'regular'}",
                    color=block.color,
                    style="Bold" if block.weight >= 600 else "",
                )
            )

        # QR block and its caption.
        if spec.qr:
            qx, qy, qw, qh = spec.qr.box.to_px(width, height)
            side = int(min(qw, qh))
            qr_path, scannable = make_qr_image(
                spec.qr.payload,
                side,
                out.parent / f"qr_{spec.candidate_id}_{spec.seed}.png",
            )
            if not scannable:
                warnings.append("qrcode package unavailable; rendered a non-scannable QR placeholder.")
            draw.rectangle((qx - 8, qy - 8, qx + side + 8, qy + side + 8), fill=(255, 255, 255))
            qr_image = Image.open(qr_path).convert("RGB").resize((side, side), Image.Resampling.NEAREST)
            canvas.paste(qr_image, (int(qx), int(qy)))
            image_rects["qr"] = (qx, qy, side, side)

            if spec.qr.label:
                label_size = max(12.0, side * 0.075)
                label_font = _font(label_size, 700)
                label_y = qy + side + 14
                draw.text((qx + side / 2, label_y), spec.qr.label, font=label_font, fill=_hex(brand.color("surface")), anchor="ma")
                bbox = draw.textbbox((qx + side / 2, label_y), spec.qr.label, font=label_font, anchor="ma")
                rows.append(
                    ManifestRow(
                        id="qr_label",
                        role="label",
                        text=spec.qr.label,
                        x=bbox[0],
                        y=bbox[1],
                        width=bbox[2] - bbox[0],
                        height=bbox[3] - bbox[1],
                        size=label_size,
                        font="mock:bold",
                        color=brand.color("surface"),
                        style="Bold",
                    )
                )

        canvas.save(out, "PNG")
        return RenderResult(
            output_png=str(out),
            width=width,
            height=height,
            rows=rows,
            hero_rect=hero_rect,
            logo_rect=logo_rect,
            image_rects=image_rects,
            engine=self.engine,
            warnings=warnings,
        )


class VectorCraftComposer:
    """Live composition through the VectorCraft CLI."""

    engine = "vectorcraft"

    def __init__(self, renderer=None, cli_path: str | Path | None = None, dry_run: bool = False):
        self._renderer = renderer
        self._cli_path = cli_path
        self.dry_run = dry_run

    def _new_renderer(self):
        if self._renderer is not None:
            self._renderer.clear()
            return self._renderer
        from poster_agent.renderer.vectorcraft_renderer import VectorCraftRenderer

        return VectorCraftRenderer(cli_path=self._cli_path)

    def build(
        self,
        spec: PosterSpec,
        assets: AssetBundle,
        brand: BrandContract,
        work_dir: str | Path,
    ):
        fmt = spec.format
        width, height = fmt.width, fmt.height
        vc = self._new_renderer()
        vc.new_document(width=width, height=height, units="Points", color_mode="rgb", raster_resolution=fmt.dpi)

        background = assets.get("background")
        if background and Path(background.path).exists():
            vc.place_image(background.path, rect=[0, 0, width, height])

        for slot in spec.image_slots:
            if slot.role != "hero":
                continue
            image = assets.get(slot.id)
            if not image or not Path(image.path).exists():
                continue
            x, y, w, h = slot.box.to_px(width, height)
            vc.place_image(image.path, rect=[x, y, w, h])

        field = _field_rect(spec, brand)
        if field and spec.logo_slots:
            fx1, fy1, fx2, fy2 = field
            vc.add_shape_rectangle(fx1, fy1, fx2 - fx1, fy2 - fy1, fill=spec.logo_slots[0].solid_field)
            accent_h = max(4, int(height * 0.004))
            vc.add_shape_rectangle(
                fx1,
                fy2,
                fx2 - fx1,
                accent_h,
                fill=brand.color("secondary"),
            )

        if spec.qr:
            qx, qy, qw, qh = spec.qr.box.to_px(width, height)
            side = int(min(qw, qh))
            qr_path, scannable = make_qr_image(
                spec.qr.payload,
                side,
                Path(work_dir) / f"qr_{spec.candidate_id}_{spec.seed}.png",
            )
            vc.add_shape_rectangle(qx - 8, qy - 8, side + 16, side + 16, fill="#FFFFFF")
            vc.place_image(qr_path, rect=[qx, qy, side, side])
            if spec.qr.label:
                label_size = max(12.0, side * 0.075)
                vc.add_text(
                    text=spec.qr.label,
                    x=qx + side / 2,
                    y=qy + side + 14,
                    size=label_size,
                    font=brand.fonts.resolve("body"),
                    color=brand.color("surface"),
                    justify="center",
                    style="Bold",
                    role="qr_label",
                )

        for block in spec.text_blocks:
            x, y, w, h = block.box.to_px(width, height)
            vc.area_text(
                text=block.text,
                x=x,
                y=y,
                width=w,
                height=h,
                size=block.size,
                font=brand.fonts.resolve(block.font_role),
                color=block.color,
                justify=block.align,
                style="Bold" if block.weight >= 600 else "",
                tracking=block.tracking,
                leading=block.line_height,
                role=block.id,
            )

        if spec.logo_slots and assets.logo and Path(assets.logo.path).exists():
            logo_slot = spec.logo_slots[0]
            x, y, w, h = logo_slot.box.to_px(width, height)
            if logo_slot.preserve_aspect:
                with Image.open(assets.logo.path) as mark:
                    ratio = mark.width / max(1, mark.height)
                if w / h > ratio:
                    draw_w, draw_h = h * ratio, h
                else:
                    draw_w, draw_h = w, w / ratio
                x += (w - draw_w) / 2
                y += (h - draw_h) / 2
                w, h = draw_w, draw_h
            vc.place_image(assets.logo.path, rect=[x, y, w, h])

        return vc

    def render(
        self,
        spec: PosterSpec,
        assets: AssetBundle,
        brand: BrandContract,
        output_path: str | Path,
        work_dir: str | Path | None = None,
        dry_run: bool | None = None,
    ) -> RenderResult:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        work = Path(work_dir or out.parent)
        work.mkdir(parents=True, exist_ok=True)
        vc = self.build(spec, assets, brand, work)
        commands_path = work / f"commands_{spec.candidate_id}_{spec.seed}.json"
        with open(commands_path, "w", encoding="utf-8") as handle:
            json.dump(vc.commands, handle, indent=2)

        if self.dry_run if dry_run is None else dry_run:
            return self._planned_result(spec, assets, brand, commands_path)

        result = vc.execute(output_png=out, work_dir=work)
        if not result.success:
            raise RuntimeError(f"VectorCraft render failed: {result.error_message}")
        return self._result_from_vc(spec, assets, brand, result, out, commands_path)

    def _planned_result(
        self,
        spec: PosterSpec,
        assets: AssetBundle,
        brand: BrandContract,
        commands_path: Path,
    ) -> RenderResult:
        fmt = spec.format
        rows = [
            ManifestRow(
                id=block.id,
                role=block.role,
                text=block.text,
                x=block.box.to_px(fmt.width, fmt.height)[0],
                y=block.box.to_px(fmt.width, fmt.height)[1],
                width=block.box.to_px(fmt.width, fmt.height)[2],
                height=block.box.to_px(fmt.width, fmt.height)[3],
                size=block.size,
                font=brand.fonts.resolve(block.font_role),
                color=block.color,
                style="Bold" if block.weight >= 600 else "",
            )
            for block in spec.text_blocks
        ]
        return RenderResult(
            output_png="",
            width=fmt.width,
            height=fmt.height,
            rows=rows,
            hero_rect=self._hero_rect(spec),
            logo_rect=self._logo_rect(spec),
            image_rects=self._image_rects(spec),
            engine="vectorcraft-dry-run",
            warnings=["Dry run: commands only, no raster output."],
            commands_path=str(commands_path),
        )

    def _result_from_vc(self, spec, assets, brand, result, out: Path, commands_path: Path) -> RenderResult:
        fmt = spec.format
        by_role = {block.id: block for block in spec.text_blocks}
        rows: list[ManifestRow] = []
        for item in result.text_manifest:
            role = item.get("role") or ""
            block = by_role.get(role)
            bounds = item.get("bounds") or {}
            if bounds:
                x = float(bounds.get("x", 0.0))
                y = float(bounds.get("y", 0.0))
                w = float(bounds.get("width", 0.0))
                h = float(bounds.get("height", 0.0))
            elif block:
                x, y, w, h = block.box.to_px(fmt.width, fmt.height)
            else:
                continue
            rows.append(
                ManifestRow(
                    id=item.get("id") or role,
                    role=role,
                    text=item.get("text", ""),
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    size=float(item.get("size") or (block.size if block else 0.0)),
                    font=item.get("font", ""),
                    color=block.color if block else "#FFFFFF",
                    style=item.get("style", ""),
                )
            )
        return RenderResult(
            output_png=str(result.output_png or out),
            width=fmt.width,
            height=fmt.height,
            rows=rows,
            hero_rect=self._hero_rect(spec),
            logo_rect=self._logo_rect(spec),
            image_rects=self._image_rects(spec),
            engine=self.engine,
            warnings=list(result.warnings),
            commands_path=str(commands_path),
        )

    @staticmethod
    def _hero_rect(spec: PosterSpec) -> tuple[float, float, float, float] | None:
        hero = spec.image("hero")
        if not hero:
            return None
        return hero.box.to_px(spec.format.width, spec.format.height)  # type: ignore[return-value]

    @staticmethod
    def _logo_rect(spec: PosterSpec) -> tuple[float, float, float, float] | None:
        if not spec.logo_slots:
            return None
        return spec.logo_slots[0].box.to_px(spec.format.width, spec.format.height)  # type: ignore[return-value]

    @staticmethod
    def _image_rects(spec: PosterSpec) -> dict[str, tuple[float, float, float, float]]:
        return {
            slot.id: slot.box.to_px(spec.format.width, spec.format.height)  # type: ignore[misc]
            for slot in spec.image_slots
        }
