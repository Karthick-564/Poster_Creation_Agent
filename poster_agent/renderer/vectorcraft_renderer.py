"""VectorCraft Renderer: High-precision agent-native vector layout and typography engine."""
import json
import logging
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def get_vectorcraft_fonts_dir(cli_path: Optional[str | Path] = None) -> Path:
    """Resolve the shared VectorCraft Fonts directory programmatically.

    Follows VectorCraft's exact prefs_dir.rs & profile.rs resolution logic:
    1. VECTORCRAFT_CONFIG_DIR env var if set: <VECTORCRAFT_CONFIG_DIR>/Fonts
    2. Portable mode marker ('portable.txt' or 'VectorCraft.portable') beside executable:
       <exe_dir>/VectorCraftData/Fonts
    3. Platform conventions:
       - Windows: %APPDATA%/VectorCraft/Fonts
       - macOS: ~/Library/Application Support/VectorCraft/Fonts
       - Linux: $XDG_CONFIG_HOME/vectorcraft/Fonts or ~/.config/vectorcraft/Fonts
    """
    config_dir_env = os.environ.get("VECTORCRAFT_CONFIG_DIR")
    if config_dir_env:
        return Path(config_dir_env) / "Fonts"

    resolved_cli = Path(cli_path).resolve() if cli_path else (
        Path(__file__).resolve().parent.parent.parent
        / VectorCraftRenderer.DEFAULT_CLI_REL
    ).resolve()

    exe_dir = resolved_cli.parent
    if (exe_dir / "portable.txt").is_file() or (exe_dir / "VectorCraft.portable").is_file():
        return exe_dir / "VectorCraftData" / "Fonts"

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "VectorCraft" / "Fonts"
        return Path.home() / "AppData" / "Roaming" / "VectorCraft" / "Fonts"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "VectorCraft" / "Fonts"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            return Path(xdg) / "vectorcraft" / "Fonts"
        return Path.home() / ".config" / "vectorcraft" / "Fonts"


@dataclass
class VectorCraftResult:
    """Result returned by VectorCraft headless execution."""
    success: bool
    output_png: Optional[Path] = None
    output_pdf: Optional[Path] = None
    output_svg: Optional[Path] = None
    execution_time_sec: float = 0.0
    command_count: int = 0
    step_results: list[dict[str, Any]] = field(default_factory=list)
    text_manifest: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error_message: Optional[str] = None


class VectorCraftRenderer:
    """Interfaces directly with the VectorCraft CLI engine for deterministic layout composition."""

    DEFAULT_CLI_REL = Path("tools/vectorcraft_bin/vectorcraft-0.19.0-windows-x64-portable/vectorcraft-cli.exe")

    def __init__(self, cli_path: Optional[str | Path] = None):
        if cli_path:
            self.cli_path = Path(cli_path).resolve()
        else:
            self.cli_path = (Path(__file__).parent.parent.parent / self.DEFAULT_CLI_REL).resolve()

        if not self.cli_path.exists():
            raise FileNotFoundError(f"VectorCraft CLI binary not found at: {self.cli_path}")

        self.commands: list[dict[str, Any]] = []
        self._queued_texts: list[dict[str, Any]] = []
        self.text_manifest: list[dict[str, Any]] = []
        self._last_node_step_idx: Optional[int] = None

    def clear(self) -> None:
        """Clear queued commands."""
        self.commands.clear()
        self._queued_texts.clear()
        self.text_manifest.clear()
        self._last_node_step_idx = None

    def new_document(
        self,
        width: float,
        height: float,
        units: str = "Points",
        color_mode: str = "rgb",
        raster_resolution: int | str = 300,
    ) -> "VectorCraftRenderer":
        """Initialize a new document artboard."""
        self.commands.append({
            "command": "file.new",
            "params": {
                "width": width,
                "height": height,
                "units": units,
                "colorMode": color_mode,
            },
        })
        if raster_resolution:
            self.set_raster_effects_settings(resolution=raster_resolution, color_model=color_mode)
        return self

    def set_raster_effects_settings(
        self,
        resolution: int | str = 300,
        color_model: str = "rgb",
        background: str = "transparent",
        anti_alias: bool = True,
        clipping_mask: bool = False,
        add_around: float = 0.0,
    ) -> "VectorCraftRenderer":
        """Configure print resolution and settings for live raster effects."""
        params: dict[str, Any] = {
            "resolution": resolution,
            "colorModel": color_model,
            "background": background,
            "antiAlias": anti_alias,
            "clippingMask": clipping_mask,
            "addAround": add_around,
        }
        self.commands.append({
            "command": "document.rasterEffectsSettings",
            "params": params,
        })
        return self

    def place_image(
        self,
        path: str | Path,
        rect: Optional[list[float]] = None,
        at: Optional[list[float]] = None,
        link: bool = True,
    ) -> "VectorCraftRenderer":
        """Place a raster or vector image asset onto the artboard."""
        abs_path = str(Path(path).resolve())
        params: dict[str, Any] = {"path": abs_path, "link": link}
        if rect:
            params["rect"] = rect
        elif at:
            params["at"] = at
        self.commands.append({"command": "file.place", "params": params})
        self._last_node_step_idx = len(self.commands) - 1
        return self

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
        rotation: float = 0.0,
    ) -> "VectorCraftRenderer":
        """Add a live rectangle shape with optional paint styling."""
        self.commands.append({"command": "select.none", "params": {}})
        if fill:
            self.commands.append({"command": "paint.setFill", "params": {"color": fill}})
        else:
            self.commands.append({"command": "paint.none", "params": {}})

        if stroke and stroke_width > 0:
            self.commands.append({"command": "paint.setStroke", "params": {"color": stroke}})
            self.commands.append({"command": "stroke.set", "params": {"weight": stroke_width}})

        params: dict[str, Any] = {"x": x, "y": y, "width": width, "height": height}
        if radius > 0:
            params["radius"] = radius
        if rotation != 0.0:
            params["rotation"] = rotation
        self.commands.append({"command": "shape.rectangle", "params": params})
        self._last_node_step_idx = len(self.commands) - 1
        return self

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
    ) -> "VectorCraftRenderer":
        """Add an ellipse or circle shape."""
        self.commands.append({"command": "select.none", "params": {}})
        if fill:
            self.commands.append({"command": "paint.setFill", "params": {"color": fill}})
        else:
            self.commands.append({"command": "paint.none", "params": {}})

        if stroke and stroke_width > 0:
            self.commands.append({"command": "paint.setStroke", "params": {"color": stroke}})
            self.commands.append({"command": "stroke.set", "params": {"weight": stroke_width}})

        params: dict[str, Any] = {"x": x, "y": y, "width": width, "height": height}
        if rotation != 0.0:
            params["rotation"] = rotation
        self.commands.append({"command": "shape.ellipse", "params": params})
        self._last_node_step_idx = len(self.commands) - 1
        return self

    def add_path(
        self,
        d: str,
        fill: Optional[str] = None,
        stroke: Optional[str] = None,
        stroke_width: float = 0.0,
        closed: bool = True,
    ) -> "VectorCraftRenderer":
        """Add a custom vector path via SVG path data."""
        self.commands.append({"command": "select.none", "params": {}})
        if fill:
            self.commands.append({"command": "paint.setFill", "params": {"color": fill}})
        else:
            self.commands.append({"command": "paint.none", "params": {}})

        if stroke and stroke_width > 0:
            self.commands.append({"command": "paint.setStroke", "params": {"color": stroke}})
            self.commands.append({"command": "stroke.set", "params": {"weight": stroke_width}})

        self.commands.append({
            "command": "path.create",
            "params": {"d": d, "closed": closed},
        })
        self._last_node_step_idx = len(self.commands) - 1
        return self

    def add_shape_star(
        self,
        cx: float,
        cy: float,
        radius1: float,
        radius2: float,
        points: int = 4,
        rotation: float = 0.0,
        fill: Optional[str] = None,
        stroke: Optional[str] = None,
        stroke_width: float = 0.0,
    ) -> "VectorCraftRenderer":
        """Add a star polygon (e.g. 4-point sparkle star)."""
        self.commands.append({"command": "select.none", "params": {}})
        if fill:
            self.commands.append({"command": "paint.setFill", "params": {"color": fill}})
        else:
            self.commands.append({"command": "paint.none", "params": {}})

        if stroke and stroke_width > 0:
            self.commands.append({"command": "paint.setStroke", "params": {"color": stroke}})
            self.commands.append({"command": "stroke.set", "params": {"weight": stroke_width}})

        params: dict[str, Any] = {
            "cx": cx,
            "cy": cy,
            "radius1": radius1,
            "radius2": radius2,
            "points": points,
        }
        if rotation != 0.0:
            params["rotation"] = rotation
        self.commands.append({"command": "shape.star", "params": params})
        self._last_node_step_idx = len(self.commands) - 1
        return self

    def add_starfield(
        self,
        width: float,
        height: float,
        count: int = 80,
        colors: Optional[list[str]] = None,
        seed: int = 42,
    ) -> "VectorCraftRenderer":
        """Draw a procedural night-sky vector starfield with twinkling stars."""
        rng = random.Random(seed)
        palette = colors or ["#FFF3E0", "#FFFFFF", "#7AE7C7", "#FFD166"]

        for _ in range(count):
            x = rng.uniform(20, width - 20)
            y = rng.uniform(20, height * 0.85)  # Concentrated in upper/middle sky
            color = rng.choice(palette)

            star_type = rng.random()
            if star_type < 0.15:
                # 4-point twinkle star
                r1 = rng.uniform(5.0, 10.0)
                r2 = r1 * 0.22
                rot = rng.uniform(0, 45)
                self.add_shape_star(cx=x, cy=y, radius1=r1, radius2=r2, points=4, rotation=rot, fill=color)
            else:
                # Small circular pinprick star
                rad = rng.uniform(1.0, 2.5)
                self.add_shape_ellipse(x=x - rad, y=y - rad, width=rad * 2, height=rad * 2, fill=color)

        return self

    def add_torn_strip(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: str = "#F2F2EE",
        stroke: Optional[str] = "#CCCCCC",
        stroke_width: float = 1.0,
        seed: int = 42,
        jag: float = 6.0,
    ) -> "VectorCraftRenderer":
        """Generate and draw an organic torn paper magazine cutout strip."""
        rng = random.Random(seed)
        pts = []
        steps_x = max(5, int(width / 20))
        for i in range(steps_x + 1):
            px = x + (width * i / steps_x)
            py = y + rng.uniform(-jag * 0.5, jag * 0.5)
            pts.append((px, py))
        steps_y = max(3, int(height / 20))
        for j in range(1, steps_y + 1):
            px = x + width + rng.uniform(-jag * 0.6, jag * 0.6)
            py = y + (height * j / steps_y)
            pts.append((px, py))
        for i in range(steps_x - 1, -1, -1):
            px = x + (width * i / steps_x)
            py = y + height + rng.uniform(-jag, jag)
            pts.append((px, py))
        for j in range(steps_y - 1, 0, -1):
            px = x + rng.uniform(-jag * 0.6, jag * 0.6)
            py = y + (height * j / steps_y)
            pts.append((px, py))

        d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f} " + " ".join(f"L {p[0]:.1f} {p[1]:.1f}" for p in pts[1:]) + " Z"
        return self.add_path(d=d, fill=fill, stroke=stroke, stroke_width=stroke_width, closed=True)

    def add_halftone_cluster(
        self,
        center_x: float,
        center_y: float,
        rows: int = 6,
        cols: int = 5,
        spacing: float = 30.0,
        dot_radius: float = 9.0,
        color: str = "#C82A2A",
        seed: int = 42,
    ) -> "VectorCraftRenderer":
        """Draw a distressed halftone ink stamp dot cluster."""
        rng = random.Random(seed)
        start_x = center_x - (cols * spacing) / 2
        start_y = center_y - (rows * spacing) / 2

        for r in range(rows):
            for c in range(cols):
                # Distressed probability: drop some dots organically like an ink stamp
                if rng.random() > 0.88:
                    continue
                jitter_x = rng.uniform(-2.5, 2.5)
                jitter_y = rng.uniform(-2.5, 2.5)
                rad = dot_radius * rng.uniform(0.75, 1.25)
                cx = start_x + (c * spacing) + jitter_x
                cy = start_y + (r * spacing) + jitter_y
                self.add_shape_ellipse(
                    x=cx - rad,
                    y=cy - rad,
                    width=rad * 2,
                    height=rad * 2,
                    fill=color,
                )
        return self

    def add_text(
        self,
        text: str,
        x: float,
        y: float,
        size: float,
        font: str = "Arial",
        color: str = "#000000",
        rotation: float = 0.0,
        justify: str = "auto",
        area: Optional[dict[str, Any]] = None,
        style: str = "",
        tracking: float = 0.0,
        leading: Optional[float] = None,
        role: Optional[str] = None,
    ) -> "VectorCraftRenderer":
        """Add crisp native typography with font metrics."""
        if not text or not text.strip():
            return self

        params: dict[str, Any] = {
            "text": text,
            "x": x,
            "y": y,
            "size": size,
            "font": font,
            "color": color,
            "justify": justify,
        }
        if rotation != 0.0:
            params["rotation"] = rotation
        if area:
            params["area"] = area
        if style:
            params["style"] = style
        self.commands.append({"command": "text.create", "params": params})
        self._last_node_step_idx = len(self.commands) - 1

        style_params: dict[str, Any] = {}
        if style:
            style_params["style"] = style
        if tracking != 0.0:
            style_params["tracking"] = tracking
        if leading is not None:
            style_params["leading"] = leading

        if style_params:
            self.commands.append({"command": "text.setStyle", "params": style_params})

        self._queued_texts.append({
            "role": role,
            "text": text,
            "size": size,
            "font": font,
            "style": style,
            "tracking": tracking,
            "leading": leading,
        })
        return self

    def fit_headline(self, target_id: Optional[int | str] = None) -> "VectorCraftRenderer":
        """Track the first line of area type so it fills the frame width (Swiss headline lockup)."""
        params: dict[str, Any] = {}
        if target_id is not None:
            params["id"] = target_id
        self.commands.append({"command": "text.fitHeadline", "params": params})
        return self

    def area_text(
        self,
        text: str,
        x: float,
        y: float,
        width: float,
        height: float,
        size: float,
        font: str = "Arial",
        color: str = "#000000",
        fit: str = "autoHeight",
        rotation: float = 0.0,
        justify: str = "auto",
        style: str = "",
        tracking: float = 0.0,
        leading: Optional[float] = None,
        role: Optional[str] = None,
    ) -> "VectorCraftRenderer":
        """Add area text within a bounding box."""
        area_params = {"width": width, "height": height, "fit": fit}
        return self.add_text(
            text=text,
            x=x,
            y=y,
            size=size,
            font=font,
            color=color,
            rotation=rotation,
            justify=justify,
            area=area_params,
            style=style,
            tracking=tracking,
            leading=leading,
            role=role,
        )

    def add_effect(
        self,
        effect_name: str,
        params: Optional[dict[str, Any]] = None,
        target_id: Optional[int | str] = None,
    ) -> "VectorCraftRenderer":
        """Attach a live effect (e.g. stylize.dropShadow, texture.grain) to an object.

        If target_id is omitted, targets the active selection (the most recently created node).
        """
        payload: dict[str, Any] = {"effect": effect_name, "params": params or {}}
        if target_id is not None:
            if target_id in ("$last", "last"):
                if self._last_node_step_idx is not None:
                    payload["id"] = f"${self._last_node_step_idx}.id"
                else:
                    payload["id"] = "$last.id"
            else:
                payload["id"] = target_id
        self.commands.append({"command": "effect.apply", "params": payload})
        return self

    def soft_scrim(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        stops: Optional[list[tuple[float, str, float]]] = None,
        direction: str = "to_bottom",
    ) -> "VectorCraftRenderer":
        """Create a non-destructive atmospheric gradient scrim over background art.

        Unlike solid shape fills, soft_scrim uses per-stop alpha so underlying art
        shows through without punching an opaque hole.

        stops: List of (offset, hex_color, alpha) tuples. Defaults to dark fade to transparent.
        direction: 'to_bottom' | 'to_top' | 'to_right' | 'to_left'
        """
        if not stops:
            stops = [(0.0, "#070B19", 0.85), (1.0, "#070B19", 0.0)]

        if direction == "to_bottom":
            start = [x + width / 2.0, y]
            end = [x + width / 2.0, y + height]
        elif direction == "to_top":
            start = [x + width / 2.0, y + height]
            end = [x + width / 2.0, y]
        elif direction == "to_right":
            start = [x, y + height / 2.0]
            end = [x + width, y + height / 2.0]
        elif direction == "to_left":
            start = [x + width, y + height / 2.0]
            end = [x, y + height / 2.0]
        else:
            start = [x + width / 2.0, y]
            end = [x + width / 2.0, y + height]

        formatted_stops = [
            {"offset": s[0], "color": s[1], "opacity": s[2]}
            for s in stops
        ]

        self.commands.append({"command": "select.none", "params": {}})
        self.commands.append({
            "command": "paint.setFill",
            "params": {
                "gradient": {
                    "kind": "linear",
                    "method": "classic",
                    "stops": formatted_stops,
                    "start": start,
                    "end": end,
                    "dither": True,
                }
            },
        })
        self.commands.append({
            "command": "shape.rectangle",
            "params": {"x": x, "y": y, "width": width, "height": height},
        })
        self._last_node_step_idx = len(self.commands) - 1
        return self

    def radial_light(
        self,
        cx: float,
        cy: float,
        radius: float,
        color: str = "#00F5D4",
        alpha_stop_inner: float = 0.8,
        alpha_stop_outer: float = 0.0,
        blend_mode: str = "screen",
    ) -> "VectorCraftRenderer":
        """Add a screen-blended radial light spill or atmospheric glow."""
        x = cx - radius
        y = cy - radius
        w = radius * 2.0
        h = radius * 2.0

        formatted_stops = [
            {"offset": 0.0, "color": color, "opacity": alpha_stop_inner},
            {"offset": 1.0, "color": color, "opacity": alpha_stop_outer},
        ]

        self.commands.append({"command": "select.none", "params": {}})
        self.commands.append({
            "command": "paint.setFill",
            "params": {
                "gradient": {
                    "kind": "radial",
                    "method": "classic",
                    "stops": formatted_stops,
                    "start": [cx, cy],
                    "end": [cx + radius, cy],
                    "dither": True,
                }
            },
        })
        self.commands.append({
            "command": "shape.ellipse",
            "params": {"x": x, "y": y, "width": w, "height": h},
        })
        self._last_node_step_idx = len(self.commands) - 1
        if blend_mode:
            self.commands.append({
                "command": "transparency.set",
                "params": {"blend": blend_mode},
            })
        return self

    def orbital_text(
        self,
        path_d: str,
        text: str,
        size: float,
        font: str = "Arial",
        style: str = "",
        color: str = "#000000",
        at: Optional[list[float]] = None,
        justify: str = "center",
        role: Optional[str] = None,
    ) -> "VectorCraftRenderer":
        """Place editorial text along an arbitrary vector path baseline."""
        if not text or not text.strip():
            return self

        self.commands.append({
            "command": "path.create",
            "params": {"d": path_d, "closed": False},
        })

        params: dict[str, Any] = {
            "path": "$last.id",
            "mode": "onPath",
            "text": text,
            "size": size,
            "font": font,
            "color": color,
            "justify": justify,
        }
        if style:
            params["style"] = style
        if at is not None:
            params["at"] = at

        self.commands.append({"command": "text.createInPath", "params": params})
        self._last_node_step_idx = len(self.commands) - 1

        self._queued_texts.append({
            "role": role,
            "text": text,
            "size": size,
            "font": font,
            "style": style,
            "tracking": 0.0,
            "leading": None,
        })
        return self

    def gradient_fill(
        self,
        id_or_last: Optional[int | str] = None,
        stops: Optional[list[tuple[float, str, float]]] = None,
        direction: str = "to_bottom",
        kind: str = "linear",
        start: Optional[list[float]] = None,
        end: Optional[list[float]] = None,
    ) -> "VectorCraftRenderer":
        """Apply a gradient fill to an existing shape or the active selection."""
        if not stops:
            stops = [(0.0, "#000000", 1.0), (1.0, "#FFFFFF", 1.0)]

        formatted_stops = [
            {"offset": s[0], "color": s[1], "opacity": s[2] if len(s) > 2 else 1.0}
            for s in stops
        ]

        grad_params: dict[str, Any] = {
            "kind": kind,
            "method": "classic",
            "stops": formatted_stops,
            "dither": True,
        }
        if start is not None and end is not None:
            grad_params["start"] = start
            grad_params["end"] = end

        payload: dict[str, Any] = {"gradient": grad_params}
        if id_or_last is not None:
            if id_or_last in ("$last", "last"):
                if self._last_node_step_idx is not None:
                    payload["id"] = f"${self._last_node_step_idx}.id"
                else:
                    payload["id"] = "$last.id"
            else:
                payload["id"] = id_or_last

        self.commands.append({"command": "paint.setFill", "params": payload})
        return self

    def execute(
        self,
        output_png: Optional[str | Path] = None,
        output_pdf: Optional[str | Path] = None,
        output_svg: Optional[str | Path] = None,
        scale: float = 1.0,
        work_dir: Optional[str | Path] = None,
    ) -> VectorCraftResult:
        """Run the queued command batch in VectorCraft headless mode and export deliverables."""
        if not self.commands:
            raise ValueError("No commands queued for VectorCraft execution.")

        work_path = Path(work_dir) if work_dir else Path("runs")
        work_path.mkdir(parents=True, exist_ok=True)
        batch_file = work_path / f"vc_batch_{int(time.time()*1000)}.json"

        with open(batch_file, "w", encoding="utf-8") as f:
            json.dump(self.commands, f, indent=2)

        cli_args = [str(self.cli_path), "run", "--commands", str(batch_file)]

        out_png_path = Path(output_png).resolve() if output_png else None
        out_pdf_path = Path(output_pdf).resolve() if output_pdf else None
        out_svg_path = Path(output_svg).resolve() if output_svg else None

        if out_png_path:
            out_png_path.parent.mkdir(parents=True, exist_ok=True)
            cli_args.extend(["--export", str(out_png_path), "--scale", str(scale)])
        if out_pdf_path:
            out_pdf_path.parent.mkdir(parents=True, exist_ok=True)
            cli_args.extend(["--export", str(out_pdf_path)])
        if out_svg_path:
            out_svg_path.parent.mkdir(parents=True, exist_ok=True)
            cli_args.extend(["--export", str(out_svg_path)])

        start_time = time.time()
        try:
            res = subprocess.run(
                cli_args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=60,
            )
            elapsed = time.time() - start_time

            # Parse results from stdout JSON lines
            step_results = []
            text_manifest = []
            queued_idx = 0

            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        step_data = json.loads(line)
                        step_results.append(step_data)

                        cmd_name = step_data.get("command")
                        if cmd_name in ("text.create", "text.createInPath"):
                            step_res = step_data.get("result", {})
                            queued_meta = self._queued_texts[queued_idx] if queued_idx < len(self._queued_texts) else {}
                            queued_idx += 1

                            manifest_item = {
                                "id": step_res.get("id"),
                                "role": queued_meta.get("role"),
                                "text": queued_meta.get("text", ""),
                                "bounds": step_res.get("bounds"),
                                "overflow": step_res.get("overflow"),
                                "size": queued_meta.get("size"),
                                "font": queued_meta.get("font"),
                                "style": queued_meta.get("style", ""),
                            }
                            text_manifest.append(manifest_item)

                            if step_res.get("overflow"):
                                role_desc = manifest_item["role"] or manifest_item["text"][:24]
                                print(f">>> TEXT OVERFLOW: node {manifest_item['id']} ({role_desc})")
                    except json.JSONDecodeError:
                        pass

            self.text_manifest = text_manifest
            if text_manifest:
                manifest_file = work_path / "text_manifest.json"
                try:
                    with open(manifest_file, "w", encoding="utf-8") as f:
                        json.dump(text_manifest, f, indent=2)
                except Exception as e:
                    logger.warning(f"Could not write text_manifest.json: {e}")

            if res.returncode != 0:
                err_msg = res.stderr.strip() or res.stdout.strip()
                return VectorCraftResult(
                    success=False,
                    execution_time_sec=elapsed,
                    command_count=len(self.commands),
                    step_results=step_results,
                    text_manifest=text_manifest,
                    error_message=err_msg,
                )

            return VectorCraftResult(
                success=True,
                output_png=out_png_path if out_png_path and out_png_path.exists() else None,
                output_pdf=out_pdf_path if out_pdf_path and out_pdf_path.exists() else None,
                output_svg=out_svg_path if out_svg_path and out_svg_path.exists() else None,
                execution_time_sec=elapsed,
                command_count=len(self.commands),
                step_results=step_results,
                text_manifest=text_manifest,
            )
        except Exception as e:
            elapsed = time.time() - start_time
            return VectorCraftResult(
                success=False,
                execution_time_sec=elapsed,
                command_count=len(self.commands),
                error_message=str(e),
            )
        finally:
            # Clean up batch file if needed
            if batch_file.exists():
                try:
                    batch_file.unlink()
                except OSError:
                    pass

