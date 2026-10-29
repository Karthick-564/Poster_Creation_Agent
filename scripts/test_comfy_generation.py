"""Test direct queueing of Ideogram 4.0 generation in ComfyUI."""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
import shutil

ENDPOINT = "http://127.0.0.1:8188"
WORKFLOW_TEMPLATE = Path("poster_agent/generators/ideogram_workflow_api.json")

def queue_prompt(prompt_workflow: dict, client_id: str = "agent_test") -> str:
    p = {"prompt": prompt_workflow, "client_id": client_id}
    data = json.dumps(p).encode("utf-8")
    req = urllib.request.Request(f"{ENDPOINT}/prompt", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode())
        return res["prompt_id"]

def wait_for_execution(prompt_id: str, timeout_s: int = 180) -> str:
    start_t = time.time()
    print(f"Waiting for ComfyUI execution (prompt_id: {prompt_id})...")
    while time.time() - start_t < timeout_s:
        try:
            req = urllib.request.Request(f"{ENDPOINT}/history/{prompt_id}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                history = json.loads(resp.read().decode())
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    # Look for node 158 (SaveImage)
                    if "158" in outputs and "images" in outputs["158"]:
                        img_info = outputs["158"]["images"][0]
                        filename = img_info["filename"]
                        subfolder = img_info.get("subfolder", "")
                        print(f"Generation complete! Output image: {filename}")
                        return filename
        except Exception as e:
            pass
        time.sleep(2)
    raise TimeoutError("ComfyUI generation timed out.")

def main():
    if not WORKFLOW_TEMPLATE.exists():
        print("Template missing:", WORKFLOW_TEMPLATE)
        return

    wf = json.loads(WORKFLOW_TEMPLATE.read_text(encoding="utf-8"))
    seed = 123456

    test_prompt = {
        "high_level_description": "A striking modern tech summit poster visual featuring an intricate glowing 3D AI neural core with holographic data streams, sleek dark glass aesthetics, and vibrant neon cyan accents.",
        "style_description": {
            "aesthetics": "Futuristic tech aesthetic, hyper-detailed 3D digital art, clean studio lighting, high contrast.",
            "lighting": "Volumetric neon rim lighting, glowing cyan and electric purple light rays.",
            "medium": "digital_art",
            "art_style": "futuristic 3D concept render with ample dark calm zones for typography",
            "color_palette": ["#0B132B", "#00F5D4", "#7209B7", "#FFFFFF"]
        },
        "compositional_deconstruction": {
            "background": "Deep textured obsidian gradient backdrop (#0B132B) with soft atmospheric fog and quiet space for poster text.",
            "elements": [
                {
                    "type": "centerpiece",
                    "bbox": [250, 150, 750, 850],
                    "desc": "A mesmerizing floating spherical artificial intelligence brain core made of crystalline light fibers and luminous geometric nodes, radiating cyan energy.",
                    "color_palette": ["#00F5D4", "#7209B7", "#FFFFFF"]
                }
            ]
        }
    }

    # Inject prompt and seed
    wf["98:24"]["inputs"]["text"] = json.dumps(test_prompt, indent=2)
    wf["98:18"]["inputs"]["noise_seed"] = seed
    wf["158"]["inputs"]["filename_prefix"] = f"Ideogram_Agent_Live_{seed}"

    prompt_id = queue_prompt(wf)
    print("Queued prompt:", prompt_id)
    out_file = wait_for_execution(prompt_id)
    
    src = Path("ComfyUI/output") / out_file
    dst = Path("runs") / out_file
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"Copied live AI poster artwork to: {dst}")

if __name__ == "__main__":
    main()

