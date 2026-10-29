"""Renderer module: Composes PosterSpec to HTML/CSS and exports to PNG + PDF via Playwright."""
import base64
import html
import io
import json
import os
from pathlib import Path
from typing import Any, Literal
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.spec.models import PosterSpec, BBox


class DOMBoundingBox(BaseModel):
    """Bounding box extracted from DOM element."""
    model_config = ConfigDict(extra="forbid")
    element_id: str
    role: str
    left: float
    top: float
    right: float
    bottom: float
    width: float
    height: float


class RenderResult(BaseModel):
    """Output from the renderer."""
    model_config = ConfigDict(extra="forbid")
    png_path: Path
    pdf_path: Path | None = None
    html_path: Path
    dom_boxes: dict[str, DOMBoundingBox] = Field(default_factory=dict)
    strategy: Literal["A", "B"] = "B"


def _generate_qr_base64(payload: str) -> str:
    """Generate QR code PNG as base64 string."""
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        # Fallback simple placeholder image if qrcode not available
        img = Image.new("RGBA", (150, 150), (255, 255, 255, 255))
        d = ImageDraw.Draw(img)
        d.rectangle([(10, 10), (140, 140)], outline=(0, 0, 0, 255), width=4)
        d.text((30, 60), "QR CODE", fill=(0, 0, 0, 255))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"


def _load_asset_base64(asset_filename: str, assets_dir: Path | str = "assets") -> str | None:
    """Read asset file (PNG/SVG) and return base64 data URI."""
    path = Path(assets_dir) / asset_filename
    if not path.exists():
        # Search relative to repo root
        repo_root = Path(__file__).resolve().parent.parent.parent
        alt_path = repo_root / "assets" / asset_filename
        if alt_path.exists():
            path = alt_path
        else:
            return None

    data = path.read_bytes()
    if path.suffix.lower() == ".svg":
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"
    else:
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:image/png;base64,{b64}"


def _load_art_image_base64(art_image_path: str | Path) -> str | None:
    """Read art image and return base64 data URI."""
    p = Path(art_image_path)
    if not p.exists():
        return None
    data = p.read_bytes()
    suffix = p.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"


class PosterRenderer:
    """Renders PosterSpec into HTML/CSS and exports to PNG & PDF via Playwright."""

    def __init__(self, assets_dir: Path | str = "assets"):
        self.assets_dir = Path(assets_dir)
        if not self.assets_dir.exists():
            repo_root = Path(__file__).resolve().parent.parent.parent
            self.assets_dir = repo_root / "assets"

    def compose_html(
        self,
        spec: PosterSpec,
        strategy: Literal["A", "B"] = "B",
        art_image_path: str | Path | None = None,
    ) -> str:
        """Compose HTML string with pixel-perfect CSS absolute positioning."""
        w = spec.canvas_width_px
        h = spec.canvas_height_px

        bg_color = spec.palette[0] if spec.palette else "#0B132B"
        primary_color = spec.palette[1] if len(spec.palette) > 1 else "#00F5D4"

        # Background art layer
        art_layer_html = ""
        if art_image_path:
            art_data_uri = _load_art_image_base64(art_image_path)
            if art_data_uri:
                art_layer_html = (
                    f'<div class="art-layer" style="'
                    f'position: absolute; left: 0; top: 0; width: {w}px; height: {h}px; '
                    f'background-image: url(\'{art_data_uri}\'); background-size: cover; '
                    f'background-position: center; z-index: 1;"></div>'
                )

        # Logos layer (always placed by code)
        logos_html = []
        for i, logo in enumerate(spec.logos):
            l_px, t_px, r_px, b_px = logo.box.to_pixels(w, h)
            lw = r_px - l_px
            lh = b_px - t_px
            pad = logo.clear_space_px or 0
            logo_uri = _load_asset_base64(logo.file, self.assets_dir)
            if logo_uri:
                logos_html.append(
                    f'<div id="logo_{i}" data-role="logo" class="poster-element poster-logo" style="'
                    f'position: absolute; left: {l_px}px; top: {t_px}px; width: {lw}px; height: {lh}px; '
                    f'padding: {pad}px; box-sizing: border-box; z-index: 20; display: flex; '
                    f'align-items: center; justify-content: center;">'
                    f'<img src="{logo_uri}" style="max-width: 100%; max-height: 100%; object-fit: contain;" />'
                    f'</div>'
                )

        # QR code
        qr_html = ""
        if spec.qr_code:
            qr_uri = _generate_qr_base64(spec.qr_code)
            # Default QR box in bottom right if not specified
            qr_size = min(int(w * 0.12), 250)
            qr_left = w - qr_size - int(w * 0.05)
            qr_top = h - qr_size - int(h * 0.04)
            qr_html = (
                f'<div id="qr_code" data-role="qr_code" class="poster-element poster-qr" style="'
                f'position: absolute; left: {qr_left}px; top: {qr_top}px; width: {qr_size}px; height: {qr_size}px; '
                f'background: #ffffff; padding: 8px; border-radius: 8px; box-sizing: border-box; z-index: 20;">'
                f'<img src="{qr_uri}" style="width: 100%; height: 100%; object-fit: contain;" />'
                f'</div>'
            )

        # Text elements (included in Strategy B, omitted in Strategy A)
        text_elements_html = []
        if strategy == "B":
            for elem in spec.elements:
                l_px, t_px, r_px, b_px = elem.box.to_pixels(w, h)
                box_w = r_px - l_px
                box_h = b_px - t_px

                # Fit font size to bounding box and canvas width
                # 1 pt scaled proportionally to canvas width, capped by box height
                ideal_px = int(round(elem.size * (w / 800.0)))
                font_px = max(14, min(ideal_px, int(box_h * 0.65)))

                # Role specific typography enhancements
                text_transform = "none"
                letter_spacing = "normal"
                if elem.role in ("headline", "label"):
                    text_transform = "uppercase"
                    letter_spacing = "1px"
                elif elem.role == "subheadline":
                    letter_spacing = "0.5px"

                escaped_text = html.escape(elem.text)

                text_elements_html.append(
                    f'<div id="{elem.id}" data-role="{elem.role}" class="poster-element poster-text" style="'
                    f'position: absolute; left: {l_px}px; top: {t_px}px; width: {box_w}px; height: {box_h}px; '
                    f'font-family: \'{elem.font}\', \'Segoe UI\', Arial, sans-serif; '
                    f'font-size: {font_px}px; font-weight: {elem.weight}; color: {elem.color}; '
                    f'text-transform: {text_transform}; letter-spacing: {letter_spacing}; '
                    f'line-height: 1.15; overflow: hidden; display: flex; align-items: center; '
                    f'word-break: break-word; z-index: 10; box-sizing: border-box;">'
                    f'<span>{escaped_text}</span>'
                    f'</div>'
                )

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Poster</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Montserrat:wght@600;700;800;900&family=Outfit:wght@600;700;800;900&family=JetBrains+Mono:wght@500;700&display=swap');
    
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
      -webkit-font-smoothing: antialiased;
    }}
    
    body {{
      background: #111111;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      margin: 0;
    }}
    
    #canvas {{
      position: relative;
      width: {w}px;
      height: {h}px;
      background-color: {bg_color};
      overflow: hidden;
    }}
  </style>
</head>
<body>
  <div id="canvas">
    {art_layer_html}
    {''.join(text_elements_html)}
    {''.join(logos_html)}
    {qr_html}
  </div>
</body>
</html>
"""
        return html_template

    def render(
        self,
        spec: PosterSpec,
        output_dir: Path | str,
        strategy: Literal["A", "B"] = "B",
        art_image_path: str | Path | None = None,
        base_name: str = "poster",
    ) -> RenderResult:
        """Render poster to HTML, PNG, and PDF."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        html_file = out_path / f"{base_name}.html"
        png_file = out_path / f"{base_name}.png"
        pdf_file = out_path / f"{base_name}.pdf"

        html_content = self.compose_html(spec, strategy=strategy, art_image_path=art_image_path)
        html_file.write_text(html_content, encoding="utf-8")

        dom_boxes: dict[str, DOMBoundingBox] = {}

        # Attempt Playwright rendering
        playwright_success = False
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    viewport={"width": spec.canvas_width_px, "height": spec.canvas_height_px},
                    device_scale_factor=1.0,
                )
                page.set_content(html_content, wait_until="networkidle")

                # Extract bounding boxes from DOM
                elements_info = page.evaluate("""() => {
                    const canvas = document.getElementById('canvas');
                    const cRect = canvas.getBoundingClientRect();
                    const elems = document.querySelectorAll('.poster-element');
                    const results = {};
                    elems.forEach(el => {
                        const r = el.getBoundingClientRect();
                        results[el.id] = {
                            id: el.id,
                            role: el.getAttribute('data-role') || 'unknown',
                            left: r.left - cRect.left,
                            top: r.top - cRect.top,
                            right: r.right - cRect.left,
                            bottom: r.bottom - cRect.top,
                            width: r.width,
                            height: r.height
                        };
                    });
                    return results;
                }""")

                for eid, info in elements_info.items():
                    dom_boxes[eid] = DOMBoundingBox(
                        element_id=eid,
                        role=info["role"],
                        left=info["left"],
                        top=info["top"],
                        right=info["right"],
                        bottom=info["bottom"],
                        width=info["width"],
                        height=info["height"],
                    )

                # Export PNG
                canvas_handle = page.query_selector("#canvas")
                if canvas_handle:
                    canvas_handle.screenshot(path=str(png_file))
                else:
                    page.screenshot(path=str(png_file), full_page=True)

                # Export PDF
                try:
                    page.pdf(
                        path=str(pdf_file),
                        width=f"{spec.canvas_width_px}px",
                        height=f"{spec.canvas_height_px}px",
                        print_background=True,
                    )
                except Exception:
                    pdf_file = None

                browser.close()
                playwright_success = True
        except Exception:
            playwright_success = False

        if not playwright_success:
            # High-fidelity PIL fallback renderer
            dom_boxes = self._render_pil_fallback(
                spec=spec,
                strategy=strategy,
                art_image_path=art_image_path,
                png_path=png_file,
                pdf_path=pdf_file,
            )

        return RenderResult(
            png_path=png_file,
            pdf_path=pdf_file if pdf_file and pdf_file.exists() else None,
            html_path=html_file,
            dom_boxes=dom_boxes,
            strategy=strategy,
        )

    def _render_pil_fallback(
        self,
        spec: PosterSpec,
        strategy: Literal["A", "B"],
        art_image_path: str | Path | None,
        png_path: Path,
        pdf_path: Path | None,
    ) -> dict[str, DOMBoundingBox]:
        """High-fidelity PIL fallback renderer ensuring deterministic offline execution."""
        w = spec.canvas_width_px
        h = spec.canvas_height_px

        bg_hex = spec.palette[0] if spec.palette else "#0B132B"
        bg_rgb = tuple(int(bg_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

        img = Image.new("RGBA", (w, h), bg_rgb + (255,))

        if art_image_path and Path(art_image_path).exists():
            art_img = Image.open(art_image_path).convert("RGBA")
            art_img = art_img.resize((w, h), Image.Resampling.LANCZOS)
            img.paste(art_img, (0, 0), art_img)

        draw = ImageDraw.Draw(img)
        dom_boxes: dict[str, DOMBoundingBox] = {}

        # Draw logos
        for i, logo in enumerate(spec.logos):
            l_px, t_px, r_px, b_px = logo.box.to_pixels(w, h)
            lw = r_px - l_px
            lh = b_px - t_px
            logo_id = f"logo_{i}"
            logo_file_path = self.assets_dir / logo.file
            if logo_file_path.exists() and logo_file_path.suffix.lower() == ".png":
                logo_img = Image.open(logo_file_path).convert("RGBA")
                logo_img.thumbnail((lw, lh), Image.Resampling.LANCZOS)
                img.paste(logo_img, (l_px, t_px), logo_img)

            dom_boxes[logo_id] = DOMBoundingBox(
                element_id=logo_id,
                role="logo",
                left=float(l_px),
                top=float(t_px),
                right=float(r_px),
                bottom=float(b_px),
                width=float(lw),
                height=float(lh),
            )

        # Draw text elements (Strategy B)
        if strategy == "B":
            for elem in spec.elements:
                l_px, t_px, r_px, b_px = elem.box.to_pixels(w, h)
                bw = r_px - l_px
                bh = b_px - t_px
                ideal_px = int(round(elem.size * (w / 800.0)))
                font_px = max(14, min(ideal_px, int(bh * 0.65)))
                color_hex = elem.color.lstrip("#")
                color_rgb = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))

                # Use default PIL font or system font
                try:
                    font = ImageFont.truetype("arial.ttf", font_px)
                except Exception:
                    font = ImageFont.load_default()

                text = elem.text.upper() if elem.role in ("headline", "label") else elem.text
                draw.text((l_px, t_px), text, fill=color_rgb + (255,), font=font)

                dom_boxes[elem.id] = DOMBoundingBox(
                    element_id=elem.id,
                    role=elem.role,
                    left=float(l_px),
                    top=float(t_px),
                    right=float(r_px),
                    bottom=float(b_px),
                    width=float(bw),
                    height=float(bh),
                )

        # Draw QR code
        if spec.qr_code:
            qr_size = min(int(w * 0.12), 250)
            qr_left = w - qr_size - int(w * 0.05)
            qr_top = h - qr_size - int(h * 0.04)
            draw.rectangle(
                [(qr_left, qr_top), (qr_left + qr_size, qr_top + qr_size)],
                fill=(255, 255, 255, 255),
            )
            draw.text((qr_left + 20, qr_top + 40), "QR CODE", fill=(0, 0, 0, 255))
            dom_boxes["qr_code"] = DOMBoundingBox(
                element_id="qr_code",
                role="qr_code",
                left=float(qr_left),
                top=float(qr_top),
                right=float(qr_left + qr_size),
                bottom=float(qr_top + qr_size),
                width=float(qr_size),
                height=float(qr_size),
            )

        img.save(png_path, "PNG")
        if pdf_path:
            img.convert("RGB").save(pdf_path, "PDF")

        return dom_boxes

