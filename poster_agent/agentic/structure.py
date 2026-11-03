"""Locked structural zones for agentic poster design.

Emits deterministic institutional elements (logo header, legal footer bar, QR code)
before the LLM designer begins. These elements are flagged as locked items in the
VectorCraft MCP server so the designer cannot delete, move, or collide with them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from poster_agent.house_style import load_house_style, resolve_school
from poster_agent.ingestion.extractor import ExtractedBrief

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def generate_qr_code(payload: str, output_path: Path) -> Path:
    """Generate QR code PNG image."""
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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        return output_path
    except ImportError:
        # Fallback to minimal placeholder if qrcode is not installed
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (200, 200), "#FFFFFF")
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 190, 190], outline="#000000", width=4)
        draw.text((25, 90), "QR PLACEHOLDER", fill="#000000")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        return output_path


def lock_header_logo(
    server: Any,
    brief: ExtractedBrief,
    school_info: dict[str, Any],
    canvas_w: float,
    canvas_h: float,
    margin_x: float,
    margin_y: float,
) -> dict[str, Any]:
    """Emit and lock institutional logo at top of canvas."""
    school_logo = school_info.get("logo", "assets/logo_kumaraguru.png")
    logo_path = Path(school_logo)
    if not logo_path.is_absolute():
        logo_path = PROJECT_ROOT / logo_path

    logo_h = max(40.0, canvas_h * 0.035)
    logo_w = logo_h * 3.0
    logo_y = margin_y + 8.0
    logo_x = canvas_w - margin_x - logo_w # Top right

    # If logo file exists, place it locked
    if logo_path.exists():
        server.place_image(
            path=str(logo_path),
            rect=[logo_x, logo_y, logo_w, logo_h],
            role="logo",
            item_id="locked_header_logo",
            locked=True,
        )
    else:
        # Fallback solid placeholder container
        server.add_shape_rectangle(
            x=logo_x,
            y=logo_y,
            width=logo_w,
            height=logo_h,
            fill="#FFFFFF",
            radius=6.0,
            item_id="locked_header_logo",
            locked=True,
        )

    return {
        "id": "locked_header_logo",
        "rect": [logo_x, logo_y, logo_w, logo_h],
        "locked": True,
    }


def lock_footer_bar(
    server: Any,
    brief: ExtractedBrief,
    school_info: dict[str, Any],
    canvas_w: float,
    canvas_h: float,
) -> dict[str, Any]:
    """Emit and lock solid brand-color footer strip at bottom of canvas."""
    palette = school_info.get("palette", {})
    primary_color = palette.get("primary", "#1E2842")
    surface_color = palette.get("surface", "#FFFFFF")

    bar_h = max(68.0, canvas_h * 0.038)
    bar_y = canvas_h - bar_h

    # Locked footer rectangle
    server.add_shape_rectangle(
        x=0.0,
        y=bar_y,
        width=canvas_w,
        height=bar_h,
        fill=primary_color,
        item_id="locked_footer_rect",
        locked=True,
    )

    # Footer legal / organizer text
    footer_text = (
        brief.get_text("organizer")
        or school_info.get("name", "KUMARAGURU COLLEGE OF TECHNOLOGY")
    ).upper()

    font_display = school_info.get("fonts", {}).get("display", "Montserrat")
    text_sz = max(12.0, min(15.0, bar_h * 0.26))
    text_y = bar_y + (bar_h - text_sz) / 2.0

    server.add_text(
        text=footer_text,
        x=canvas_w * 0.5,
        y=text_y,
        size=text_sz,
        font=font_display,
        color=surface_color,
        role="footer",
        item_id="locked_footer_text",
        locked=True,
    )

    return {
        "id": "locked_footer_bar",
        "rect": [0.0, bar_y, canvas_w, bar_h],
        "locked": True,
    }


def lock_qr_code(
    server: Any,
    brief: ExtractedBrief,
    school_info: dict[str, Any],
    canvas_w: float,
    canvas_h: float,
    margin_x: float,
    margin_y: float,
    session_dir: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Emit and lock QR code block in the lower-right area above footer."""
    qr_payload = (
        getattr(brief, "asset_references", {}).get("qr_link")
        or brief.get_text("qr_link")
        or brief.get_text("qr_url")
    )
    if not qr_payload:
        return None

    out_dir = session_dir or (PROJECT_ROOT / "runs" / "qr_cache")
    qr_file = out_dir / "locked_qr.png"
    generate_qr_code(qr_payload, qr_file)

    qr_size = max(110.0, canvas_w * 0.12)
    bar_h = max(68.0, canvas_h * 0.038)
    qr_x = canvas_w - margin_x - qr_size
    qr_y = canvas_h - bar_h - qr_size - 32.0

    # Place QR image
    server.place_image(
        path=str(qr_file),
        rect=[qr_x, qr_y, qr_size, qr_size],
        role="qr",
        item_id="locked_qr_image",
        locked=True,
    )

    # QR label
    cta_text = brief.get_text("cta").upper() if brief.get_text("cta") else "SCAN TO REGISTER"
    font_body = school_info.get("fonts", {}).get("body", "Inter")
    server.add_text(
        text=cta_text,
        x=qr_x + (qr_size / 2.0),
        y=qr_y + qr_size + 10.0,
        size=11.0,
        font=font_body,
        color="#FFFFFF",
        role="cta",
        item_id="locked_qr_label",
        locked=True,
    )

    return {
        "id": "locked_qr",
        "rect": [qr_x, qr_y, qr_size, qr_size + 28.0],
        "locked": True,
    }


def lock_all_zones(
    server: Any,
    brief: ExtractedBrief,
    school_id: Optional[str] = None,
) -> dict[str, Any]:
    """Emit and lock all mandatory institutional zones into the server."""
    house_style = load_house_style()
    actual_school, school_info = resolve_school(brief, house_style=house_style)
    if school_id and school_id in house_style.get("schools", {}):
        actual_school = school_id
        school_info = house_style["schools"][school_id]

    cw = server.doc_width or 1080.0
    ch = server.doc_height or 1920.0
    margin_x = max(40.0, cw * 0.045)
    margin_y = max(40.0, ch * 0.03)

    header = lock_header_logo(server, brief, school_info, cw, ch, margin_x, margin_y)
    footer = lock_footer_bar(server, brief, school_info, cw, ch)
    session_dir = getattr(server, "session_dir", None)
    qr = lock_qr_code(server, brief, school_info, cw, ch, margin_x, margin_y, session_dir=session_dir)

    return {
        "school": actual_school,
        "header": header,
        "footer": footer,
        "qr": qr,
    }
