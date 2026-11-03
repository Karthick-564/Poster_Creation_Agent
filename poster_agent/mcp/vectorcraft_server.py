"""VectorCraft MCP Server: High-precision typography and layout engine over JSON-RPC 2.0.

Provides an interactive designer session interface for OpenCode and other MCP clients.
Features verbatim-validated typography authoring, instant pre-render QA gate measurement,
and blocked-honest export controls.
"""
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Optional

import numpy as np

from poster_agent.ingestion.extractor import BriefExtractor, ExtractedBrief
from poster_agent.qa.gates import (
    GateFailure,
    _get_bounds,
    _rgb_to_relative_luminance,
    check_canvas_bounds,
    check_dedupe,
    check_hero_overlap,
    check_required_content,
    check_row_overlap,
    check_v_band_coverage_gate,
)
from poster_agent.renderer.composer import estimate_text_width
from poster_agent.renderer.vectorcraft_renderer import VectorCraftRenderer


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Parse hex color string (#RGB, #RRGGBB) to (r, g, b) tuple."""
    h = str(hex_str).strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) >= 6:
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except ValueError:
            pass
    return (0, 0, 0)


class VectorCraftMCPServer:
    """In-memory VectorCraft MCP Server managing an interactive poster design session."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        base_dir: Optional[Path] = None,
    ):
        self.project_root = (base_dir or Path.cwd()).resolve()
        self.session_id = session_id or f"mcp_session_{int(time.time())}"
        self.session_dir = self.project_root / "runs" / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.renderer = VectorCraftRenderer()
        self.brief: Optional[ExtractedBrief] = None
        self.raw_brief: str = ""
        self.doc_width: Optional[float] = None
        self.doc_height: Optional[float] = None
        self.hero_rect: Optional[tuple[float, float, float, float]] = None
        self.manifest_rows: list[dict[str, Any]] = []
        self.items: dict[str, dict[str, Any]] = {}
        self.last_measure_result: Optional[dict[str, Any]] = None
        self.tool_call_history: list[dict[str, Any]] = []

    def _rel(self, p: Path) -> str:
        """Format path relative to project root safely across drive letters."""
        try:
            return str(p.relative_to(self.project_root))
        except ValueError:
            return str(p)

    # -------------------------------------------------------------------------
    # Tool Implementations
    # -------------------------------------------------------------------------

    def create_doc(self, width: float, height: float) -> dict[str, Any]:
        """Start a fresh document buffer with dimensions and persist initial session.vcs."""
        self.doc_width = float(width)
        self.doc_height = float(height)
        self.manifest_rows.clear()
        self.items.clear()
        self.last_measure_result = None
        self.hero_rect = None

        self.renderer.clear()
        self.renderer.new_document(width=self.doc_width, height=self.doc_height)

        initial_vcs = self.session_dir / "session.vcs"
        self.renderer.save_session(
            initial_vcs,
            metadata={"session_id": self.session_id, "doc_width": self.doc_width, "doc_height": self.doc_height},
        )

        return {
            "status": "ok",
            "doc_width": self.doc_width,
            "doc_height": self.doc_height,
            "session_file": self._rel(initial_vcs),
        }

    def load_brief(self, path: str) -> dict[str, Any]:
        """Ingest a brief file and lock verbatim fields into session memory."""
        p = Path(path)
        if not p.is_absolute():
            p = self.project_root / p
        p = p.resolve()

        if not p.exists():
            return {"error": f"FileNotFoundError: Brief file not found at '{path}'"}

        try:
            p.relative_to(self.project_root)
        except ValueError:
            return {"error": f"SecurityError: Brief path '{path}' is outside project root."}

        content = p.read_text(encoding="utf-8")
        self.raw_brief = content
        extractor = BriefExtractor()
        self.brief = extractor.extract(content)

        return {
            "status": "ok",
            "path": self._rel(p),
            "field_count": len(self.brief.fields),
            "fields": sorted(list(self.brief.fields.keys())),
        }

    def _validate_verbatim(self, text: str) -> Optional[dict[str, Any]]:
        """Validate text string against loaded brief whole-tokens. Returns error dict if invalid, None if valid."""
        if self.brief is None:
            return {
                "error": f"VerbatimValidationError: '{text}' does not appear in loaded brief (no brief loaded)"
            }

        text_clean = text.strip()
        if not text_clean:
            return {"error": "VerbatimValidationError: Empty text string is invalid"}

        brief_raw = self.raw_brief
        fields = list(self.brief.fields.values())
        unmapped = list(getattr(self.brief, "unmapped_lines", []))

        def matches_whole_tokens(cand: str, target: str) -> bool:
            cand_norm = " ".join(cand.strip().lower().split())
            target_norm = " ".join(target.strip().lower().split())
            if not cand_norm or not target_norm:
                return False
            if cand_norm == target_norm:
                return True
            pattern = r"(?<!\w)" + re.escape(cand_norm) + r"(?!\w)"
            return bool(re.search(pattern, target_norm))

        def candidate_in_sources(cand: str) -> bool:
            if matches_whole_tokens(cand, brief_raw):
                return True
            if any(matches_whole_tokens(cand, f.text) for f in fields):
                return True
            if any(matches_whole_tokens(cand, u) for u in unmapped):
                return True
            return False

        norm_space_text = " ".join(text_clean.split())
        matched = candidate_in_sources(norm_space_text)

        if not matched and "\n" in text_clean:
            lines = [l.strip() for l in text_clean.split("\n") if l.strip()]
            matched = bool(lines) and all(candidate_in_sources(l) for l in lines)

        if not matched:
            return {
                "error": f"VerbatimValidationError: '{text}' does not appear in loaded brief"
            }
        return None

    def _rebuild_commands(self) -> None:
        """Synchronize the command buffer and manifest from the single source of truth (self.items)."""
        self.renderer.clear()
        self.renderer.new_document(width=self.doc_width or 1080.0, height=self.doc_height or 1920.0)
        self.manifest_rows.clear()
        self.hero_rect = None

        for idx, (item_id, item) in enumerate(self.items.items()):
            item["z_order"] = idx
            itype = item.get("type")
            p = item.get("params", {})
            if itype == "text":
                baseline_y = float(p["y"]) + float(p["size"]) * 0.78
                self.renderer.add_text(
                    text=p["text"],
                    x=float(p["x"]),
                    y=baseline_y,
                    size=float(p["size"]),
                    font=p.get("font", "Arial"),
                    style=p.get("style", ""),
                    color=p.get("color", "#000000"),
                    role=p.get("role", "text"),
                )
                self.manifest_rows.append({
                    "id": item_id,
                    "role": p.get("role", "text"),
                    "text": p["text"],
                    "x": float(item["rect"][0]),
                    "y": float(item["rect"][1]),
                    "width": float(item["rect"][2]),
                    "height": float(item["rect"][3]),
                    "bounds": {
                        "x": float(item["rect"][0]),
                        "y": float(item["rect"][1]),
                        "width": float(item["rect"][2]),
                        "height": float(item["rect"][3]),
                    },
                    "size": float(p["size"]),
                    "font": p.get("font", "Arial"),
                    "style": p.get("style", ""),
                    "color": p.get("color", "#000000"),
                    "locked": bool(item.get("locked", False)),
                })
            elif itype == "rectangle":
                self.renderer.add_shape_rectangle(
                    x=float(p["x"]),
                    y=float(p["y"]),
                    width=float(p["width"]),
                    height=float(p["height"]),
                    fill=p.get("fill"),
                    stroke=p.get("stroke"),
                    stroke_width=float(p.get("stroke_width", 0.0)),
                    radius=float(p.get("radius", 0.0)),
                )
            elif itype == "ellipse":
                self.renderer.add_shape_ellipse(
                    x=float(p["x"]),
                    y=float(p["y"]),
                    width=float(p["width"]),
                    height=float(p["height"]),
                    fill=p.get("fill"),
                    stroke=p.get("stroke"),
                    stroke_width=float(p.get("stroke_width", 0.0)),
                    rotation=float(p.get("rotation", 0.0)),
                )
            elif itype == "image":
                rect = p.get("rect")
                self.renderer.place_image(
                    path=p["path"],
                    rect=rect,
                )
                if p.get("blend_mode"):
                    self.renderer.commands.append({"command": "transparency.set", "params": {"blend": p["blend_mode"]}})
                if p.get("feather_radius") and float(p["feather_radius"]) > 0:
                    self.renderer.add_effect(effect_name="stylize.feather", params={"radius": float(p["feather_radius"])})
                if p.get("role") == "hero" and rect and len(rect) == 4:
                    self.hero_rect = (float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]))
            elif itype == "scrim":
                self.renderer.soft_scrim(
                    x=float(p["x"]),
                    y=float(p["y"]),
                    width=float(p["width"]),
                    height=float(p["height"]),
                    stops=p.get("stops"),
                    direction=p.get("direction", "to_bottom"),
                )
            elif itype == "radial_light":
                eff_radius = float(p.get("radius", 200.0))
                self.renderer.radial_light(
                    cx=float(p["cx"]),
                    cy=float(p["cy"]),
                    radius=eff_radius,
                    color=p.get("color", "#00F5D4"),
                    alpha_stop_inner=float(p.get("opacity", 0.8)),
                    alpha_stop_outer=0.0,
                )
            elif itype == "path":
                self.renderer.add_path(
                    d=p["d"],
                    fill=p.get("fill"),
                    stroke=p.get("stroke"),
                    stroke_width=float(p.get("stroke_width", 0.0)),
                    closed=p.get("closed", True),
                )

        self.save_session()

    def add_text(
        self,
        text: str,
        x: float,
        y: float,
        size: float,
        font: str = "Arial",
        style: str = "",
        color: str = "#000000",
        role: str = "text",
        item_id: Optional[str] = None,
        locked: bool = False,
    ) -> dict[str, Any]:
        """Add text command with strict verbatim brief validation."""
        val_err = self._validate_verbatim(text)
        if val_err:
            return val_err

        text_clean = text.strip()
        actual_id = item_id or f"{role}_{len(self.items) + 1}"

        if "\n" in text_clean:
            lines = [l for l in text_clean.split("\n") if l.strip()]
            est_w = max((estimate_text_width(l, size, font=font) for l in lines), default=0.0)
            est_h = len(lines) * float(size) * 1.15
        else:
            est_w = estimate_text_width(text_clean, size, font=font)
            est_h = float(size) * 1.15

        rect = [float(x), float(y), float(est_w), float(est_h)]

        self.items[actual_id] = {
            "id": actual_id,
            "type": "text",
            "rect": rect,
            "text": text_clean,
            "z_order": len(self.items),
            "locked": bool(locked),
            "role": role,
            "params": {
                "text": text_clean,
                "x": float(x),
                "y": float(y),
                "size": float(size),
                "font": font,
                "style": style,
                "color": color,
                "role": role,
            },
        }

        self._rebuild_commands()

        row = next((r for r in self.manifest_rows if r["id"] == actual_id), {
            "id": actual_id,
            "bounds": {"x": float(x), "y": float(y), "width": float(est_w), "height": float(est_h)},
        })

        return {
            "status": "ok",
            "item_id": actual_id,
            "row_id": actual_id,
            "bounds": row.get("bounds", {"x": float(x), "y": float(y), "width": float(est_w), "height": float(est_h)}),
            "command_count": len(self.renderer.commands),
            "locked": bool(locked),
        }

    def add_shape_rectangle(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: Optional[str] = None,
        stroke: Optional[str] = None,
        stroke_width: float = 0.0,
        radius: float = 0.0,
        item_id: Optional[str] = None,
        locked: bool = False,
    ) -> dict[str, Any]:
        """Add rectangle shape with fill or stroke styling."""
        actual_id = item_id or f"rect_{len(self.items) + 1}"
        rect = [float(x), float(y), float(width), float(height)]

        self.items[actual_id] = {
            "id": actual_id,
            "type": "rectangle",
            "rect": rect,
            "text": None,
            "z_order": len(self.items),
            "locked": bool(locked),
            "params": {
                "x": float(x),
                "y": float(y),
                "width": float(width),
                "height": float(height),
                "fill": fill,
                "stroke": stroke,
                "stroke_width": float(stroke_width),
                "radius": float(radius),
            },
        }

        self._rebuild_commands()

        return {
            "status": "ok",
            "item_id": actual_id,
            "rect": rect,
            "fill": fill,
            "locked": bool(locked),
            "command_count": len(self.renderer.commands),
        }

    def place_image(
        self,
        path: str,
        rect: Optional[list[float]] = None,
        blend_mode: Optional[str] = None,
        feather_radius: Optional[float] = None,
        role: str = "image",
        item_id: Optional[str] = None,
        locked: bool = False,
    ) -> dict[str, Any]:
        """Place image command and validate path is within project root."""
        p = Path(path)
        if not p.is_absolute():
            p = self.project_root / p
        p = p.resolve()

        try:
            p.relative_to(self.project_root)
        except ValueError:
            return {"error": f"SecurityError: Image path '{path}' is outside project root."}

        if not p.exists():
            return {"error": f"FileNotFoundError: Image file not found at '{path}'"}

        actual_id = item_id or (role if role in ("hero", "logo", "background") and role not in self.items else f"image_{len(self.items) + 1}")
        actual_rect = [float(c) for c in rect] if (rect and len(rect) == 4) else [0.0, 0.0, self.doc_width or 1080.0, self.doc_height or 1920.0]

        self.items[actual_id] = {
            "id": actual_id,
            "type": "image",
            "rect": actual_rect,
            "text": None,
            "z_order": len(self.items),
            "locked": bool(locked),
            "role": role,
            "params": {
                "path": str(p),
                "rect": actual_rect,
                "blend_mode": blend_mode,
                "feather_radius": feather_radius,
                "role": role,
            },
        }

        self._rebuild_commands()

        return {
            "status": "ok",
            "item_id": actual_id,
            "image_path": self._rel(p),
            "rect": actual_rect,
            "blend_mode": blend_mode,
            "feather_radius": feather_radius,
            "role": role,
            "locked": bool(locked),
            "command_count": len(self.renderer.commands),
        }

    def add_shape_ellipse(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: Optional[str] = None,
        stroke: Optional[str] = None,
        stroke_width: float = 0.0,
        rotation: float = 0.0,
        item_id: Optional[str] = None,
        locked: bool = False,
    ) -> dict[str, Any]:
        """Add ellipse or circle shape with fill/stroke styling."""
        actual_id = item_id or f"ellipse_{len(self.items) + 1}"
        rect = [float(x), float(y), float(width), float(height)]

        self.items[actual_id] = {
            "id": actual_id,
            "type": "ellipse",
            "rect": rect,
            "text": None,
            "z_order": len(self.items),
            "locked": bool(locked),
            "params": {
                "x": float(x),
                "y": float(y),
                "width": float(width),
                "height": float(height),
                "fill": fill,
                "stroke": stroke,
                "stroke_width": float(stroke_width),
                "rotation": float(rotation),
            },
        }

        self._rebuild_commands()

        return {
            "status": "ok",
            "item_id": actual_id,
            "ellipse": rect,
            "fill": fill,
            "locked": bool(locked),
            "command_count": len(self.renderer.commands),
        }

    def add_path(
        self,
        d: str,
        fill: Optional[str] = None,
        stroke: Optional[str] = None,
        stroke_width: float = 0.0,
        closed: bool = True,
        item_id: Optional[str] = None,
        locked: bool = False,
    ) -> dict[str, Any]:
        """Add custom vector path via SVG path data."""
        actual_id = item_id or f"path_{len(self.items) + 1}"
        rect = [0.0, 0.0, self.doc_width or 1080.0, self.doc_height or 1920.0]

        self.items[actual_id] = {
            "id": actual_id,
            "type": "path",
            "rect": rect,
            "text": None,
            "z_order": len(self.items),
            "locked": bool(locked),
            "params": {
                "d": d,
                "fill": fill,
                "stroke": stroke,
                "stroke_width": float(stroke_width),
                "closed": closed,
            },
        }

        self._rebuild_commands()

        return {
            "status": "ok",
            "item_id": actual_id,
            "d": d,
            "fill": fill,
            "locked": bool(locked),
            "command_count": len(self.renderer.commands),
        }

    def set_transparency(
        self,
        opacity: float = 1.0,
        blend: str = "normal",
        target_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Set opacity and blend mode on the active selection or target node."""
        params: dict[str, Any] = {"opacity": float(opacity), "blend": blend}
        if target_id is not None:
            params["id"] = target_id
        self.renderer.commands.append({"command": "transparency.set", "params": params})
        self.save_session()
        return {
            "status": "ok",
            "opacity": float(opacity),
            "blend": blend,
            "command_count": len(self.renderer.commands),
        }

    def add_effect(
        self,
        effect: str,
        params: Optional[dict[str, Any]] = None,
        target_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Attach a live raster or vector effect (e.g. stylize.dropShadow, stylize.feather, texture.grain)."""
        self.renderer.add_effect(effect_name=effect, params=params, target_id=target_id)
        self.save_session()
        return {
            "status": "ok",
            "effect": effect,
            "params": params or {},
            "command_count": len(self.renderer.commands),
        }

    def soft_scrim(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        stops: Optional[list[Any]] = None,
        direction: str = "to_bottom",
        item_id: Optional[str] = None,
        locked: bool = False,
    ) -> dict[str, Any]:
        """Append atmospheric gradient scrim command."""
        parsed_stops = []
        if stops:
            for s in stops:
                if isinstance(s, (list, tuple)) and len(s) == 3:
                    parsed_stops.append((float(s[0]), str(s[1]), float(s[2])))

        actual_id = item_id or f"scrim_{len(self.items) + 1}"
        rect = [float(x), float(y), float(width), float(height)]

        self.items[actual_id] = {
            "id": actual_id,
            "type": "scrim",
            "rect": rect,
            "text": None,
            "z_order": len(self.items),
            "locked": bool(locked),
            "params": {
                "x": float(x),
                "y": float(y),
                "width": float(width),
                "height": float(height),
                "stops": parsed_stops or None,
                "direction": direction,
            },
        }

        self._rebuild_commands()

        return {
            "status": "ok",
            "item_id": actual_id,
            "scrim": {"x": x, "y": y, "width": width, "height": height, "direction": direction},
            "locked": bool(locked),
            "command_count": len(self.renderer.commands),
        }

    def radial_light(
        self,
        cx: float,
        cy: float,
        rx: Optional[float] = None,
        ry: Optional[float] = None,
        radius: Optional[float] = None,
        color: str = "#00F5D4",
        opacity: float = 0.8,
        item_id: Optional[str] = None,
        locked: bool = False,
    ) -> dict[str, Any]:
        """Append radial light glow command."""
        eff_radius = float(radius) if radius is not None else max(float(rx or 200.0), float(ry or 200.0))
        actual_id = item_id or f"light_{len(self.items) + 1}"
        rect = [float(cx - eff_radius), float(cy - eff_radius), float(2 * eff_radius), float(2 * eff_radius)]

        self.items[actual_id] = {
            "id": actual_id,
            "type": "radial_light",
            "rect": rect,
            "text": None,
            "z_order": len(self.items),
            "locked": bool(locked),
            "params": {
                "cx": float(cx),
                "cy": float(cy),
                "radius": eff_radius,
                "color": color,
                "opacity": float(opacity),
            },
        }

        self._rebuild_commands()

        return {
            "status": "ok",
            "item_id": actual_id,
            "radial_light": {"cx": cx, "cy": cy, "radius": eff_radius, "color": color},
            "locked": bool(locked),
            "command_count": len(self.renderer.commands),
        }

    # -------------------------------------------------------------------------
    # Item Management & Space Inspection (Agentic Designer)
    # -------------------------------------------------------------------------

    def list_items(self) -> dict[str, Any]:
        """Return every placed element on the artboard with id, type, rect, text, z_order, and locked status."""
        items_list = []
        for it in self.items.values():
            entry = {
                "id": it["id"],
                "type": it["type"],
                "rect": it["rect"],
                "text": it.get("text"),
                "z_order": it.get("z_order", 0),
                "locked": bool(it.get("locked", False)),
            }
            if it.get("role"):
                entry["role"] = it["role"]
            items_list.append(entry)
        return {
            "status": "ok",
            "count": len(items_list),
            "items": items_list,
        }

    def update_item(self, id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Move, resize, restyle, or edit an existing item. Refuses locked items. Verbatim check applies if text changes."""
        if id not in self.items:
            return {"error": f"ItemNotFoundError: Item '{id}' does not exist"}
        item = self.items[id]
        if item.get("locked"):
            return {"error": f"LockedItemError: Item '{id}' is locked and cannot be modified"}

        itype = item["type"]
        params = item["params"]

        # Verbatim brief check if text is changing
        if "text" in fields and itype == "text":
            new_text = str(fields["text"])
            val_res = self._validate_verbatim(new_text)
            if val_res is not None:
                return val_res
            params["text"] = new_text
            item["text"] = new_text

        # Update properties
        for k in (
            "x", "y", "size", "font", "style", "color", "role",
            "width", "height", "fill", "stroke", "stroke_width",
            "radius", "rotation", "blend_mode", "rect", "stops", "direction"
        ):
            if k in fields:
                params[k] = fields[k]

        # Recalculate item bounding box rect
        if itype == "text":
            cur_text = params["text"]
            cur_size = float(params.get("size", 16.0))
            cur_font = params.get("font", "Arial")
            cur_x = float(params.get("x", 0.0))
            cur_y = float(params.get("y", 0.0))
            if "\n" in cur_text:
                lines = [l.strip() for l in cur_text.split("\n") if l.strip()]
                est_w = max((estimate_text_width(l, cur_size, font=cur_font) for l in lines), default=0.0)
                est_h = len(lines) * cur_size * 1.15
            else:
                est_w = estimate_text_width(cur_text, cur_size, font=cur_font)
                est_h = cur_size * 1.15
            item["rect"] = [cur_x, cur_y, float(est_w), float(est_h)]
        elif itype in ("rectangle", "scrim"):
            item["rect"] = [float(params["x"]), float(params["y"]), float(params["width"]), float(params["height"])]
        elif itype == "image" and "rect" in params and params["rect"]:
            item["rect"] = [float(c) for c in params["rect"]]
        elif itype == "radial_light":
            cx = float(params["cx"])
            cy = float(params["cy"])
            r = float(params.get("radius", 200.0))
            item["rect"] = [cx - r, cy - r, 2 * r, 2 * r]

        self._rebuild_commands()
        return {
            "status": "ok",
            "item": {
                "id": item["id"],
                "type": item["type"],
                "rect": item["rect"],
                "text": item.get("text"),
                "z_order": item.get("z_order", 0),
                "locked": item.get("locked", False),
            },
        }

    def delete_item(self, id: str) -> dict[str, Any]:
        """Delete an item from canvas. Refuses locked items."""
        if id not in self.items:
            return {"error": f"ItemNotFoundError: Item '{id}' does not exist"}
        item = self.items[id]
        if item.get("locked"):
            return {"error": f"LockedItemError: Item '{id}' is locked and cannot be deleted"}
        del self.items[id]
        self._rebuild_commands()
        return {"status": "ok", "deleted_id": id}

    def get_free_regions(self, min_width: float = 160.0, min_height: float = 40.0) -> dict[str, Any]:
        """Calculate calm/unoccupied rectangular regions within safe margins, treating locked zones and placed items as obstacles."""
        cw = self.doc_width or 1080.0
        ch = self.doc_height or 1920.0
        margin_px = max(40.0, cw * 0.045)
        safe_left = margin_px
        safe_right = cw - margin_px
        safe_top = margin_px
        safe_bottom = ch - margin_px

        # Collect obstacles: locked zones, text rows, hero image, and placed shape cards
        obstacles = []
        for it in self.items.values():
            r = it.get("rect")
            if not r or len(r) != 4:
                continue
            rx, ry, rw, rh = float(r[0]), float(r[1]), float(r[2]), float(r[3])
            # Full-bleed canvas background or ambient soft scrims are background atmosphere, not physical obstacles
            if rw >= cw * 0.95 and rh >= ch * 0.95 and it["type"] in ("image", "rectangle", "scrim") and not it.get("locked"):
                continue
            if rw <= 0 or rh <= 0:
                continue
            obstacles.append((rx, ry, rw, rh))

        # Y slice boundaries
        y_cuts = {safe_top, safe_bottom}
        for ox, oy, ow, oh in obstacles:
            top = max(safe_top, oy)
            bottom = min(safe_bottom, oy + oh)
            if safe_top <= top <= safe_bottom:
                y_cuts.add(top)
            if safe_top <= bottom <= safe_bottom:
                y_cuts.add(bottom)
        sorted_y = sorted(list(y_cuts))

        free_rects = []
        for i in range(len(sorted_y) - 1):
            y0 = sorted_y[i]
            y1 = sorted_y[i + 1]
            band_h = y1 - y0
            if band_h < min_height:
                continue

            # X blocked intervals in this band
            x_blocked = []
            for ox, oy, ow, oh in obstacles:
                if not (y1 <= oy or y0 >= oy + oh):
                    x_start = max(safe_left, ox)
                    x_end = min(safe_right, ox + ow)
                    if x_start < x_end:
                        x_blocked.append((x_start, x_end))

            if not x_blocked:
                free_rects.append((safe_left, y0, safe_right - safe_left, band_h))
            else:
                x_blocked.sort(key=lambda b: b[0])
                merged = []
                curr_s, curr_e = x_blocked[0]
                for s, e in x_blocked[1:]:
                    if s <= curr_e:
                        curr_e = max(curr_e, e)
                    else:
                        merged.append((curr_s, curr_e))
                        curr_s, curr_e = s, e
                merged.append((curr_s, curr_e))

                last_x = safe_left
                for s, e in merged:
                    if s - last_x >= min_width:
                        free_rects.append((last_x, y0, s - last_x, band_h))
                    last_x = max(last_x, e)
                if safe_right - last_x >= min_width:
                    free_rects.append((last_x, y0, safe_right - last_x, band_h))

        # Merge vertically adjacent free rectangles with identical horizontal footprint
        merged_rects = []
        free_rects.sort(key=lambda r: (round(r[0], 1), round(r[2], 1), round(r[1], 1)))
        for r in free_rects:
            if merged_rects:
                prev_x, prev_y, prev_w, prev_h = merged_rects[-1]
                if abs(prev_x - r[0]) < 1.0 and abs(prev_w - r[2]) < 1.0 and abs((prev_y + prev_h) - r[1]) < 1.0:
                    merged_rects[-1] = (prev_x, prev_y, prev_w, prev_h + r[3])
                    continue
            merged_rects.append(r)

        regions = [
            {
                "x": round(r[0], 1),
                "y": round(r[1], 1),
                "width": round(r[2], 1),
                "height": round(r[3], 1),
                "area": round(r[2] * r[3], 1),
            }
            for r in merged_rects
            if r[2] >= min_width and r[3] >= min_height
        ]
        regions.sort(key=lambda rg: rg["area"], reverse=True)

        return {
            "status": "ok",
            "free_region_count": len(regions),
            "canvas_size": [cw, ch],
            "safe_margin": margin_px,
            "obstacle_count": len(obstacles),
            "free_regions": regions,
        }

    def _get_local_background(self, row: dict[str, Any]) -> str:
        """Find local background color covering text row from command buffer."""
        rect_elements = []
        curr_fill = None
        for cmd in self.renderer.commands:
            c_name = cmd.get("command")
            params = cmd.get("params", {})
            if c_name == "paint.setFill":
                if "color" in params:
                    curr_fill = params["color"]
                elif "gradient" in params and "stops" in params["gradient"]:
                    stops = params["gradient"]["stops"]
                    if stops:
                        curr_fill = stops[0].get("color")
            elif c_name == "paint.none":
                curr_fill = None
            elif c_name == "shape.rectangle" and curr_fill:
                rx = float(params.get("x", 0.0))
                ry = float(params.get("y", 0.0))
                rw = float(params.get("width", 0.0))
                rh = float(params.get("height", 0.0))
                rect_elements.append({"x": rx, "y": ry, "w": rw, "h": rh, "color": curr_fill})

        # Text centroid
        rx, ry, rw, rh = _get_bounds(row)
        cx = rx + rw / 2.0
        cy = ry + rh / 2.0

        for r in reversed(rect_elements):
            if (r["x"] <= cx <= (r["x"] + r["w"])) and (r["y"] <= cy <= (r["y"] + r["h"])):
                return r["color"]

        return "#FFFFFF"

    def measure(self) -> dict[str, Any]:
        """Evaluate Phase-D deterministic QA gates without raster rendering."""
        cw = self.doc_width or 1080.0
        ch = self.doc_height or 1920.0
        margin_px = max(40.0, cw * 0.045)

        failures = []

        # 1. Canvas Bounds
        failures.extend(check_canvas_bounds(self.manifest_rows, canvas_w=cw, canvas_h=ch, margin_px=margin_px))

        # 2. Row Overlap
        failures.extend(check_row_overlap(self.manifest_rows))

        # 3. Hero Overlap
        if self.hero_rect:
            failures.extend(check_hero_overlap(self.manifest_rows, hero_rect=self.hero_rect))

        # 4. Dedupe
        failures.extend(check_dedupe(self.manifest_rows))

        # 5. Required Content
        if self.brief or self.raw_brief:
            failures.extend(check_required_content(self.manifest_rows, brief=self.brief, brief_text=self.raw_brief))

        # 6. Vertical Band Coverage
        _, cov_pct, _, cov_failures = check_v_band_coverage_gate(self.manifest_rows, canvas_h=ch, min_coverage=70.0)
        failures.extend(cov_failures)

        # 7. Composition-time Contrast Gate (Pure Math on text_color vs local_bg)
        contrast_failures = []
        for r in self.manifest_rows:
            target_id = str(r.get("id", r.get("role", "text")))
            tc = str(r.get("color", "#000000"))
            local_bg = self._get_local_background(r)

            arr_fg = np.array([[[c for c in _hex_to_rgb(tc)]]], dtype=np.float32)
            arr_bg = np.array([[[c for c in _hex_to_rgb(local_bg)]]], dtype=np.float32)
            l_fg = float(_rgb_to_relative_luminance(arr_fg)[0, 0])
            l_bg = float(_rgb_to_relative_luminance(arr_bg)[0, 0])

            l_max = max(l_fg, l_bg)
            l_min = min(l_fg, l_bg)
            cr = (l_max + 0.05) / (l_min + 0.05)

            sz = float(r.get("size", 16.0))
            sty = str(r.get("style", "")).lower()
            is_large = (sz >= 24.0) or (sz >= 18.0 and ("bold" in sty or "black" in sty))
            threshold = 3.0 if is_large else 4.5

            if cr < threshold:
                contrast_failures.append(GateFailure(
                    kind="contrast",
                    target=target_id,
                    detail=f"Low contrast for {'large' if is_large else 'body'} text '{str(r.get('text', ''))[:24]}': CR {cr:.2f}:1 < {threshold:.1f}:1 against background {local_bg}",
                    measured={
                        "contrast_ratio": round(cr, 2),
                        "threshold": threshold,
                        "is_large_text": is_large,
                        "text_size": sz,
                        "text_color": tc,
                        "bg_color": local_bg,
                        "L_fg": round(l_fg, 4),
                        "L_bg": round(l_bg, 4),
                    },
                ))
        failures.extend(contrast_failures)

        fail_dicts = [f.to_dict() if hasattr(f, "to_dict") else f for f in failures]
        score = round(max(0.0, 10.0 - (len(failures) * 1.5)), 2)
        passed = len(failures) == 0

        self.last_measure_result = {
            "passed": passed,
            "failure_count": len(failures),
            "failures": fail_dicts,
            "score": score,
            "v_band_coverage_pct": round(cov_pct, 1),
        }
        return self.last_measure_result

    def render_preview(self, scale: float = 0.5) -> dict[str, Any]:
        """Render fast raster preview image via VectorCraft CLI."""
        preview_path = self.session_dir / "preview.png"
        if not self.renderer.cli_path.exists():
            return {
                "status": "skipped",
                "preview_path": None,
                "reason": f"VectorCraft CLI binary not present at {self.renderer.cli_path}",
            }
        res = self.renderer.execute(output_png=preview_path, scale=float(scale))
        if not res.success:
            return {"error": f"VectorCraftPreviewFailed: {res.error_message or 'Unknown preview render error'}"}

        rel_path = self._rel(preview_path)
        return {
            "status": "ok",
            "preview_path": rel_path,
            "scale": scale,
            "command_count": len(self.renderer.commands),
            "execution_time_sec": res.execution_time_sec,
        }

    def save_session(self, path: Optional[str] = None) -> dict[str, Any]:
        """Export current command buffer and typography manifest as .vcs file."""
        if path:
            target = Path(path)
            if not target.is_absolute():
                target = self.project_root / target
        else:
            target = self.session_dir / "session.vcs"

        meta = {
            "session_id": self.session_id,
            "doc_width": self.doc_width,
            "doc_height": self.doc_height,
            "manifest_rows": self.manifest_rows,
            "items": self.items,
            "hero_rect": self.hero_rect,
        }
        self.renderer.hero_rect = self.hero_rect
        p = self.renderer.save_session(target, metadata=meta)
        return {
            "status": "ok",
            "session_path": self._rel(p),
            "command_count": len(self.renderer.commands),
        }

    def load_session(self, path: str) -> dict[str, Any]:
        """Restore document buffer and typography manifest from a .vcs file."""
        p = Path(path)
        if not p.is_absolute():
            p = self.project_root / p
        p = p.resolve()

        if not p.exists():
            return {"error": f"FileNotFoundError: Session file '{path}' does not exist"}

        loaded = VectorCraftRenderer.load_session(p)
        self.renderer = loaded
        self.doc_width = loaded.doc_width
        self.doc_height = loaded.doc_height
        self.hero_rect = loaded.hero_rect

        # Reconstruct manifest_rows and items from loaded session metadata
        self.manifest_rows.clear()
        self.items.clear()
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_manifest = data.get("metadata", {}).get("manifest_rows", [])
            if saved_manifest:
                self.manifest_rows = list(saved_manifest)
            saved_items = data.get("metadata", {}).get("items", {})
            if saved_items:
                self.items = dict(saved_items)
        except Exception:
            pass

        if not self.manifest_rows:
            # Fall back to deriving from queued texts
            for idx, qt in enumerate(loaded._queued_texts):
                txt = qt.get("text", "")
                sz = float(qt.get("size", 12.0))
                fnt = qt.get("font", "Arial")
                rl = qt.get("role", "text")
                w = estimate_text_width(txt, sz, font=fnt)
                h = sz * 1.15
                self.manifest_rows.append({
                    "id": f"{rl}_{idx+1}",
                    "role": rl,
                    "text": txt,
                    "x": 40.0,
                    "y": 40.0 + idx * (h + 10.0),
                    "width": w,
                    "height": h,
                    "bounds": {"x": 40.0, "y": 40.0 + idx * (h + 10.0), "width": w, "height": h},
                    "size": sz,
                    "font": fnt,
                    "style": qt.get("style", ""),
                    "color": "#000000",
                })

        self.last_measure_result = None
        return {
            "status": "ok",
            "session_path": self._rel(p),
            "command_count": len(self.renderer.commands),
            "doc_width": self.doc_width,
            "doc_height": self.doc_height,
        }

    def export(self, output_png: str, output_pdf: Optional[str] = None) -> dict[str, Any]:
        """Final render execution. BLOCKED with typed error unless measure() passes with 0 failed gates."""
        if self.last_measure_result is None:
            return {
                "error": "ExportBlockedError: Cannot export poster: measure() has not been run. Run measure() before export."
            }

        if not self.last_measure_result.get("passed", False):
            fc = self.last_measure_result.get("failure_count", 0)
            return {
                "error": f"ExportBlockedError: Cannot export poster: layout has {fc} failing QA gates. Resolve all gates with measure() before export."
            }

        png_p = Path(output_png)
        if not png_p.is_absolute():
            png_p = self.project_root / png_p
        png_p.parent.mkdir(parents=True, exist_ok=True)

        pdf_p = None
        if output_pdf:
            pdf_p = Path(output_pdf)
            if not pdf_p.is_absolute():
                pdf_p = self.project_root / pdf_p
            pdf_p.parent.mkdir(parents=True, exist_ok=True)

        res = self.renderer.execute(output_png=png_p, output_pdf=pdf_p, scale=1.0)
        if not res.success:
            return {"error": f"VectorCraftExportFailed: {res.error_message or 'Export rendering failed'}"}

        self.save_session()
        return {
            "status": "ok",
            "output_png": self._rel(png_p),
            "output_pdf": self._rel(pdf_p) if pdf_p else None,
            "score": self.last_measure_result.get("score", 10.0),
            "command_count": len(self.renderer.commands),
            "execution_time_sec": res.execution_time_sec,
        }

    # -------------------------------------------------------------------------
    # Tool Schemas & Dispatcher
    # -------------------------------------------------------------------------

    @classmethod
    def get_tool_definitions(cls) -> list[dict[str, Any]]:
        return [
            {
                "name": "create_doc",
                "description": "Initialize a fresh poster artboard with width and height in points.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "number", "description": "Document width in points (e.g. 1080)"},
                        "height": {"type": "number", "description": "Document height in points (e.g. 1920)"},
                    },
                    "required": ["width", "height"],
                },
            },
            {
                "name": "load_brief",
                "description": "Ingest and lock brief verbatim strings into session memory.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to brief file relative to project root"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "add_shape_rectangle",
                "description": "Add rectangle shape (e.g. background fill or card) with fill/stroke styling.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "width": {"type": "number"},
                        "height": {"type": "number"},
                        "fill": {"type": "string", "description": "Hex fill color string (e.g. #070B19)"},
                        "stroke": {"type": "string", "description": "Hex stroke color string"},
                        "stroke_width": {"type": "number", "default": 0.0},
                        "radius": {"type": "number", "default": 0.0},
                    },
                    "required": ["x", "y", "width", "height"],
                },
            },
            {
                "name": "add_text",
                "description": "Add typographic text with strict brief verbatim validation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Verbatim text string from loaded brief"},
                        "x": {"type": "number", "description": "X coordinate in points"},
                        "y": {"type": "number", "description": "Y coordinate in points"},
                        "size": {"type": "number", "description": "Font size in points"},
                        "font": {"type": "string", "description": "Font family name", "default": "Arial"},
                        "style": {"type": "string", "description": "Font style variant (e.g. Bold, Regular)", "default": ""},
                        "color": {"type": "string", "description": "Hex color string (e.g. #FFFFFF)", "default": "#000000"},
                        "role": {"type": "string", "description": "Semantic role (headline, subtitle, date, venue, footer)", "default": "text"},
                    },
                    "required": ["text", "x", "y", "size"],
                },
            },
            {
                "name": "place_image",
                "description": "Place a local raster or vector image asset onto the artboard with optional blend mode and edge feathering.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to image asset relative to project root"},
                        "rect": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "[x, y, width, height] destination bounding rectangle",
                        },
                        "blend_mode": {
                            "type": "string",
                            "description": "Blend mode (screen, multiply, overlay, softLight, normal, etc.)",
                        },
                        "feather_radius": {
                            "type": "number",
                            "description": "Edge feathering radius in pixels to dissolve hard boundaries",
                        },
                        "role": {
                            "type": "string",
                            "description": "Layer role: hero (updates hero_rect), background, logo, or image",
                            "default": "image",
                        },
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "add_shape_ellipse",
                "description": "Add an ellipse or circle shape with fill and stroke styling.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "width": {"type": "number"},
                        "height": {"type": "number"},
                        "fill": {"type": "string", "description": "Hex color string (e.g. #00F5D4)"},
                        "stroke": {"type": "string", "description": "Hex color string"},
                        "stroke_width": {"type": "number", "default": 0.0},
                        "rotation": {"type": "number", "default": 0.0},
                    },
                    "required": ["x", "y", "width", "height"],
                },
            },
            {
                "name": "add_path",
                "description": "Add a custom vector path via SVG path data string.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "d": {"type": "string", "description": "SVG path data (e.g. 'M 0 0 L 100 100 Z')"},
                        "fill": {"type": "string"},
                        "stroke": {"type": "string"},
                        "stroke_width": {"type": "number", "default": 0.0},
                        "closed": {"type": "boolean", "default": True},
                    },
                    "required": ["d"],
                },
            },
            {
                "name": "set_transparency",
                "description": "Set opacity and blend mode on the active selection or target node.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "opacity": {"type": "number", "default": 1.0, "description": "Opacity from 0.0 to 1.0"},
                        "blend": {"type": "string", "default": "normal", "description": "PDF blend mode"},
                        "target_id": {"type": "string", "description": "Optional target node ID"},
                    },
                },
            },
            {
                "name": "add_effect",
                "description": "Attach a live raster or vector effect (e.g. stylize.dropShadow, stylize.feather, texture.grain).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "effect": {"type": "string", "description": "Effect identifier (e.g. stylize.feather, stylize.dropShadow)"},
                        "params": {"type": "object", "description": "Effect parameters dictionary"},
                        "target_id": {"type": "string", "description": "Optional target node ID"},
                    },
                    "required": ["effect"],
                },
            },
            {
                "name": "soft_scrim",
                "description": "Add non-destructive atmospheric gradient scrim over background art.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "width": {"type": "number"},
                        "height": {"type": "number"},
                        "stops": {
                            "type": "array",
                            "description": "List of [offset, hex_color, opacity] gradient stops",
                        },
                        "direction": {"type": "string", "description": "to_bottom, to_top, to_right, to_left", "default": "to_bottom"},
                    },
                    "required": ["x", "y", "width", "height"],
                },
            },
            {
                "name": "radial_light",
                "description": "Add screen-blended radial light glow or atmospheric spill.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cx": {"type": "number", "description": "Center X coordinate"},
                        "cy": {"type": "number", "description": "Center Y coordinate"},
                        "rx": {"type": "number", "description": "Radius X"},
                        "ry": {"type": "number", "description": "Radius Y"},
                        "radius": {"type": "number", "description": "Radius"},
                        "color": {"type": "string", "default": "#00F5D4"},
                        "opacity": {"type": "number", "default": 0.8},
                    },
                    "required": ["cx", "cy"],
                },
            },
            {
                "name": "measure",
                "description": "Evaluate Phase-D deterministic QA gates without raster rendering.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "list_items",
                "description": "List every placed element on the artboard with its id, type, rect, text, z_order, and locked status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "update_item",
                "description": "Move, resize, restyle, or edit an existing item. Refuses locked items. Verbatim check applies if text is changed.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "ID of item to update"},
                        "fields": {"type": "object", "description": "Key-value dictionary of updated properties (e.g. x, y, size, color, fill, text)"},
                    },
                    "required": ["id", "fields"],
                },
            },
            {
                "name": "delete_item",
                "description": "Delete an item from the canvas. Refuses locked items.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "ID of item to delete"},
                    },
                    "required": ["id"],
                },
            },
            {
                "name": "get_free_regions",
                "description": "Calculate calm and unoccupied rectangular regions within safe margins, treating locked zones and placed items as obstacles.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "min_width": {"type": "number", "default": 160.0, "description": "Minimum region width in points"},
                        "min_height": {"type": "number", "default": 40.0, "description": "Minimum region height in points"},
                    },
                },
            },
            {
                "name": "render_preview",
                "description": "Generate rapid raster preview PNG via VectorCraft CLI.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "scale": {"type": "number", "default": 0.5, "description": "Render scale factor"},
                    },
                },
            },
            {
                "name": "save_session",
                "description": "Export current command buffer to an editable .vcs session file.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Optional destination path for .vcs file"},
                    },
                },
            },
            {
                "name": "load_session",
                "description": "Restore document buffer and typography manifest from a .vcs file.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to .vcs file to load"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "export",
                "description": "Final render export. Blocked unless measure() reports 0 failed gates.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "output_png": {"type": "string", "description": "Destination PNG output path"},
                        "output_pdf": {"type": "string", "description": "Optional destination PDF output path"},
                    },
                    "required": ["output_png"],
                },
            },
        ]

    def dispatch_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch tool by name with arguments dict."""
        self.tool_call_history.append({"name": name, "arguments": arguments, "time": time.time()})
        method = getattr(self, name, None)
        if method is None:
            return {"error": f"ToolNotFound: Unknown tool '{name}'"}
        try:
            return method(**arguments)
        except TypeError as te:
            return {"error": f"InvalidArgumentsError: {te}"}
        except Exception as e:
            return {"error": f"ToolExecutionError: {e}"}

    # -------------------------------------------------------------------------
    # JSON-RPC 2.0 Protocol Handler
    # -------------------------------------------------------------------------

    def handle_message(self, message: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Handle incoming JSON-RPC 2.0 message."""
        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        # Notifications (e.g. notifications/initialized) require no response
        if msg_id is None:
            return None

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "vectorcraft-mcp",
                        "version": "1.0.0",
                    },
                },
            }

        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": self.get_tool_definitions()},
            }

        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            tool_res = self.dispatch_tool(tool_name, tool_args)
            is_err = isinstance(tool_res, dict) and "error" in tool_res
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(tool_res, indent=2),
                        }
                    ],
                    "isError": is_err,
                },
            }

        # Unknown method protocol error
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }

    def run_stdio(self) -> None:
        """Run stdio JSON-RPC loop reading line-delimited or Content-Length messages."""
        sys.stderr.write(f"[VectorCraft MCP Server] Started stdio loop (session: {self.session_id})\n")
        sys.stderr.flush()

        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line_str = line.strip()
            if not line_str:
                continue

            # Support Content-Length header framing if present
            if line_str.lower().startswith("content-length:"):
                try:
                    length = int(line_str.split(":", 1)[1].strip())
                    # Consume empty line separator
                    sep = sys.stdin.readline()
                    payload = sys.stdin.read(length)
                    data = json.loads(payload)
                except Exception as e:
                    sys.stderr.write(f"[VectorCraft MCP Server] Header parse error: {e}\n")
                    continue
            else:
                try:
                    data = json.loads(line_str)
                except json.JSONDecodeError as jde:
                    sys.stderr.write(f"[VectorCraft MCP Server] JSON decode error: {jde}\n")
                    continue

            resp = self.handle_message(data)
            if resp is not None:
                out_line = json.dumps(resp)
                sys.stdout.write(out_line + "\n")
                sys.stdout.flush()


def main():
    server = VectorCraftMCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
