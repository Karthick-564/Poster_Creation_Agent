"""Test Strategy A generation with Ideogram 4.0 in ComfyUI."""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
import shutil

ENDPOINT = "http://127.0.0.1:8188"
WORKFLOW_TEMPLATE = Path("poster_agent/generators/ideogram_workflow_api.json")

def queue_prompt(prompt_workflow: dict, client_id: str = "strategy_a_test") -> str:
    p = {"prompt": prompt_workflow, "client_id": client_id}
    data = json.dumps(p).encode("utf-8")
    req = urllib.request.Request(f"{ENDPOINT}/prompt", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode())
        return res["prompt_id"]

def wait_for_execution(prompt_id: str, timeout_s: int = 180) -> str:
    start_t = time.time()
    print(f"Waiting for Ideogram Strategy A execution (prompt_id: {prompt_id})...")
    while time.time() - start_t < timeout_s:
        try:
            req = urllib.request.Request(f"{ENDPOINT}/history/{prompt_id}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                history = json.loads(resp.read().decode())
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    if "158" in outputs and "images" in outputs["158"]:
                        img_info = outputs["158"]["images"][0]
                        filename = img_info["filename"]
                        print(f"Generation complete! Output image: {filename}")
                        return filename
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError("ComfyUI generation timed out.")

def main():
    wf = json.loads(WORKFLOW_TEMPLATE.read_text(encoding="utf-8"))
    seed = 888123

    strategy_a_prompt = {
        "high_level_description": "A high-impact promotional event poster with bold typography 'AI SUMMIT 2026' dominating the top, a glowing holographic 3D neural core centerpiece in the middle, and clean event date and venue details at the bottom.",
        "style_description": {
            "aesthetics": "Futuristic tech summit poster, hyper-crisp typography, 3D digital concept art, bold visual hierarchy.",
            "lighting": "Volumetric neon rim lighting, electric cyan and magenta glows.",
            "medium": "graphic_design",
            "art_style": "bold modern promotional poster with clean negative space and perfectly rendered lettering",
            "color_palette": ["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"]
        },
        "compositional_deconstruction": {
            "background": "Deep textured obsidian backdrop (#0B132B) with subtle ambient light gradient and dark calm zones.",
            "elements": [
                {
                    "type": "text",
                    "bbox": [80, 80, 200, 920],
                    "text": "AI SUMMIT 2026",
                    "desc": "Renders the massive primary headline 'AI SUMMIT 2026' in bold, clean white modern sans-serif typography (#FFFFFF) across the top.",
                    "color_palette": ["#FFFFFF"]
                },
                {
                    "type": "obj",
                    "bbox": [240, 100, 700, 900],
                    "desc": "A breathtaking 3D floating artificial intelligence neural core with crystalline light filaments, glowing cyan rings, and magenta energy pulses.",
                    "color_palette": ["#00F5D4", "#F72585", "#FFFFFF"]
                },
                {
                    "type": "text",
                    "bbox": [750, 80, 810, 600],
                    "text": "December 5, 2026",
                    "desc": "Renders the exact date 'December 5, 2026' in vibrant neon cyan sans-serif text (#00F5D4).",
                    "color_palette": ["#00F5D4"]
                },
                {
                    "type": "text",
                    "bbox": [820, 80, 870, 750],
                    "text": "Main Auditorium",
                    "desc": "Renders the venue 'Main Auditorium' in crisp white legible typography (#FFFFFF).",
                    "color_palette": ["#FFFFFF"]
                }
            ]
        }
    }

    # Inject prompt and seed
    wf["98:24"]["inputs"]["text"] = json.dumps(strategy_a_prompt, indent=2)
    wf["98:18"]["inputs"]["noise_seed"] = seed
    wf["158"]["inputs"]["filename_prefix"] = f"Ideogram_StrategyA_{seed}"

    prompt_id = queue_prompt(wf)
    print("Queued prompt:", prompt_id)
    out_file = wait_for_execution(prompt_id)

    src = Path("ComfyUI/output") / out_file
    dst = Path("runs") / f"strategy_a_test_{seed}.png"
    shutil.copy2(src, dst)
    print(f"Strategy A image saved to: {dst}")

if __name__ == "__main__":
    main()

