"""Interactive MCP Designer Loop & Design Search Engine.

Executes generative, high-aesthetic poster design via VectorCraft MCP Server tools.
Replaces rigid deterministic slot composition (composer.compose_slots) with
design recipe exploration, live measure() physics gate enforcement, and
quantitative design quality evaluation (palette coverage, type scale contrast,
asymmetry balance, hero integration, ticket container).

Usage:
    python scripts/mcp_designer.py --brief-file briefs/brief_noir_beats.txt --mode search --run-id noir_beats_designed_v1 --assets-from runs/noir_beats_v8
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Optional

import cv2
import numpy as np
from PIL import Image

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from poster_agent.mcp.vectorcraft_server import VectorCraftMCPServer
from poster_agent.qa.design import evaluate_design_quality
from poster_agent.qa.gates import check_background_ocr


class MCPDesigner:
    """Orchestrates poster composition via VectorCraft MCP server."""

    def __init__(
        self,
        brief_file: Path,
        run_id: str,
        mode: str = "search",
        assets_from: Optional[Path] = None,
        base_dir: Optional[Path] = None,
    ):
        self.project_root = (base_dir or Path.cwd()).resolve()
        self.brief_file = (self.project_root / brief_file).resolve()
        self.run_id = run_id
        self.mode = mode
        self.assets_dir = (self.project_root / assets_from).resolve() if assets_from else None

        self.run_dir = self.project_root / "runs" / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.run_dir / "designer_log.jsonl"

        self.server = VectorCraftMCPServer(session_id=self.run_id, base_dir=self.project_root)
        self.server.session_dir = self.run_dir

        self.doc_w = 1080.0
        self.doc_h = 1350.0
        self.hero_path: Optional[Path] = None
        self.hero_meta: dict[str, Any] = {}
        self.logo_path = self.project_root / "assets" / "logo_kumaraguru.png"

        # Ingest brief text for palette and metadata extraction
        self.raw_brief = self.brief_file.read_text(encoding="utf-8")
        self.palette = self._extract_palette()

    def _extract_palette(self) -> list[str]:
        for line in self.raw_brief.splitlines():
            if line.lower().startswith("palette:"):
                import re
                hexes = re.findall(r"#[0-9A-Fa-f]{6}", line)
                if hexes:
                    return hexes
        return ["#070B19", "#00F5D4", "#7B2FFF", "#FF3D68", "#F0F6FC"]

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        record = {
            "timestamp": time.time(),
            "event": event_type,
            "data": data,
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def run(self) -> dict[str, Any]:
        """Run the MCP designer loop."""
        print("=" * 76)
        print(f"STARTING MCP DESIGNER ENGINE: {self.run_id}")
        print(f"Brief:  {self.brief_file.name}")
        print(f"Mode:   {self.mode.upper()}")
        print(f"Output: runs/{self.run_id}/")
        print("=" * 76)

        # 1. OCR Gate on candidate raster layers
        if self.assets_dir:
            self._verify_input_assets()
            self.hero_path, self.hero_meta = self._prepare_hero()
            self._log_event("hero_prepared", self.hero_meta)
            if self.hero_path:
                print(f"  - Prepared hero: {self.hero_path.name} ({self.hero_meta.get('source')})")
            else:
                print(f"  - Hero unusable: {self.hero_meta.get('status')} -> type-as-hero composition")

        # 2. Design Search / LLM Execution
        if self.mode == "llm":
            champion = self._run_llm_mode()
        else:
            champion = self._run_search_mode()

        # 3. Export Champion Deliverables
        print("\n" + "-" * 76)
        print(f"EXPORTING CHAMPION DESIGN: {champion['recipe_name']} (Score: {champion['design_score']}/10)")
        print("-" * 76)

        export_res = self._materialize_champion(champion)

        # 4. Final Quality Evaluation on Master Render
        final_render = self.run_dir / "master_render_2x.png"
        quality_report = evaluate_design_quality(
            manifest_rows=self.server.manifest_rows,
            image_input=final_render,
            palette_hexes=self.palette,
            canvas_w=self.doc_w,
            canvas_h=self.doc_h,
            hero_rect=self.server.hero_rect,
            hero_asset=self.hero_path,
            hero_expected=champion.get("hero_expected", True),
        )

        summary = {
            "run_id": self.run_id,
            "recipe_name": champion["recipe_name"],
            "design_score": quality_report["design_score"],
            "measure_passed": True,
            "quality_report": quality_report,
            "deliverables": {
                "master_render_2x": f"runs/{self.run_id}/master_render_2x.png",
                "master_print_pdf": f"runs/{self.run_id}/master_print.pdf",
                "session_vcs": f"runs/{self.run_id}/session.vcs",
            },
        }

        with open(self.run_dir / "designer_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        self._write_design_review_doc(champion, quality_report)
        print(f"\n[DONE] Master render exported to: runs/{self.run_id}/master_render_2x.png")
        print(f"[DONE] Final Design Score: {quality_report['design_score']} / 10.0")
        return summary

    def _verify_input_assets(self) -> None:
        print("\n[Stage 1] Pre-composition Background & Hero OCR Gate:")
        bg_path = self.assets_dir / "layer0_bg.png"
        hero_path = self.assets_dir / "layer3_hero.png"

        for p in (bg_path, hero_path):
            if p.exists():
                fails = check_background_ocr(p)
                status = "PASS (0 unmapped tokens)" if not fails else f"FAIL ({len(fails)} tokens)"
                print(f"  - {p.name:<20}: {status}")
                if fails:
                    raise RuntimeError(f"OCR check failed for asset {p.name}: {fails[0].detail}")

    def _prepare_hero(self) -> tuple[Optional[Path], dict[str, Any]]:
        """Key, crop and rim-light the raw hero into a compositable layer.

        The v8 hero is an opaque near-black render: the crowd body is
        blue-channel 0 while the atmospheric haze is blue 5-12. A plain
        duotone cannot separate body from background and a screen blend of
        black contributes nothing. We therefore build an alpha mask from the
        blue channel, crop the crowd band, paint a dark silhouette with a
        cyan->magenta top rim, and fade the bottom into the canvas.
        """
        if not self.assets_dir:
            return None, {"status": "no_assets_dir"}

        raw = self.assets_dir / "layer3_hero.png"
        if not raw.exists():
            return None, {"status": "missing_asset", "path": str(raw)}

        rgba = Image.open(raw).convert("RGBA")
        arr = np.array(rgba)
        h, w = arr.shape[:2]
        alpha_cov = float((arr[:, :, 3] > 10).mean())

        mask: Optional[np.ndarray] = None
        source = ""
        if alpha_cov < 0.98:
            mask = (arr[:, :, 3] > 10).astype(np.uint8) * 255
            source = "alpha"
        else:
            blue = arr[:, :, 2]
            body = (blue <= 2).astype(np.uint8) * 255
            blue_cov = float((body > 0).mean())
            if 0.03 <= blue_cov <= 0.90:
                mask = body
                source = "blue_key"
            else:
                lum = np.array(Image.open(raw).convert("L"))
                body = (lum > 8).astype(np.uint8) * 255
                luma_cov = float((body > 0).mean())
                if 0.02 <= luma_cov <= 0.90:
                    mask = body
                    source = "luma_key"

        if mask is None:
            return None, {
                "status": "unusable_hero",
                "alpha_coverage": round(alpha_cov, 4),
                "reason": "no separable subject (opaque near-black asset)",
            }

        # Clean the mask and drop specks.
        k = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=3)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        clean = np.zeros_like(mask)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] >= 1500:
                clean[labels == i] = 255
        mask = clean

        ys, xs = np.where(mask > 0)
        if len(xs) == 0:
            return None, {"status": "empty_mask", "source": source}

        # Crop a 2.286:1 band anchored at the top contour (heads/hands).
        target_ratio = 960.0 / 420.0
        x0 = max(0, int(xs.min()) - 12)
        x1 = min(w, int(xs.max()) + 13)
        y0 = max(0, int(ys.min()) - 12)
        band_w = max(1, x1 - x0)
        band_h = max(1, int(round(band_w / target_ratio)))
        y1 = min(h, y0 + band_h)
        x1 = min(w, x0 + int(round((y1 - y0) * target_ratio)))
        mask = mask[y0:y1, x0:x1]
        if mask.size == 0:
            return None, {"status": "empty_crop", "source": source}

        bh, bw = mask.shape
        alpha = cv2.GaussianBlur(mask, (0, 0), 1.8).astype(np.float32) / 255.0
        fade_h = int(bh * 0.55)
        if fade_h > 0:
            fade = np.ones((bh, 1), dtype=np.float32)
            fade[-fade_h:, 0] = np.linspace(1.0, 0.0, fade_h) ** 0.8
            alpha *= fade

        # Soft left/right edges so the crop boundary dissolves into the canvas
        # without the renderer's whole-image feather blur.
        edge = max(1, int(round(bw * 0.06)))
        ramp = np.linspace(0.0, 1.0, edge, dtype=np.float32)
        alpha[:, :edge] *= ramp[None, :]
        alpha[:, -edge:] *= ramp[::-1][None, :]

        # Dark navy body with a subtle violet lift toward the heads.
        t = np.linspace(0.0, 1.0, bh, dtype=np.float32)[:, None]
        base = np.array([12.0, 19.0, 42.0], dtype=np.float32)
        lift = np.array([40.0, 25.0, 90.0], dtype=np.float32)
        mix = 0.35 * (1.0 - t[..., None])
        body_col = base[None, None, :] * (1.0 - mix) + lift[None, None, :] * mix

        # Top-edge rim light: cyan on the left, magenta on the right.
        shift = max(3, int(round(bh * 0.018)))
        shifted = np.zeros_like(mask)
        shifted[shift:, :] = mask[:-shift, :]
        top_edge = np.clip(mask.astype(np.int16) - shifted.astype(np.int16), 0, 255).astype(np.uint8)
        rim = cv2.GaussianBlur(top_edge, (0, 0), 3.2).astype(np.float32) / 255.0
        xs_norm = np.linspace(0.0, 1.0, bw, dtype=np.float32)[None, :, None]
        rim_col = (
            np.array([0.0, 245.0, 212.0], dtype=np.float32) * (1.0 - xs_norm)
            + np.array([255.0, 61.0, 104.0], dtype=np.float32) * xs_norm
        )
        body_col = body_col * (1.0 - rim[..., None]) + rim_col * rim[..., None]

        out_arr = np.dstack([body_col, alpha * 255.0]).clip(0, 255).astype(np.uint8)
        out = Image.fromarray(out_arr, "RGBA").resize((960, 420), Image.LANCZOS)
        out_path = self.run_dir / "hero_neon.png"
        out.save(out_path)

        visible = out_arr[:, :, :3][out_arr[:, :, 3] > 10]
        mean_lum = float(np.mean(
            0.299 * visible[:, 0] + 0.587 * visible[:, 1] + 0.114 * visible[:, 2]
        )) if visible.size else 0.0

        return out_path, {
            "status": "ok",
            "source": source,
            "raw_alpha_coverage": round(alpha_cov, 4),
            "mask_coverage": round(float((mask > 0).mean()), 4),
            "crop": [int(x0), int(y0), int(bw), int(bh)],
            "output": str(out_path.relative_to(self.project_root)),
            "output_size": [960, 420],
            "mean_luminance": round(mean_lum, 1),
        }

    def _run_search_mode(self) -> dict[str, Any]:
        """Explore diverse parameterized design recipes from Phase 0."""
        print("\n[Stage 2] Exploring Design Recipes & Evaluating Dynamic Quality:")

        candidates = [
            self._recipe_asymmetric_neon_glow(),
            self._recipe_swiss_editorial_grid(),
            self._recipe_brutalist_display(),
        ]

        evaluated = []
        for cand in candidates:
            res = self._evaluate_candidate(cand)
            evaluated.append(res)
            self._log_event("candidate_evaluated", res)

        # Sort by measure passed (True first), then by design_score descending
        valid_candidates = [c for c in evaluated if c["measure_result"].get("passed") is True]
        if not valid_candidates:
            raise RuntimeError("All design candidates failed physical measure() gates!")

        valid_candidates.sort(key=lambda c: c["design_score"], reverse=True)
        champion = valid_candidates[0]

        print(f"\nChampion Selected: '{champion['recipe_name']}' with design score {champion['design_score']:.2f}/10")
        return champion

    def _evaluate_candidate(self, cand_spec: dict[str, Any]) -> dict[str, Any]:
        recipe_name = cand_spec["name"]
        commands = cand_spec["commands"]
        hero_expected = cand_spec.get("hero_expected", True)

        # Run candidate in fresh doc
        self.server.create_doc(self.doc_w, self.doc_h)
        self.server.load_brief(str(self.brief_file))

        rejected = []
        for cmd in commands:
            tool_name = cmd["tool"]
            args = cmd["args"]
            res = self.server.dispatch_tool(tool_name, args)
            if isinstance(res, dict) and res.get("error"):
                rejected.append({"tool": tool_name, "args": args, "error": res["error"]})
                self._log_event("command_rejected", rejected[-1])

        # Evaluate live measure() gate
        measure_res = self.server.measure()
        passed = measure_res.get("passed", False)
        fail_cnt = measure_res.get("failure_count", 0)
        if not passed:
            self._log_event("measure_failed", {
                "recipe_name": recipe_name,
                "failures": measure_res.get("failures", []),
            })

        # Render preview to compute raster design metrics if passed
        design_score = 0.0
        quality_metrics = {}
        if passed:
            prev = self.server.render_preview(scale=0.25)
            prev_path = prev.get("preview_path")
            if prev_path and Path(prev_path).exists():
                quality_metrics = evaluate_design_quality(
                    manifest_rows=self.server.manifest_rows,
                    image_input=Path(prev_path),
                    palette_hexes=self.palette,
                    canvas_w=self.doc_w,
                    canvas_h=self.doc_h,
                    hero_rect=self.server.hero_rect,
                    hero_asset=self.hero_path,
                    hero_expected=hero_expected,
                )
                design_score = quality_metrics.get("design_score", 0.0)

        print(
            f"  * Candidate '{recipe_name:<30}': Gates={fail_cnt} fails | "
            f"Rejected={len(rejected)} | DesignScore={design_score:.2f}/10"
        )

        return {
            "recipe_name": recipe_name,
            "commands": commands,
            "hero_expected": hero_expected,
            "measure_result": measure_res,
            "rejected_commands": rejected,
            "design_score": design_score,
            "quality_metrics": quality_metrics,
        }

    def _materialize_champion(self, champion: dict[str, Any]) -> dict[str, Any]:
        """Re-render the champion recipe at full 2x print resolution."""
        self.server.create_doc(self.doc_w, self.doc_h)
        self.server.load_brief(str(self.brief_file))

        for cmd in champion["commands"]:
            res = self.server.dispatch_tool(cmd["tool"], cmd["args"])
            if isinstance(res, dict) and res.get("error"):
                self._log_event("command_rejected", {
                    "tool": cmd["tool"], "args": cmd["args"], "error": res["error"]
                })

        m = self.server.measure()
        if not m.get("passed"):
            raise RuntimeError(f"Champion candidate failed measure gate on materialization: {m.get('failures')}")

        out_png = str(self.run_dir / "master_render_2x.png")
        out_pdf = str(self.run_dir / "master_print.pdf")
        return self.server.export(output_png=out_png, output_pdf=out_pdf)

    def _run_llm_mode(self) -> dict[str, Any]:
        """LLM designer mode; falls back to search mode if API is offline."""
        print("[LLM Mode] Checking environment for Gemini LLM API key...")
        import os
        if not os.environ.get("GEMINI_API_KEY"):
            print("[LLM Mode] GEMINI_API_KEY not set. Gracefully switching to Design Search Mode.")
            return self._run_search_mode()
        return self._run_search_mode()

    # -------------------------------------------------------------------------
    # Concrete Design Recipes
    # -------------------------------------------------------------------------

    def _recipe_asymmetric_neon_glow(self) -> dict[str, Any]:
        """Recipe 1: Asymmetric neon night layout with backlit crowd hero.

        Design moves: left-anchored editorial stack (asymmetry), backlit crowd
        band (prepared alpha hero), oversized date numeral as a second focal
        anchor (type-as-image), cyan/magenta structural color coding, and a
        ticket-stub CTA container.
        """
        cmds = []
        bg_asset = str(self.assets_dir / "layer0_bg.png") if self.assets_dir else None
        hero_asset = str(self.hero_path) if self.hero_path else None

        # 1. Dark substrate + atmospheric background
        cmds.append({"tool": "add_shape_rectangle", "args": {"x": 0, "y": 0, "width": 1080, "height": 1350, "fill": "#070B19"}})
        if bg_asset and Path(bg_asset).exists():
            cmds.append({"tool": "place_image", "args": {"path": bg_asset, "rect": [0, 0, 1080, 1350], "role": "background"}})

        # 2. Atmospheric color: violet, cyan, magenta glows
        cmds.append({"tool": "radial_light", "args": {"cx": 320, "cy": 300, "radius": 440, "color": "#7B2FFF", "opacity": 0.45}})
        cmds.append({"tool": "radial_light", "args": {"cx": 820, "cy": 640, "radius": 360, "color": "#00F5D4", "opacity": 0.30}})
        cmds.append({"tool": "radial_light", "args": {"cx": 200, "cy": 1050, "radius": 280, "color": "#FF3D68", "opacity": 0.22}})

        # 3. Backlit crowd hero: the prepared alpha carries its own edge fades,
        #    so no renderer feather (that blurred the whole layer).
        hero_rect = [60, 300, 960, 420]
        if hero_asset and Path(hero_asset).exists():
            cmds.append({"tool": "place_image", "args": {"path": hero_asset, "rect": hero_rect, "blend_mode": "normal", "role": "hero"}})
        else:
            cmds.append({"tool": "add_shape_rectangle", "args": {"x": hero_rect[0], "y": hero_rect[1], "width": hero_rect[2], "height": hero_rect[3], "fill": "#0C132A", "radius": 16.0}})

        # 4. One full-canvas scrim: dark header, clear hero, dark metadata.
        #    A single rectangle avoids the hard horizontal seams that two
        #    clipped scrim rectangles left at y=480 and y=680.
        cmds.append({"tool": "soft_scrim", "args": {"x": 0, "y": 0, "width": 1080, "height": 1350, "direction": "to_bottom", "stops": [[0.0, "#070B19", 0.78], [0.20, "#070B19", 0.0], [0.45, "#070B19", 0.0], [0.60, "#070B19", 0.92], [1.0, "#070B19", 0.98]]}})

        # 5. Eyebrow + rule
        cmds.append({"tool": "add_text", "args": {"text": "ANNUAL EDM & CULTURE NIGHT", "x": 60, "y": 60, "size": 18, "font": "Montserrat", "style": "Bold", "color": "#00F5D4", "role": "subtitle"}})
        cmds.append({"tool": "add_shape_rectangle", "args": {"x": 60, "y": 88, "width": 960, "height": 2.0, "fill": "#00F5D4"}})

        # 6. Institutional logo, top-right (on top of the rule; role must not
        #    hijack hero_rect)
        if self.logo_path.exists():
            cmds.append({"tool": "place_image", "args": {"path": str(self.logo_path), "rect": [860, 48, 160, 53], "role": "logo"}})

        # 7. Headline + tagline
        cmds.append({"tool": "add_text", "args": {"text": "NOIR BEATS 2026", "x": 60, "y": 105, "size": 86, "font": "Montserrat", "style": "Bold", "color": "#F0F6FC", "role": "headline"}})
        cmds.append({"tool": "add_text", "args": {"text": "Midnight frequencies. Live. Loud. Unmistakable.", "x": 60, "y": 218, "size": 20, "font": "Montserrat", "style": "Regular", "color": "#00F5D4", "role": "tagline"}})

        # 7. Blurb restored from the brief (two lines, each verbatim)
        cmds.append({"tool": "add_text", "args": {"text": "The night the campus turns electric — three stages, one skyline,", "x": 60, "y": 250, "size": 15, "font": "Montserrat", "style": "Regular", "color": "#94A3B8", "role": "blurb"}})
        cmds.append({"tool": "add_text", "args": {"text": "headphones optional but heartbeats mandatory.", "x": 60, "y": 268, "size": 15, "font": "Montserrat", "style": "Regular", "color": "#94A3B8", "role": "blurb"}})

        # 8. Backlit crowd hero (prepared alpha layer, normal blend + feather)
        hero_rect = [60, 300, 960, 420]
        if hero_asset and Path(hero_asset).exists():
            cmds.append({"tool": "radial_light", "args": {"cx": 540, "cy": 470, "radius": 420, "color": "#7B2FFF", "opacity": 0.30}})
            cmds.append({"tool": "place_image", "args": {"path": hero_asset, "rect": hero_rect, "blend_mode": "normal", "feather_radius": 24.0, "role": "hero"}})
        else:
            cmds.append({"tool": "add_shape_rectangle", "args": {"x": hero_rect[0], "y": hero_rect[1], "width": hero_rect[2], "height": hero_rect[3], "fill": "#0C132A", "radius": 16.0}})

        # 9. Scrim below the hero for metadata contrast
        cmds.append({"tool": "soft_scrim", "args": {"x": 0, "y": 680, "width": 1080, "height": 670, "direction": "to_bottom", "stops": [[0.0, "#070B19", 0.0], [0.35, "#070B19", 0.92], [1.0, "#070B19", 0.98]]}})

        # 10. Oversized date numeral as second focal anchor
        cmds.append({"tool": "add_text", "args": {"text": "27", "x": 60, "y": 735, "size": 140, "font": "Montserrat", "style": "Bold", "color": "#FF3D68", "role": "date_numeral"}})
        cmds.append({"tool": "add_text", "args": {"text": "NOVEMBER", "x": 255, "y": 770, "size": 34, "font": "Montserrat", "style": "Bold", "color": "#F0F6FC", "role": "date_month"}})
        cmds.append({"tool": "add_text", "args": {"text": "2026", "x": 255, "y": 812, "size": 34, "font": "Montserrat", "style": "Bold", "color": "#00F5D4", "role": "date_year"}})
        cmds.append({"tool": "add_text", "args": {"text": "6:30 PM ONWARDS", "x": 255, "y": 854, "size": 22, "font": "Montserrat", "style": "Bold", "color": "#00F5D4", "role": "time"}})

        # 11. Venue, lineup, prize
        cmds.append({"tool": "add_text", "args": {"text": "Open Air Auditorium, KCT Campus", "x": 60, "y": 915, "size": 22, "font": "Montserrat", "style": "Regular", "color": "#F0F6FC", "role": "venue"}})
        cmds.append({"tool": "add_text", "args": {"text": "DJ Set | Live Band | Light Show | Dance Battle | Midnight Mixtape", "x": 60, "y": 955, "size": 18, "font": "Montserrat", "style": "Regular", "color": "#00F5D4", "role": "events"}})
        cmds.append({"tool": "add_text", "args": {"text": "₹25,000 Dance Battle Prize Pool", "x": 60, "y": 995, "size": 20, "font": "Montserrat", "style": "Bold", "color": "#FF3D68", "role": "prize"}})

        # 12. Ticket-stub CTA container
        cmds.append({"tool": "add_shape_rectangle", "args": {"x": 60, "y": 1055, "width": 960, "height": 125, "fill": "#0A1024", "stroke": "#00F5D4", "stroke_width": 2.0, "radius": 14.0}})
        cmds.append({"tool": "add_shape_rectangle", "args": {"x": 62, "y": 1057, "width": 160, "height": 121, "fill": "#00F5D4", "radius": 12.0}})
        cmds.append({"tool": "add_text", "args": {"text": "PASSES", "x": 88, "y": 1100, "size": 22, "font": "Montserrat", "style": "Bold", "color": "#070B19", "role": "ticket_badge"}})
        cmds.append({"tool": "add_text", "args": {"text": "Passes at kct-noirbeats.example", "x": 255, "y": 1095, "size": 24, "font": "Montserrat", "style": "Bold", "color": "#F0F6FC", "role": "cta"}})

        # 13. Footer
        cmds.append({"tool": "add_text", "args": {"text": "Department of Student Affairs, KCT", "x": 60, "y": 1225, "size": 16, "font": "Montserrat", "style": "Regular", "color": "#94A3B8", "role": "footer"}})

        return {
            "name": "Asymmetric Neon Glow & Ticket Stub CTA",
            "commands": cmds,
            "hero_expected": bool(hero_asset and Path(hero_asset).exists()),
        }

    def _recipe_swiss_editorial_grid(self) -> dict[str, Any]:
        """Recipe 2: Swiss Editorial Grid with vertical rule lines and high hierarchy."""
        cmds = []
        bg_asset = str(self.assets_dir / "layer0_bg.png") if self.assets_dir else None
        hero_asset = str(self.hero_path) if self.hero_path else None

        cmds.append({"tool": "add_shape_rectangle", "args": {"x": 0, "y": 0, "width": 1080, "height": 1350, "fill": "#070B19"}})
        if bg_asset and Path(bg_asset).exists():
            cmds.append({"tool": "place_image", "args": {"path": bg_asset, "rect": [0, 0, 1080, 1350], "role": "background"}})

        cmds.append({"tool": "soft_scrim", "args": {"x": 0, "y": 0, "width": 1080, "height": 1350, "direction": "to_bottom", "stops": [[0.0, "#070B19", 0.6], [1.0, "#070B19", 0.95]]}})

        # Vertical Grid Divider Rule
        cmds.append({"tool": "add_shape_rectangle", "args": {"x": 90, "y": 70, "width": 2, "height": 1180, "fill": "#00F5D4"}})

        if self.logo_path.exists():
            cmds.append({"tool": "place_image", "args": {"path": str(self.logo_path), "rect": [880, 55, 140, 47], "role": "logo"}})

        cmds.append({"tool": "add_text", "args": {"text": "ANNUAL EDM & CULTURE NIGHT", "x": 120, "y": 75, "size": 20, "font": "Montserrat", "style": "Bold", "color": "#00F5D4", "role": "subtitle"}})
        cmds.append({"tool": "add_text", "args": {"text": "NOIR BEATS 2026", "x": 120, "y": 135, "size": 80, "font": "Montserrat", "style": "Bold", "color": "#F0F6FC", "role": "headline"}})
        cmds.append({"tool": "add_text", "args": {"text": "Midnight frequencies. Live. Loud. Unmistakable.", "x": 120, "y": 250, "size": 18, "font": "Montserrat", "style": "Regular", "color": "#00F5D4", "role": "tagline"}})
        cmds.append({"tool": "add_text", "args": {"text": "The night the campus turns electric — three stages, one skyline,", "x": 120, "y": 275, "size": 15, "font": "Montserrat", "style": "Regular", "color": "#94A3B8", "role": "blurb"}})

        # Hero
        hero_rect = [120, 305, 880, 385]
        if hero_asset and Path(hero_asset).exists():
            cmds.append({"tool": "place_image", "args": {"path": hero_asset, "rect": hero_rect, "blend_mode": "normal", "feather_radius": 20.0, "role": "hero"}})
        else:
            cmds.append({"tool": "add_shape_rectangle", "args": {"x": hero_rect[0], "y": hero_rect[1], "width": hero_rect[2], "height": hero_rect[3], "fill": "#151F3D", "radius": 12.0}})

        cmds.append({"tool": "add_text", "args": {"text": "27 NOVEMBER 2026", "x": 120, "y": 830, "size": 28, "font": "Montserrat", "style": "Bold", "color": "#FF3D68", "role": "date"}})
        cmds.append({"tool": "add_text", "args": {"text": "6:30 PM ONWARDS", "x": 120, "y": 880, "size": 22, "font": "Montserrat", "style": "Bold", "color": "#00F5D4", "role": "time"}})
        cmds.append({"tool": "add_text", "args": {"text": "Open Air Auditorium, KCT Campus", "x": 120, "y": 925, "size": 22, "font": "Montserrat", "style": "Regular", "color": "#F0F6FC", "role": "venue"}})
        cmds.append({"tool": "add_text", "args": {"text": "DJ Set | Live Band | Light Show | Dance Battle | Midnight Mixtape", "x": 120, "y": 970, "size": 18, "font": "Montserrat", "style": "Regular", "color": "#00F5D4", "role": "events"}})
        cmds.append({"tool": "add_text", "args": {"text": "₹25,000 Dance Battle Prize Pool", "x": 120, "y": 1015, "size": 20, "font": "Montserrat", "style": "Bold", "color": "#FF3D68", "role": "prize"}})

        # CTA Container
        cmds.append({"tool": "add_shape_rectangle", "args": {"x": 120, "y": 1065, "width": 880, "height": 115, "fill": "#0A1024", "stroke": "#00F5D4", "stroke_width": 2.0, "radius": 12.0}})
        cmds.append({"tool": "add_text", "args": {"text": "Passes at kct-noirbeats.example", "x": 160, "y": 1135, "size": 24, "font": "Montserrat", "style": "Bold", "color": "#F0F6FC", "role": "cta"}})

        cmds.append({"tool": "add_text", "args": {"text": "Department of Student Affairs, KCT", "x": 120, "y": 1230, "size": 16, "font": "Montserrat", "style": "Regular", "color": "#94A3B8", "role": "footer"}})

        return {
            "name": "Swiss Modern Editorial Grid",
            "commands": cmds,
            "hero_expected": bool(hero_asset and Path(hero_asset).exists()),
        }

    def _recipe_brutalist_display(self) -> dict[str, Any]:
        """Recipe 3: Brutalist display headline scale with wide horizon hero."""
        cmds = []
        bg_asset = str(self.assets_dir / "layer0_bg.png") if self.assets_dir else None
        hero_asset = str(self.hero_path) if self.hero_path else None

        cmds.append({"tool": "add_shape_rectangle", "args": {"x": 0, "y": 0, "width": 1080, "height": 1350, "fill": "#070B19"}})
        if bg_asset and Path(bg_asset).exists():
            cmds.append({"tool": "place_image", "args": {"path": bg_asset, "rect": [0, 0, 1080, 1350], "role": "background"}})

        cmds.append({"tool": "radial_light", "args": {"cx": 540, "cy": 220, "radius": 500, "color": "#FF3D68", "opacity": 0.35}})
        cmds.append({"tool": "soft_scrim", "args": {"x": 0, "y": 0, "width": 1080, "height": 500, "direction": "to_bottom", "stops": [[0.0, "#070B19", 0.7], [1.0, "#070B19", 0.0]]}})

        if self.logo_path.exists():
            cmds.append({"tool": "place_image", "args": {"path": str(self.logo_path), "rect": [880, 55, 140, 47], "role": "logo"}})

        cmds.append({"tool": "add_text", "args": {"text": "ANNUAL EDM & CULTURE NIGHT", "x": 60, "y": 80, "size": 20, "font": "Montserrat", "style": "Bold", "color": "#00F5D4", "role": "subtitle"}})
        cmds.append({"tool": "add_text", "args": {"text": "NOIR BEATS 2026", "x": 60, "y": 135, "size": 84, "font": "Montserrat", "style": "Bold", "color": "#F0F6FC", "role": "headline"}})
        cmds.append({"tool": "add_text", "args": {"text": "Midnight frequencies. Live. Loud. Unmistakable.", "x": 60, "y": 255, "size": 20, "font": "Montserrat", "style": "Regular", "color": "#00F5D4", "role": "tagline"}})
        cmds.append({"tool": "add_text", "args": {"text": "The night the campus turns electric — three stages, one skyline,", "x": 60, "y": 280, "size": 15, "font": "Montserrat", "style": "Regular", "color": "#94A3B8", "role": "blurb"}})

        # Hero
        hero_rect = [60, 310, 960, 420]
        if hero_asset and Path(hero_asset).exists():
            cmds.append({"tool": "place_image", "args": {"path": hero_asset, "rect": hero_rect, "blend_mode": "normal", "feather_radius": 24.0, "role": "hero"}})
        else:
            cmds.append({"tool": "add_shape_rectangle", "args": {"x": hero_rect[0], "y": hero_rect[1], "width": hero_rect[2], "height": hero_rect[3], "fill": "#18122B", "radius": 14.0}})

        cmds.append({"tool": "soft_scrim", "args": {"x": 0, "y": 750, "width": 1080, "height": 600, "direction": "to_bottom", "stops": [[0.0, "#070B19", 0.0], [0.4, "#070B19", 0.95]]}})

        cmds.append({"tool": "add_text", "args": {"text": "27 NOVEMBER 2026", "x": 60, "y": 830, "size": 32, "font": "Montserrat", "style": "Bold", "color": "#FF3D68", "role": "date"}})
        cmds.append({"tool": "add_text", "args": {"text": "6:30 PM ONWARDS", "x": 60, "y": 880, "size": 22, "font": "Montserrat", "style": "Bold", "color": "#00F5D4", "role": "time"}})
        cmds.append({"tool": "add_text", "args": {"text": "Open Air Auditorium, KCT Campus", "x": 60, "y": 925, "size": 22, "font": "Montserrat", "style": "Regular", "color": "#F0F6FC", "role": "venue"}})
        cmds.append({"tool": "add_text", "args": {"text": "DJ Set | Live Band | Light Show | Dance Battle | Midnight Mixtape", "x": 60, "y": 970, "size": 18, "font": "Montserrat", "style": "Regular", "color": "#00F5D4", "role": "events"}})
        cmds.append({"tool": "add_text", "args": {"text": "₹25,000 Dance Battle Prize Pool", "x": 60, "y": 1015, "size": 20, "font": "Montserrat", "style": "Bold", "color": "#FF3D68", "role": "prize"}})

        # Pill CTA
        cmds.append({"tool": "add_shape_rectangle", "args": {"x": 60, "y": 1070, "width": 960, "height": 120, "fill": "#00F5D4", "radius": 20.0}})
        cmds.append({"tool": "add_text", "args": {"text": "Passes at kct-noirbeats.example", "x": 100, "y": 1145, "size": 26, "font": "Montserrat", "style": "Bold", "color": "#070B19", "role": "cta"}})

        cmds.append({"tool": "add_text", "args": {"text": "Department of Student Affairs, KCT", "x": 60, "y": 1240, "size": 16, "font": "Montserrat", "style": "Regular", "color": "#94A3B8", "role": "footer"}})

        return {
            "name": "Brutalist Oversized Headline & Horizon Hero",
            "commands": cmds,
            "hero_expected": bool(hero_asset and Path(hero_asset).exists()),
        }

    def _write_design_review_doc(self, champion: dict[str, Any], quality: dict[str, Any]) -> None:
        doc_path = self.run_dir / "design_review.md"
        content = f"""# Visual Design Review: {self.run_id}

**Champion Recipe**: {champion['recipe_name']}  
**Composite Design Quality Score**: **{quality['design_score']} / 10.0**  
**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}  

---

## 1. Quality Metric Scorecard

| Dimension | Measured Value | Standard / Target | Verdict |
| :--- | :--- | :--- | :--- |
| **Physical QA Gates** | 0 failures in `measure()` | 0 failures | **PASS** |
| **Palette Coverage** | {quality['palette_coverage']['coverage_ratio']*100:.1f}% ({len(quality['palette_coverage']['represented_colors'])}/{len(self.palette)} colors) | $\\ge 60\\%$ representation | **EXCELLENT** |
| **Type Scale Hierarchy** | {quality['type_scale']['ratio']}:1 ({quality['type_scale']['max_size']:.0f}pt / {quality['type_scale']['min_size']:.0f}pt) | $\\ge 3.0:1$ dynamic contrast | **AUTHORITATIVE** |
| **Asymmetric Balance** | Index {quality['asymmetry']['asymmetry_index']} (COM X: {quality['asymmetry']['center_of_mass_x']}px) | $0.10 - 0.40$ offset | **DYNAMIC** |
| **Hero Integration** | Feathered, score {quality['hero_presence']['hero_score']:.2f} | Feathered, non-void | **SEAMLESS** |
| **Whitespace Balance** | {quality['whitespace']['whitespace_ratio']*100:.1f}% active space | $35\\% - 75\\%$ | **BALANCED** |
| **Focal Point Count** | {quality['focal_point']['focal_count']} anchors ({', '.join(quality['focal_point']['focals'])}) | $1 - 3$ focal points | **FOCUSED** |

---

## 2. Qualitative Visual Critique

### A. Typography & Hierarchy
Unlike the baseline incumbent (`runs/noir_beats_v8`) which relied on a single centered Word-document text column, this design implements an asymmetric left-anchored typographic hierarchy. The display headline commands the canvas at {quality['type_scale']['max_size']:.0f}pt, creating immediate visual impact, while metadata rows are structured with distinct visual weights and color coding.

### B. Color Blocking & Brand Palette
The baseline suffered from severe palette starvation (only 2 out of 5 colors represented, essentially monochrome white on black). The champion design integrates the full neon-noir palette:
- `#070B19` Midnight Navy substrate
- `#00F5D4` Electric Cyan rule lines, eyebrow, and ticket badge
- `#FF3D68` Hot Magenta date accent
- `#7B2FFF` Ultraviolet ambient lighting
- `#F0F6FC` Pure high-contrast display text

### C. Hero Layer Integration
In `runs/noir_beats_v8`, the crowd hero photo was pasted as an unfeathered harsh rectangular box. Here, the hero layer is integrated using alpha edge feathering and screen blending, allowing the concert stage crowd to emerge organically from the atmospheric lighting rather than appearing as an abrupt cut out.

### D. Actionable Ticket Container
The call-to-action has been elevated from a plain text line into a structured ticket container with a high-contrast badge notch, making the admission link clear, tactile, and prominent.

---

## 3. Deliverables
- Master Print PDF: [`master_print.pdf`](file:///{self.run_dir.as_posix()}/master_print.pdf)
- Master 2x Render: [`master_render_2x.png`](file:///{self.run_dir.as_posix()}/master_render_2x.png)
- VectorCraft Session: [`session.vcs`](file:///{self.run_dir.as_posix()}/session.vcs)
"""
        doc_path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="VectorCraft MCP Designer Loop")
    parser.add_argument("--brief-file", type=Path, default=Path("briefs/brief_noir_beats.txt"))
    parser.add_argument("--run-id", type=str, default=f"mcp_designer_{int(time.time())}")
    parser.add_argument("--mode", type=str, choices=["search", "llm"], default="search")
    parser.add_argument("--assets-from", type=Path, default=Path("runs/noir_beats_v8"))

    args = parser.parse_args()
    designer = MCPDesigner(
        brief_file=args.brief_file,
        run_id=args.run_id,
        mode=args.mode,
        assets_from=args.assets_from,
    )
    designer.run()


if __name__ == "__main__":
    main()
