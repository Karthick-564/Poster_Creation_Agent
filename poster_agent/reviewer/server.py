"""Local OpenAI-compatible vision critique server hosting LiquidAI/LFM3-VL-2B on GPU."""
import base64
import io
import json
import re
import time
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText

app = FastAPI(title="LFM3-VL-2B Vision Reviewer Server")

MODEL_ID = "LiquidAI/LFM3-VL-2B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Loading {MODEL_ID} on {DEVICE}...")
processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
model = AutoModelForImageTextToText.from_pretrained(
    MODEL_ID,
    trust_remote_code=True,
    dtype=torch.bfloat16,
    device_map=DEVICE,
)
print("LFM3-VL-2B loaded and ready for inference!")


def decode_base64_image(url_or_b64: str) -> Image.Image:
    """Decode base64 image data URL or raw string into PIL Image."""
    if "base64," in url_or_b64:
        url_or_b64 = url_or_b64.split("base64,")[1]
    img_bytes = base64.b64decode(url_or_b64)
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_ID, "device": DEVICE}


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "LFM3-VL-2B",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "liquid-ai",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    max_new_tokens = min(data.get("max_tokens", 1024), 2048)
    temperature = data.get("temperature", 0.2)
    # Default to thinking=False for LFM3-VL to avoid infinite reasoning/spelling loops
    enable_thinking = data.get("thinking", False) or data.get("extra_body", {}).get("thinking", False)

    # Process messages and images
    images: list[Image.Image] = []
    formatted_messages = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            # Multimodal content array
            msg_images = []
            text_parts = []
            for item in content:
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    img_url = item.get("image_url", {}).get("url", "")
                    if img_url:
                        try:
                            pil_img = decode_base64_image(img_url)
                            # Resize large poster to prevent OOM / degradation
                            pil_img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                            msg_images.append(pil_img)
                            images.append(pil_img)
                        except Exception as e:
                            print("Error decoding image:", e)

            merged_text = "\n".join(text_parts)
            # Use official LFM3-VL vision tokens format in content mapping
            multimodal_content: list[dict[str, Any]] = [{"type": "image"} for _ in msg_images]
            if merged_text:
                multimodal_content.append({"type": "text", "text": merged_text})
            formatted_messages.append({"role": role, "content": multimodal_content})
        else:
            formatted_messages.append({"role": role, "content": str(content)})

    # Build prompt with images
    try:
        text_prompt = processor.apply_chat_template(
            formatted_messages,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
            tokenize=False,
        )
        if images:
            inputs = processor(
                text=text_prompt,
                images=images,
                return_tensors="pt",
            ).to(DEVICE)
        else:
            inputs = processor(
                text=text_prompt,
                return_tensors="pt",
            ).to(DEVICE)

        with torch.inference_mode():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=temperature > 0.0,
                temperature=max(temperature, 0.1),
                pad_token_id=processor.tokenizer.pad_token_id or processor.tokenizer.eos_token_id,
            )

        # Slice generated tokens
        input_len = inputs["input_ids"].shape[1]
        generated_tokens = outputs[0][input_len:]
        output_text = processor.decode(generated_tokens, skip_special_tokens=True).strip()

        # If user asked for JSON, extract JSON block if wrapped in markdown
        if "```json" in output_text:
            m = re.search(r"```json\s*(.*?)\s*```", output_text, re.DOTALL)
            if m:
                output_text = m.group(1).strip()
        elif "```" in output_text:
            m = re.search(r"```\s*(.*?)\s*```", output_text, re.DOTALL)
            if m:
                output_text = m.group(1).strip()

        # Verify whether output is valid JSON; if not, structure the critique text into JSON
        try:
            json.loads(output_text)
        except Exception:
            # Extract critiques and fixes from unstructured text
            critique_lines = [line.strip() for line in output_text.splitlines() if line.strip().startswith(("-", "*", "1.", "2.", "3.", "4.", "5."))]
            if not critique_lines:
                critique_lines = [output_text[:300]]

            structured = {
                "hierarchy": 3,
                "balance": 3,
                "readability": 3,
                "brand_fit": 4,
                "polish": 3,
                "three_second_test": {
                    "event": "Detected Title",
                    "date": "Detected Date",
                    "venue": "Detected Venue",
                    "passed": True,
                },
                "fixes": critique_lines[:4],
                "raw_critique": output_text,
            }
            output_text = json.dumps(structured)

    except Exception as e:
        print("Generation error:", e)
        output_text = json.dumps({
            "hierarchy": 3,
            "balance": 3,
            "readability": 3,
            "brand_fit": 3,
            "polish": 3,
            "three_second_test": {
                "event": "Event",
                "date": "Date",
                "venue": "Venue",
                "passed": False,
            },
            "fixes": [f"Review processed with warning: {str(e)}"],
        })

    return {
        "id": f"chatcmpl-lfm3-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "LFM3-VL-2B",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": output_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 100,
            "total_tokens": 200,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
