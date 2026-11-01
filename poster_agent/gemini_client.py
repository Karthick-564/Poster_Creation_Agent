"""Unified Gemini API client for layout planning and multimodal vision critique."""
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

load_dotenv()


class GeminiClient:
    """Client for Google Generative Language API with automatic model fallback."""

    FALLBACK_MODELS = [
        "gemini-flash-latest",
    ]

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment or .env file.")

    def _call_api(self, model: str, payload: dict[str, Any], timeout: int = 8) -> dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def generate_json(
        self,
        prompt: str,
        system_instruction: str = "",
        model_name: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Generate structured JSON using Gemini text reasoning with fast fallback."""
        models_to_try = [model_name] if model_name else self.FALLBACK_MODELS

        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": temperature,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        last_error = None
        for m in models_to_try:
            try:
                data = self._call_api(m, payload, timeout=8)
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return json.loads(text)
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"All Gemini models failed for generate_json. Last error: {last_error}")

    def critique_image(
        self,
        image_input: str | Path | bytes,
        prompt: str,
        system_instruction: str = "",
        model_name: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Critique an image using Gemini multimodal vision reasoning."""
        import io
        from PIL import Image

        if isinstance(image_input, (str, Path)):
            img = Image.open(image_input)
        else:
            img = Image.open(io.BytesIO(image_input))

        # Downscale to fast preview resolution to prevent 503/timeout payload limits
        if max(img.size) > 1024:
            img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=85)
        img_bytes = buf.getvalue()
        mime_type = "image/jpeg"

        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        models_to_try = [model_name] if model_name else self.FALLBACK_MODELS

        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [
                        {"inlineData": {"mimeType": mime_type, "data": img_b64}},
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": temperature,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        last_error = None
        for attempt in range(1):
            for m in models_to_try:
                try:
                    data = self._call_api(m, payload, timeout=6)
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return json.loads(text)
                except Exception as e:
                    last_error = e
                    continue

        raise RuntimeError(f"Gemini API rate-limited or unavailable: {last_error}")

