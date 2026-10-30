import json
import urllib.request
import urllib.error
import time

COMFY_URL = "http://127.0.0.1:8188"

def generate_aurora_bg():
    with open("poster_agent/generators/ideogram_workflow_api.json") as f:
        wf = json.load(f)

    aurora_prompt = {
        "high_level_description": "A dreamy night sky poster background with flowing aurora ribbons in mint, coral, and amber against a deep violet night sky with soft faint stars.",
        "style_description": {
            "aesthetics": "Dreamy, festive, warm night sky with ethereal glowing aurora borealis curtains and soft starlight.",
            "lighting": "Magical atmospheric glow, soft mint and coral light waves illuminating deep indigo shadows.",
            "medium": "digital_illustration",
            "art_style": "cinematic digital painting, ethereal fantasy sky, smooth atmospheric gradients.",
            "color_palette": ["#1B1040", "#7AE7C7", "#FF4D6D", "#FFB703", "#C9B8FF"]
        },
        "compositional_deconstruction": {
            "background": "Deep twilight indigo and violet night sky #1B1040 with faint distant stars and soft nebulas, leaving upper quarter and lower third open and calm for text.",
            "elements": [
                {
                    "type": "obj",
                    "bbox": [150, 50, 850, 950],
                    "desc": "Luminous flowing waves of aurora borealis ribbons shimmering in mint green #7AE7C7, warm coral #FF4D6D, and golden amber #FFB703 curving gracefully across the midground.",
                    "color_palette": ["#7AE7C7", "#FF4D6D", "#FFB703"]
                }
            ]
        }
    }

    wf["98:24"]["inputs"]["text"] = json.dumps(aurora_prompt, indent=2)
    wf["158"]["inputs"]["filename_prefix"] = "aurora_bg_ideogram"
    # Adjust aspect ratio / dimensions
    if "37" in wf and "inputs" in wf["37"]:
        wf["37"]["inputs"]["resolution"] = "1080x1350 (4:5)"

    payload = json.dumps({"prompt": wf}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=payload, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        prompt_id = res.get("prompt_id")
        print(f"Queued Ideogram Aurora Background! Prompt ID: {prompt_id}")
        return prompt_id

if __name__ == "__main__":
    generate_aurora_bg()

