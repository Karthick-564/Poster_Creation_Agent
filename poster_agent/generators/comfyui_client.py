"""Autonomous ComfyUI Generator for Multi-Layer Poster Assets.

Handles:
1. Background Generation (Ideogram 4.0).
2. Transparent RGBA Hero & Accent Cutouts (Qwen-Image 2.1 native alpha).
3. 3D Generative Headline Typography (Qwen-Image 2.1 native alpha).
"""
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path


class ComfyUIClient:
    """Direct client to local ComfyUI server for autonomous asset generation."""

    def __init__(self, endpoint: str = "http://127.0.0.1:8188"):
        self.endpoint = endpoint

    def is_alive(self) -> bool:
        """Check if ComfyUI server is reachable."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/system_stats")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def wait_for_completion(self, prompt_id: str, timeout_seconds: int = 180) -> dict | None:
        """Poll ComfyUI history until execution completes."""
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            try:
                req = urllib.request.Request(f"{self.endpoint}/history/{prompt_id}")
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if prompt_id in data:
                        return data[prompt_id]
            except Exception:
                pass
            time.sleep(2)
        return None

    def download_output_image(self, filename: str, subfolder: str, folder_type: str, dest_path: Path | str) -> Path:
        """Download rendered image from ComfyUI /view endpoint."""
        url = f"{self.endpoint}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, str(dest))
        return dest

    def generate_ideogram_background(
        self,
        description: str,
        palette: list[str],
        output_path: Path | str,
        prefix: str = "auto_bg",
    ) -> Path:
        """Generate full atmospheric poster background via Ideogram 4.0."""
        wf_path = Path(__file__).resolve().parent / "ideogram_workflow_api.json"
        with open(wf_path, "r", encoding="utf-8") as f:
            wf = json.load(f)

        ideogram_prompt = {
            "high_level_description": description,
            "style_description": {
                "aesthetics": "Rich, high-impact poster background art with deep atmospheric depth and luminous lighting.",
                "medium": "digital_illustration",
                "art_style": "cinematic digital painting, smooth atmospheric gradients, ethereal lighting.",
                "color_palette": palette[:5] if palette else ["#1B1040", "#7AE7C7", "#FF4D6D", "#FFB703"],
            },
            "compositional_deconstruction": {
                "background": f"{description}. Deep background atmosphere leaving space for floating hero elements.",
                "elements": [],
            },
        }

        wf["98:24"]["inputs"]["text"] = json.dumps(ideogram_prompt, indent=2)
        wf["158"]["inputs"]["filename_prefix"] = prefix
        if "37" in wf and "inputs" in wf["37"]:
            wf["37"]["inputs"]["resolution"] = "1080x1350 (4:5)"

        payload = json.dumps({"prompt": wf}).encode("utf-8")
        req = urllib.request.Request(f"{self.endpoint}/prompt", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            prompt_id = res.get("prompt_id")

        hist = self.wait_for_completion(prompt_id)
        if not hist or "outputs" not in hist:
            raise RuntimeError(f"Ideogram background generation failed or timed out for {prompt_id}")

        out_node = hist["outputs"].get("158", {})
        imgs = out_node.get("images", [])
        if not imgs:
            raise RuntimeError("No image output from Ideogram node 158")

        img_info = imgs[0]
        return self.download_output_image(
            filename=img_info["filename"],
            subfolder=img_info.get("subfolder", ""),
            folder_type=img_info.get("type", "output"),
            dest_path=output_path,
        )

    def generate_qwen_rgba(
        self,
        prompt: str,
        output_path: Path | str,
        prefix: str = "auto_qwen_rgba",
        width: int = 1024,
        height: int = 1024,
    ) -> Path:
        """Generate true transparent RGBA cutout via Qwen-Image 2.1 native alpha."""
        clean_prompt = prompt
        if "isolated on empty alpha channel" not in clean_prompt.lower():
            clean_prompt += ", isolated on empty alpha channel, transparent background, clean sticker cutout, 3D render, sharp edges, no background"

        workflow = {
            "1": {
                "inputs": {"unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default"},
                "class_type": "UNETLoader",
            },
            "2": {
                "inputs": {"clip_name": "qwen3vl_8b_fp8_scaled.safetensors", "type": "qwen_image"},
                "class_type": "CLIPLoader",
            },
            "3": {
                "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"},
                "class_type": "VAELoader",
            },
            "4": {
                "inputs": {"text": clean_prompt, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode",
            },
            "5": {
                "inputs": {
                    "text": "blurry, low quality, noise, solid background, white background, black background, text, watermark, hands, stand, base",
                    "clip": ["2", 0],
                },
                "class_type": "CLIPTextEncode",
            },
            "6": {
                "inputs": {"width": width, "height": height, "batch_size": 1},
                "class_type": "EmptySD3LatentImage",
            },
            "7": {
                "inputs": {
                    "seed": int(time.time() * 1000) % 1000000,
                    "steps": 20,
                    "cfg": 4.5,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["6", 0],
                },
                "class_type": "KSampler",
            },
            "8": {
                "inputs": {"samples": ["7", 0], "vae": ["3", 0]},
                "class_type": "VAEDecode",
            },
            "9": {
                "inputs": {"filename_prefix": prefix, "images": ["8", 0]},
                "class_type": "SaveImage",
            },
        }

        payload = json.dumps({"prompt": workflow}).encode("utf-8")
        req = urllib.request.Request(f"{self.endpoint}/prompt", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            prompt_id = res.get("prompt_id")

        hist = self.wait_for_completion(prompt_id)
        if not hist or "outputs" not in hist:
            raise RuntimeError(f"Qwen RGBA generation failed or timed out for {prompt_id}")

        out_node = hist["outputs"].get("9", {})
        imgs = out_node.get("images", [])
        if not imgs:
            raise RuntimeError("No image output from Qwen node 9")

        img_info = imgs[0]
        return self.download_output_image(
            filename=img_info["filename"],
            subfolder=img_info.get("subfolder", ""),
            folder_type=img_info.get("type", "output"),
            dest_path=output_path,
        )
