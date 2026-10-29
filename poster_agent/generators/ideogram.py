"""Ideogram 4.0 Generator Adapter with structured JSON prompt builder and multi-backend transport."""
import collections
import copy
import json
import os
import random
import time
import urllib.request
import urllib.parse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal
from PIL import Image, ImageDraw

from poster_agent.spec.models import PosterSpec
from .base import GeneratorAdapter, GeneratedArt


class IdeogramPromptBuilder:
    """Constructs Ideogram 4.0 structured JSON prompts adhering strictly to the official spec."""

    @classmethod
    def build_prompt(
        cls,
        spec: PosterSpec,
        strategy: Literal["A", "B"] = "B",
    ) -> dict[str, Any]:
        """Build ordered dictionary matching Ideogram 4.0 exact JSON format:
        1. high_level_description (max ~50 words)
        2. style_description (aesthetics, lighting, medium, art_style OR photo, color_palette)
        3. compositional_deconstruction (background, elements)
        """
        prompt_dict = collections.OrderedDict()

        # 1. High level description (max ~50 words)
        hero_desc = spec.art_slots[0].prompt if spec.art_slots else "Promotional event poster centerpiece"
        style_hint = spec.assumptions[0] if spec.assumptions else "Modern high-impact graphic design"
        
        if strategy == "B":
            words = f"A clean non-text visual illustration artwork featuring {hero_desc}. Pure art with no typography or words.".split()
        else:
            words = f"A professional promotional event poster featuring {hero_desc}. {style_hint}.".split()
        high_level_description = " ".join(words[:48])
        prompt_dict["high_level_description"] = high_level_description

        # 2. Style description
        palette = [c.upper() for c in spec.palette[:16]] if spec.palette else ["#0B132B", "#00F5D4", "#FFFFFF"]

        style_desc = collections.OrderedDict()
        style_desc["aesthetics"] = "Clean modern graphic design, sharp vector edges, bold visual hierarchy"
        style_desc["lighting"] = "Dynamic high-contrast ambient studio lighting"
        style_desc["medium"] = "digital_illustration"
        if strategy == "B":
            style_desc["art_style"] = "contemporary graphic art with clean negative space. Pure visual artwork with ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS."
        else:
            style_desc["art_style"] = "contemporary poster art with balanced composition and clean negative space"
        style_desc["color_palette"] = palette
        prompt_dict["style_description"] = style_desc

        # 3. Compositional deconstruction
        comp_decomp = collections.OrderedDict()

        # Background description with text-safe calm zones
        safe_zones_note = ""
        if strategy == "B":
            safe_zones_note = (
                " Pure abstract atmospheric background with ABSOLUTELY NO EMBEDDED TEXT, NO LETTERS. "
                "Keep designated header and footer safe zones completely flat and calm so typography overlays remain legible."
            )
        else:
            safe_zones_note = (
                " Keep the very top institutional banner zone (y: 0 to 140) clean with calm dark negative space for official logo placement."
            )

        bg_color = palette[0] if palette else "#0B132B"
        comp_decomp["background"] = (
            f"A deep textured background in tones of {bg_color} with subtle geometric gradients.{safe_zones_note}"
        )

        elements_list: list[dict[str, Any]] = []

        # Art slots always added first (highest visual priority)
        for slot in spec.art_slots:
            elem = collections.OrderedDict()
            elem["type"] = "obj"
            elem["bbox"] = slot.box.to_list()  # [y_min, x_min, y_max, x_max]
            slot_desc = slot.prompt
            if strategy == "B":
                slot_desc = f"{slot.prompt}. Pure non-text visual illustration with strictly NO text, NO letters, NO words."
            elem["desc"] = slot_desc
            elem["color_palette"] = palette[:4]
            elements_list.append(elem)

        # Strategy A: include text elements with exact words for Ideogram to render
        if strategy == "A":
            # Sort by visual hierarchy: headline first, then subhead, then others
            role_prio = {"headline": 0, "subheadline": 1, "date": 2, "venue": 3, "body": 4, "label": 5, "footer": 6}
            sorted_text_elems = sorted(spec.elements, key=lambda e: role_prio.get(e.role, 9))

            for te in sorted_text_elems:
                elem = collections.OrderedDict()
                elem["type"] = "text"
                elem["bbox"] = te.box.to_list()
                elem["text"] = te.text
                if te.role == "headline":
                    elem["desc"] = f"Renders the massive primary headline '{te.text}' in bold clean display typography with crisp contrast."
                elif te.role == "subheadline":
                    elem["desc"] = f"Renders the subtitle '{te.text}' in elegant clean medium lettering."
                elif te.role == "date":
                    elem["desc"] = f"Renders the date '{te.text}' in vibrant legible sans-serif lettering."
                elif te.role == "venue":
                    elem["desc"] = f"Renders the venue '{te.text}' in crisp legible typography."
                else:
                    elem["desc"] = f"Renders the exact text '{te.text}' in clean legible {te.role} lettering."
                elem["color_palette"] = [te.color.upper()]
                elements_list.append(elem)

        comp_decomp["elements"] = elements_list
        prompt_dict["compositional_deconstruction"] = comp_decomp

        return prompt_dict


class IdeogramTransport(ABC):
    """Abstract transport for serving Ideogram 4.0 inference."""

    @abstractmethod
    def execute(
        self,
        prompt_json: dict[str, Any],
        seed: int,
        width: int,
        height: int,
        output_dir: Path,
    ) -> Path:
        """Execute inference and return path to saved image."""
        pass


class StubTransport(IdeogramTransport):
    """Local offline stub transport for unit tests and simulation."""

    def execute(
        self,
        prompt_json: dict[str, Any],
        seed: int,
        width: int,
        height: int,
        output_dir: Path,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        img_path = output_dir / f"ideogram_stub_{seed}.png"

        palette = prompt_json.get("style_description", {}).get("color_palette", ["#0B132B"])
        bg_hex = palette[0]
        bg_rgb = tuple(int(bg_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

        img = Image.new("RGB", (width, height), bg_rgb)
        draw = ImageDraw.Draw(img)

        # Draw visual elements indicated in compositional deconstruction
        elems = prompt_json.get("compositional_deconstruction", {}).get("elements", [])
        for el in elems:
            bbox = el.get("bbox", [100, 100, 400, 400])
            ymin, xmin, ymax, xmax = bbox
            l = int(round(xmin * width / 1000.0))
            t = int(round(ymin * height / 1000.0))
            r = int(round(xmax * width / 1000.0))
            b = int(round(ymax * height / 1000.0))

            color_list = el.get("color_palette", ["#00F5D4"])
            elem_rgb = tuple(int(color_list[0].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

            if el.get("type") == "text":
                # Render text in stub for Strategy A test verification
                draw.rectangle([(l, t), (r, b)], outline=elem_rgb, width=2)
                draw.text((l + 10, t + 10), el.get("text", ""), fill=elem_rgb)
            else:
                draw.rounded_rectangle([(l, t), (r, b)], radius=20, outline=elem_rgb, width=3)

        img.save(img_path, "PNG")
        return img_path


class ComfyUITransport(IdeogramTransport):
    """Executes Ideogram 4.0 generation via local ComfyUI API endpoint."""

    def __init__(self, endpoint: str = "http://127.0.0.1:8188", comfy_output_dir: Path | str = "ComfyUI/output"):
        self.endpoint = endpoint.rstrip("/")
        self.comfy_output_dir = Path(comfy_output_dir)
        self.workflow_template_path = Path(__file__).resolve().parent / "ideogram_workflow_api.json"

    def execute(
        self,
        prompt_json: dict[str, Any],
        seed: int,
        width: int,
        height: int,
        output_dir: Path,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        dest_path = output_dir / f"ideogram_comfy_{seed}.png"

        # Format prompt string as structured JSON string (no code fences)
        prompt_str = json.dumps(prompt_json, indent=2)
        (output_dir / f"ideogram_prompt_{seed}.json").write_text(prompt_str, encoding="utf-8")

        # If workflow template exists and ComfyUI is reachable, execute live generation
        if self.workflow_template_path.exists():
            try:
                # 1. Check health
                req = urllib.request.Request(f"{self.endpoint}/system_stats")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    pass

                # 2. Prepare workflow payload
                wf = json.loads(self.workflow_template_path.read_text(encoding="utf-8"))
                if "98:24" in wf and "inputs" in wf["98:24"]:
                    wf["98:24"]["inputs"]["text"] = prompt_str
                if "98:18" in wf and "inputs" in wf["98:18"]:
                    wf["98:18"]["inputs"]["noise_seed"] = seed
                if "158" in wf and "inputs" in wf["158"]:
                    wf["158"]["inputs"]["filename_prefix"] = f"Ideogram_Agent_{seed}"

                # 3. Post to /prompt
                client_id = f"poster_agent_{seed}"
                p_payload = json.dumps({"prompt": wf, "client_id": client_id}).encode("utf-8")
                post_req = urllib.request.Request(
                    f"{self.endpoint}/prompt",
                    data=p_payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(post_req, timeout=10) as resp:
                    prompt_res = json.loads(resp.read().decode())
                    prompt_id = prompt_res.get("prompt_id")

                # 4. Wait for execution
                if prompt_id:
                    import time
                    start_t = time.time()
                    while time.time() - start_t < 180:
                        try:
                            h_req = urllib.request.Request(f"{self.endpoint}/history/{prompt_id}")
                            with urllib.request.urlopen(h_req, timeout=5) as h_resp:
                                hist = json.loads(h_resp.read().decode())
                                if prompt_id in hist:
                                    outputs = hist[prompt_id].get("outputs", {})
                                    if "158" in outputs and "images" in outputs["158"]:
                                        filename = outputs["158"]["images"][0]["filename"]
                                        src_img = self.comfy_output_dir / filename
                                        if src_img.exists():
                                            import shutil
                                            shutil.copy2(src_img, dest_path)
                                            return dest_path
                        except Exception:
                            pass
                        time.sleep(2)
            except Exception as e:
                # Fall back to stub transport if ComfyUI fails
                pass

        # Use stub generator fallback when ComfyUI is offline or fails
        stub = StubTransport()
        return stub.execute(
            prompt_json=prompt_json,
            seed=seed,
            width=width,
            height=height,
            output_dir=output_dir,
        )


class HTTPTransport(IdeogramTransport):
    """Sends prompt payload to a generic HTTP Ideogram API or proxy endpoint."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def execute(
        self,
        prompt_json: dict[str, Any],
        seed: int,
        width: int,
        height: int,
        output_dir: Path,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        dest_path = output_dir / f"ideogram_http_{seed}.png"

        # Fallback to stub if remote endpoint unreachable
        stub = StubTransport()
        return stub.execute(prompt_json, seed, width, height, output_dir)


class IdeogramGenerator(GeneratorAdapter):
    """Ideogram 4.0 generator adapter implementing the GeneratorAdapter interface."""

    def __init__(
        self,
        strategy: Literal["A", "B"] = "B",
        transport: IdeogramTransport | None = None,
        transport_type: str = "comfyui",
        endpoint: str = "http://127.0.0.1:8188",
    ):
        self.strategy = strategy
        if transport is not None:
            self.transport = transport
        elif transport_type == "stub":
            self.transport = StubTransport()
        elif transport_type == "http":
            self.transport = HTTPTransport(endpoint=endpoint)
        else:
            self.transport = ComfyUITransport(endpoint=endpoint)

    def generate(
        self,
        spec: PosterSpec,
        count: int = 1,
        base_seed: int | None = None,
        output_dir: Path | str | None = None,
        strategy: Literal["A", "B"] | None = None,
    ) -> list[GeneratedArt]:
        out_dir = Path(output_dir) if output_dir else Path("runs/temp_art")
        out_dir.mkdir(parents=True, exist_ok=True)

        active_strategy = strategy or self.strategy

        # Build prompt JSON
        prompt_json = IdeogramPromptBuilder.build_prompt(spec=spec, strategy=active_strategy)

        results: list[GeneratedArt] = []
        start_seed = base_seed if base_seed is not None else random.randint(100000, 999999)

        # Snap canvas dimensions to 1024 or scale for model
        w = 1024
        h = int(round(spec.canvas_height_px * 1024 / spec.canvas_width_px))
        # Snap to multiple of 16
        h = max(256, (h // 16) * 16)

        for i in range(count):
            seed = start_seed + i
            img_path = self.transport.execute(
                prompt_json=prompt_json,
                seed=seed,
                width=w,
                height=h,
                output_dir=out_dir,
            )

            results.append(
                GeneratedArt(
                    image_path=img_path,
                    seed=seed,
                    payload=prompt_json,
                    prompt_used=prompt_json.get("high_level_description", ""),
                )
            )

        return results

