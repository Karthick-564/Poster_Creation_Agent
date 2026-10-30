import json
import urllib.request
import urllib.error

COMFY_URL = "http://127.0.0.1:8188"

def generate_orb():
    prompt_workflow = {
        "1": {
            "inputs": {
                "unet_name": "qwen_image_2.1_int8_convrot.safetensors",
                "weight_dtype": "default"
            },
            "class_type": "UNETLoader"
        },
        "2": {
            "inputs": {
                "clip_name": "qwen3vl_8b_fp8_scaled.safetensors",
                "type": "qwen_image"
            },
            "class_type": "CLIPLoader"
        },
        "3": {
            "inputs": {
                "vae_name": "qwen_image_2.1_vae_bf16.safetensors"
            },
            "class_type": "VAELoader"
        },
        "4": {
            "inputs": {
                "text": "A single luminous magical crystal glass orb sphere with swirling aurora borealis light in vibrant mint green #7AE7C7, coral pink #FF4D6D, and golden amber #FFB703 trapped gracefully inside, crystalline glass reflections, ethereal volumetric glow, isolated on empty alpha channel, transparent background, clean sticker cutout, 3D render, sharp edges, no text, no words, no hands, no stand",
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "5": {
            "inputs": {
                "text": "blurry, low quality, noise, solid background, white background, black background, text, words, labels, watermark, hands, base, pedestal",
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "6": {
            "inputs": {
                "width": 1024,
                "height": 1024,
                "batch_size": 1
            },
            "class_type": "EmptySD3LatentImage"
        },
        "7": {
            "inputs": {
                "seed": 334455,
                "steps": 20,
                "cfg": 4.5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0]
            },
            "class_type": "KSampler"
        },
        "8": {
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0]
            },
            "class_type": "VAEDecode"
        },
        "9": {
            "inputs": {
                "filename_prefix": "aurora_orb_hero",
                "images": ["8", 0]
            },
            "class_type": "SaveImage"
        }
    }

    payload = json.dumps({"prompt": prompt_workflow}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=payload, headers={"Content-Type": "application/json"})
    
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        prompt_id = res["prompt_id"]
        print(f"Queued Aurora Orb Hero generation! Prompt ID: {prompt_id}")
        return prompt_id

if __name__ == "__main__":
    generate_orb()

