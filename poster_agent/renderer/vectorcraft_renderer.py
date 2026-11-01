"""VectorCraft Renderer: High-precision agent-native vector layout and typography engine."""
import json
import logging
import os
import random
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


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

    def clear(self) -> None:
        """Clear queued commands."""
        self.commands.clear()

    def new_document(
        self,
        width: float,
        height: float,
        units: str = "Points",
        color_mode: str = "rgb",
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
        params: dict[str, Any] = {"x": x, "y": y, "width": width, "height": height}
        if radius > 0:
            params["radius"] = radius
        if rotation != 0.0:
            params["rotation"] = rotation
        self.commands.append({"command": "shape.rectangle", "params": params})

        if fill:
            self.commands.append({"command": "paint.setFill", "params": {"color": fill}})
        if stroke and stroke_width > 0:
            self.commands.append({"command": "paint.setStroke", "params": {"color": stroke}})
            self.commands.append({"command": "stroke.set", "params": {"weight": stroke_width}})
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
        params: dict[str, Any] = {"x": x, "y": y, "width": width, "height": height}
        if rotation != 0.0:
            params["rotation"] = rotation
        self.commands.append({"command": "shape.ellipse", "params": params})

        if fill:
            self.commands.append({"command": "paint.setFill", "params": {"color": fill}})
        if stroke and stroke_width > 0:
            self.commands.append({"command": "paint.setStroke", "params": {"color": stroke}})
            self.commands.append({"command": "stroke.set", "params": {"weight": stroke_width}})
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
        self.commands.append({
            "command": "path.create",
            "params": {"d": d, "closed": closed},
        })
        if fill:
            self.commands.append({"command": "paint.setFill", "params": {"color": fill}})
        if stroke and stroke_width > 0:
            self.commands.append({"command": "paint.setStroke", "params": {"color": stroke}})
            self.commands.append({"command": "stroke.set", "params": {"weight": stroke_width}})
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

        if fill:
            self.commands.append({"command": "paint.setFill", "params": {"color": fill}})
        if stroke and stroke_width > 0:
            self.commands.append({"command": "paint.setStroke", "params": {"color": stroke}})
            self.commands.append({"command": "stroke.set", "params": {"weight": stroke_width}})
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
    ) -> "VectorCraftRenderer":
        """Add crisp native typography with font metrics."""
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
        self.commands.append({"command": "text.create", "params": params})
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
            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        step_results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            if res.returncode != 0:
                err_msg = res.stderr.strip() or res.stdout.strip()
                return VectorCraftResult(
                    success=False,
                    execution_time_sec=elapsed,
                    command_count=len(self.commands),
                    step_results=step_results,
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

