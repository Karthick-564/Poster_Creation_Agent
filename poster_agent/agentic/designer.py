"""Stage 4: Autonomous Designer Agent Loop.

Orchestrates the designer LLM against the VectorCraft MCP server:
- System prompt provides verbatim fields, palette, locked obstacles, free calm regions,
  and the master typography doctrine.
- Enforces strict verbatim text validation and immutability of locked zones.
- Demands live measure() feedback and preview verification.
- Caps tool calls at 30 per turn.
- Persists designer_transcript.jsonl for complete auditability and replay.
"""
from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Optional

from poster_agent.agentic.llm_backend import LLMBackend, LLMResponse, ToolCall
from poster_agent.mcp.vectorcraft_server import VectorCraftMCPServer, estimate_text_width, _hex_to_rgb, _rgb_to_relative_luminance
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def _is_light_color(hex_str: str) -> bool:
    try:
        arr = np.array([[[c for c in _hex_to_rgb(hex_str)]]], dtype=np.float32)
        return float(_rgb_to_relative_luminance(arr)[0, 0]) > 0.45
    except Exception:
        return False

def _fit_size(text: str, target_size: float, max_w: float, font: str = "Inter") -> float:
    sz = float(target_size)
    lines = [l for l in text.split("\n") if l.strip()]
    while sz > 13.0:
        w = max((estimate_text_width(l, sz, font=font) for l in lines), default=0.0)
        if w <= max_w:
            break
        sz -= 2.0
    return max(sz, 13.0)

DESIGN_DOCTRINE = """
MASTER POSTER TYPOGRAPHY & COMPOSITION DOCTRINE:
1. VERBATIM COPY INVARIANT: Every single character placed via add_text MUST be an exact token/substring from the brief. Hallucinations or paraphrases are rejected by the server.
2. LOCKED ZONE IMMUTABILITY: The institutional logo, bottom legal footer, and QR code have already been placed as LOCKED items. Do not attempt to move or delete them. Treat their bounding boxes as obstacles.
3. CLEAR TYPOGRAPHIC HIERARCHY:
   - Headline / Title: Max 2 lines. Dominant focal anchor (size >= 64pt, uppercase or bold display).
   - Date / Time & Venue: Crucial logistics, high contrast (size >= 24pt).
   - Tagline / Subtitle: Supporting context (size 18-28pt).
   - Metadata / Body: Crisp readable body (size 14-20pt).
4. CONTRAST & READABILITY:
   - Every text row must maintain >= 4.5:1 WCAG relative luminance contrast against its background fill.
   - On dark canvases (#070B19, #1E2842), use #FFFFFF, #F0F6FC, or bright secondary accents (#00F5D4, #85CEBD).
5. MARGIN SAFETY & COLLISION AVOIDANCE:
   - All text and content must stay within safe canvas margins (typically 48px from left and right).
   - Check get_free_regions to discover calm coordinates not covered by locked zones or obstacles.
6. TOOL-CALL RHYTHM:
   - Call measure() every 3-5 actions to ensure 0 physical gate failures.
   - Target: measure() must pass with 0 failures.
"""


class DesignerStage:
    """Manages the interactive LLM designer session."""

    def __init__(
        self,
        server: VectorCraftMCPServer,
        backend: Optional[LLMBackend] = None,
        max_tool_calls: int = 30,
    ):
        self.server = server
        self.backend = backend
        self.max_tool_calls = max_tool_calls
        self.transcript: list[dict[str, Any]] = []

    def _log_turn(self, role: str, content: Any, tool_calls: Optional[list[Any]] = None) -> None:
        self.transcript.append({
            "timestamp": time.time(),
            "role": role,
            "content": content,
            "tool_calls": tool_calls or [],
        })

    def run(
        self,
        brief_fields: dict[str, str],
        palette: list[str],
        run_dir: Path,
        background_layer: Optional[str] = None,
        hero_layer: Optional[str] = None,
        zones: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Execute the interactive designer loop."""
        cw = self.server.doc_width or 1080.0
        ch = self.server.doc_height or 1920.0

        # Substrate background: place dark background rectangle first if not already present
        items = self.server.list_items()["items"]
        if not any(it["id"] == "bg_substrate" for it in items):
            bg_col = palette[0] if palette else "#070B19"
            self.server.add_shape_rectangle(
                x=0, y=0, width=cw, height=ch, fill=bg_col, item_id="bg_substrate"
            )

        # If background layer image exists, place it behind creative typography (if not already placed)
        if background_layer and Path(background_layer).exists() and not any(it["id"] == "bg_image" for it in items):
            self.server.place_image(
                path=str(background_layer),
                rect=[0, 0, cw, ch],
                role="background",
                item_id="bg_image",
            )

        # If hero layer exists, place it strictly according to single-source-of-truth zones
        if hero_layer and Path(hero_layer).exists():
            zh = None
            if zones and hasattr(zones, "hero"):
                zh = getattr(zones, "hero")
            elif isinstance(zones, dict) and "hero" in zones:
                zh = zones["hero"]

            if zh and len(zh) == 4:
                # [ymin, xmin, ymax, xmax] in 0..1000
                hero_x = (zh[1] / 1000.0) * cw
                hero_y = (zh[0] / 1000.0) * ch
                hero_w = ((zh[3] - zh[1]) / 1000.0) * cw
                hero_h = ((zh[2] - zh[0]) / 1000.0) * ch
            else:
                hero_w = min(cw * 0.85, 960.0)
                hero_h = min(ch * 0.32, 550.0)
                hero_x = (cw - hero_w) / 2.0
                hero_y = ch * 0.38

            self.server.place_image(
                path=str(hero_layer),
                rect=[hero_x, hero_y, hero_w, hero_h],
                blend_mode="normal",
                feather_radius=0.0,
                role="hero",
                item_id="hero_layer",
            )
            # Soft natural ambient contact shadow to ground the hero into the scene
            self.server.renderer.add_effect(
                effect_name="stylize.dropShadow",
                params={"x": 6.0, "y": 14.0, "blur": 22.0, "opacity": 0.40, "color": "#070B19"},
            )

        # Inspect initial free regions
        free_regions_info = self.server.get_free_regions()
        free_regions = free_regions_info.get("free_regions", [])

        # Build initial prompt
        system_prompt = (
            f"You are an expert poster designer. Design a print-ready poster on a {int(cw)}x{int(ch)} canvas.\n"
            f"Palette: {', '.join(palette)}\n"
            f"{DESIGN_DOCTRINE}\n\n"
            f"Available Calm/Free Regions (x, y, w, h):\n"
            + "\n".join(f"- Region: x={r['x']}, y={r['y']}, w={r['width']}, h={r['height']}" for r in free_regions[:6])
            + "\n\nVerbatim Brief Fields:\n"
            + "\n".join(f"- {k}: {v}" for k, v in brief_fields.items())
        )

        tools = self.server.get_tool_definitions()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please design the poster typography and layout. Inspect free regions, place the headline and key logistics, and ensure measure() passes with 0 failures."},
        ]

        total_tool_calls = 0
        measure_passed = False

        if self.backend:
            # Active LLM interactive loop
            turn = 0
            while total_tool_calls < self.max_tool_calls and turn < 12 and not measure_passed:
                turn += 1
                try:
                    resp = self.backend.chat(messages=messages, tools=tools)
                except Exception as exc:
                    self._log_turn("system_error", f"LLM backend exception: {exc}")
                    break

                self._log_turn("assistant", resp.content, [tc.__dict__ for tc in resp.tool_calls])
                if not resp.tool_calls:
                    # Model sent final text
                    break

                for tc in resp.tool_calls:
                    total_tool_calls += 1
                    t_name = tc.name
                    t_args = tc.arguments
                    tool_res = self.server.dispatch_tool(t_name, t_args)
                    self._log_turn("tool", tool_res, [{"name": t_name, "args": t_args}])

                    # Append tool result to conversation history
                    messages.append({
                        "role": "tool",
                        "content": json.dumps({"tool": t_name, "result": tool_res}),
                    })

                    if t_name == "measure":
                        if tool_res.get("passed"):
                            measure_passed = True
                            break

                    if total_tool_calls >= self.max_tool_calls:
                        break

        # If LLM did not complete all placements or was unavailable, complete with structured layout
        if not measure_passed:
            self._apply_structured_creative_layout(brief_fields, palette, cw, ch)
            m = self.server.measure()
            measure_passed = bool(m.get("passed", False))

        # Save transcript
        transcript_path = run_dir / "designer_transcript.jsonl"
        with open(transcript_path, "w", encoding="utf-8") as f:
            for entry in self.transcript:
                f.write(json.dumps(entry) + "\n")

        final_measure = self.server.measure()
        return {
            "measure_passed": final_measure.get("passed", False),
            "failure_count": final_measure.get("failure_count", 0),
            "measure_result": final_measure,
            "total_tool_calls": total_tool_calls,
            "transcript_path": str(transcript_path),
        }

    def _apply_structured_creative_layout(
        self,
        fields: dict[str, str],
        palette: list[str],
        cw: float,
        ch: float,
    ) -> None:
        """Place essential creative elements into free regions ensuring measure() passes."""
        # Find headline and date
        title = fields.get("title", "EVENT")
        date = fields.get("date") or fields.get("time", "")
        venue = fields.get("venue", "")
        tagline = fields.get("tagline") or fields.get("subtitle", "")
        cta = fields.get("cta", "")

        margin = max(48.0, cw * 0.05)
        text_w = cw - (2 * margin)

        placed_texts = {
            item.get("text", "").strip().lower()
            for item in self.server.list_items().get("items", [])
            if item.get("text")
        }

        def safe_add_text(t: str, x: float, y: float, sz: float, font: str, style: str, col: str, r: str, i_id: str) -> bool:
            clean = t.strip()
            if not clean or clean.lower() in placed_texts:
                return False
            res = self.server.add_text(text=clean, x=x, y=y, size=sz, font=font, style=style, color=col, role=r, item_id=i_id)
            if res.get("status") == "ok":
                placed_texts.add(clean.lower())
                return True
            return False

        # 1. Base canvas background & atmospheric radial glow
        items = self.server.list_items().get("items", [])
        primary_bg = palette[0] if palette else "#0B1021"
        is_light = _is_light_color(primary_bg)
        text_primary = "#111827" if is_light else "#FFFFFF"
        text_secondary = "#374151" if is_light else "#C8C7CC"
        text_sub = "#1F2937" if is_light else "#E2E8F0"

        # Determine high-contrast accent
        accent_cand = palette[1] if len(palette) > 1 else ("#0F766E" if is_light else "#00F5D4")
        if is_light and _is_light_color(accent_cand):
            accent = palette[-1] if not _is_light_color(palette[-1]) else "#0F766E"
        elif not is_light and not _is_light_color(accent_cand):
            accent = palette[-1] if _is_light_color(palette[-1]) else "#00F5D4"
        else:
            accent = accent_cand

        if not any(it.get("id") in ("bg_substrate", "base_canvas_bg", "bg_image") for it in items):
            self.server.add_shape_rectangle(
                x=0.0,
                y=0.0,
                width=cw,
                height=ch,
                fill=primary_bg,
                item_id="base_canvas_bg",
            )
        glow_col = accent
        self.server.radial_light(cx=cw * 0.3, cy=ch * 0.25, radius=380.0, color=glow_col, opacity=0.35)

        # 2. Band 0: Eyebrow (if provided and not duplicate, fallback to short subtitle)
        eyebrow = fields.get("eyebrow") or (fields.get("subtitle") if len(fields.get("subtitle", "")) < 40 else "")
        if eyebrow and eyebrow.strip().lower() not in placed_texts:
            eye_sz = _fit_size(eyebrow, 15.0, text_w, font="Inter")
            eye_y = max(52.0, ch * 0.08)
            safe_add_text(
                t=eyebrow,
                x=margin,
                y=eye_y,
                sz=eye_sz,
                font="Inter",
                style="Bold",
                col=accent,
                r="eyebrow",
                i_id="creative_eyebrow",
            )

        # 3. Band 1: Headline & Tagline (y in [0.15*ch, 0.35*ch])
        head_y = max(ch * 0.16, 180.0 if ch < 1500 else 300.0)
        target_head_sz = 68.0 if ch > 1500 else 52.0
        head_size = _fit_size(title, target_head_sz, text_w, font="Montserrat")
        safe_add_text(
            t=title,
            x=margin,
            y=head_y,
            sz=head_size,
            font="Montserrat",
            style="Bold",
            col=text_primary,
            r="headline",
            i_id="creative_headline",
        )

        curr_y = head_y + (head_size * 1.25)
        if tagline and tagline.strip().lower() not in placed_texts:
            tag_sz = _fit_size(tagline, 20.0, text_w, font="Inter")
            if safe_add_text(
                t=tagline,
                x=margin,
                y=curr_y,
                sz=tag_sz,
                font="Inter",
                style="Regular",
                col=accent,
                r="tagline",
                i_id="creative_tagline",
            ):
                curr_y += tag_sz * 1.5

        # 4. Band 2: Mid-canvas hook / Subtitle / Value statement (y in [0.35*ch, 0.55*ch])
        band2_y = max(ch * 0.36, curr_y + 30.0)
        secondary_text = fields.get("subtitle") or fields.get("closing line") or fields.get("blurb") or fields.get("section")
        hero_intersects = False
        avail_text_w = text_w
        if self.server.hero_rect:
            hx, hy, hw, hh = self.server.hero_rect
            if hx > margin + 220.0:
                # Asymmetric layout: hero is on right half, text column fits cleanly on left
                avail_text_w = min(text_w, hx - margin - 24.0)
                hero_intersects = False
            elif hy <= band2_y + 40.0 <= hy + hh:
                hero_intersects = True

        if secondary_text and not hero_intersects and band2_y < (ch * 0.55):
            sec_sz = _fit_size(secondary_text, 18.0, avail_text_w, font="Inter")
            safe_add_text(
                t=secondary_text,
                x=margin,
                y=band2_y,
                sz=sec_sz,
                font="Inter",
                style="Regular",
                col=text_sub,
                r="body",
                i_id="creative_secondary_hook",
            )

        # 5. Band 3: Logistics (Date, Venue, CTA) (y in [0.55*ch, 0.80*ch])
        logistics_y = max(ch * 0.58, 760.0 if ch < 1500 else 1150.0)
        logistics_w = text_w
        if self.server.hero_rect:
            hx, hy, hw, hh = self.server.hero_rect
            if hx > margin + 220.0:
                # Hero is on right side: logistics stay in left column without being pushed below hero
                logistics_w = min(text_w, hx - margin - 24.0)
            else:
                logistics_y = max(logistics_y, hy + hh + 20.0)
        if date:
            d_sz = _fit_size(date, 24.0, logistics_w, font="Inter")
            if safe_add_text(
                t=date,
                x=margin,
                y=logistics_y,
                sz=d_sz,
                font="Inter",
                style="Bold",
                col=text_primary,
                r="date",
                i_id="creative_date",
            ):
                logistics_y += (d_sz * 1.3) + 12.0

        if venue:
            v_sz = _fit_size(venue, 19.0, logistics_w, font="Inter")
            if safe_add_text(
                t=venue,
                x=margin,
                y=logistics_y,
                sz=v_sz,
                font="Inter",
                style="Regular",
                col=text_secondary,
                r="venue",
                i_id="creative_venue",
            ):
                logistics_y += (v_sz * 1.3) + 12.0

        if cta and not any(it.get("id") == "locked_qr_label" for it in self.server.list_items().get("items", [])):
            cta_sz = _fit_size(cta, 18.0, min(logistics_w, text_w * 0.5), font="Inter")
            safe_add_text(
                t=cta,
                x=margin,
                y=logistics_y,
                sz=cta_sz,
                font="Inter",
                style="Bold",
                col=accent,
                r="cta",
                i_id="creative_cta",
            )
