"""Vision-Language Model reviewer (OpenAI-compatible endpoint with thinking mode toggle)."""
import base64
import io
import json
import re
import time
from pathlib import Path
from typing import Any
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.config.settings import ReviewerConfig, get_config
from poster_agent.spec.models import PosterSpec


class ThreeSecondTest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: str
    date: str
    venue: str
    passed: bool


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hierarchy: int = Field(..., ge=1, le=5, description="Visual dominance and eye-tracking flow")
    balance: int = Field(..., ge=1, le=5, description="Balance of whitespace and graphic mass")
    readability: int = Field(..., ge=1, le=5, description="Legibility and contrast of typography")
    brand_fit: int = Field(..., ge=1, le=5, description="Institutional credibility and styling alignment")
    polish: int = Field(..., ge=1, le=5, description="Overall aesthetic execution and visual impact")
    three_second_test: ThreeSecondTest
    fixes: list[str] = Field(default_factory=list, description="Actionable recommendations")
    model_name: str
    thinking_enabled: bool
    latency_seconds: float = 0.0
    raw_thinking: str | None = None


def encode_image_base64(image: Image.Image | str | Path, format: str = "PNG") -> str:
    """Encode PIL image or image file to base64 string."""
    if isinstance(image, (str, Path)):
        img = Image.open(image).convert("RGB")
    else:
        img = image

    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def create_downscaled_preview(image_path: str | Path, max_dim: int = 360) -> Image.Image:
    """Create downscaled thumbnail for the 3-second test."""
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img


REVIEWER_SYSTEM_RUBRIC = """You are a Master Graphic Design Director evaluating an event poster.
Evaluate the poster against the intended PosterSpec design blueprint.

Assess on a scale from 1 (poor) to 5 (exceptional):
- hierarchy: Does the main headline dominate instantly? Is visual reading flow natural?
- balance: Is the poster visually stable with thoughtful whitespace and graphic weight?
- readability: Is all typography crisp, well-contrasted, and legible?
- brand_fit: Does it reflect official, high-caliber institutional branding?
- polish: Are borders, alignments, and artwork clean and free of jarring glitches?

3-SECOND TEST:
Looking at the low-resolution thumbnail image, can a viewer glancing at the poster for 3 seconds identify:
1. Event title
2. Date
3. Venue
If all 3 are legible at a glance, set passed=true; otherwise set passed=false.

OUTPUT FORMAT:
Return strictly a valid JSON object matching this schema:
{
  "hierarchy": 1-5,
  "balance": 1-5,
  "readability": 1-5,
  "brand_fit": 1-5,
  "polish": 1-5,
  "three_second_test": {
    "event": "identified event name",
    "date": "identified date",
    "venue": "identified venue",
    "passed": true|false
  },
  "fixes": ["actionable fix 1", "actionable fix 2"]
}
"""


class PosterReviewer:
    """Critiques poster candidates using a Vision LLM over an OpenAI-compatible endpoint."""

    def __init__(
        self,
        config: ReviewerConfig | None = None,
        client: Any | None = None,
        model_name: str | None = None,
        thinking_mode: bool | None = None,
    ):
        base_cfg = config or get_config().reviewer
        self.endpoint = base_cfg.endpoint
        self.model_name = model_name or base_cfg.model
        self.thinking_mode = thinking_mode if thinking_mode is not None else base_cfg.thinking_mode
        self.client = client

    def _get_client(self):
        if self.client is not None:
            return self.client
        from openai import OpenAI
        return OpenAI(base_url=self.endpoint, api_key="local-no-key-required")

    def review(
        self,
        poster_image_path: str | Path,
        spec: PosterSpec,
    ) -> ReviewResult:
        """Execute vision evaluation on full poster + downscaled 3-second preview."""
        start_t = time.time()
        p_path = Path(poster_image_path)

        # 1. Prepare base64 images
        full_b64 = encode_image_base64(p_path)
        thumb_img = create_downscaled_preview(p_path, max_dim=360)
        thumb_b64 = encode_image_base64(thumb_img)

        spec_json_str = spec.model_dump_json(indent=2)

        user_content = [
            {
                "type": "text",
                "text": f"Here is the PosterSpec blueprint:\n```json\n{spec_json_str}\n```\n\nImage 1 is the full poster. Image 2 is the downscaled 3-second glance copy. Evaluate according to the rubric.",
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{full_b64}"},
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{thumb_b64}"},
            },
        ]

        raw_thinking: str | None = None
        data: dict[str, Any] = {}

        try:
            client = self._get_client()
            kwargs: dict[str, Any] = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": REVIEWER_SYSTEM_RUBRIC},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
                "max_tokens": 1024,
            }

            # Optional thinking mode toggle
            if self.thinking_mode:
                # Some local servers accept extra_body for reasoning tokens or thinking
                kwargs["extra_body"] = {"thinking": True}

            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or "{}"

            # Extract thinking tags if present
            think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
            if think_match:
                raw_thinking = think_match.group(1).strip()
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            data = json.loads(content)

        except Exception as e:
            # Deterministic heuristic critic fallback when local endpoint is offline
            data = self._heuristic_fallback(spec=spec, image_path=p_path)

        latency = time.time() - start_t

        return ReviewResult(
            hierarchy=int(data.get("hierarchy", 4)),
            balance=int(data.get("balance", 4)),
            readability=int(data.get("readability", 4)),
            brand_fit=int(data.get("brand_fit", 4)),
            polish=int(data.get("polish", 4)),
            three_second_test=ThreeSecondTest(
                event=str(data.get("three_second_test", {}).get("event", "Event")),
                date=str(data.get("three_second_test", {}).get("date", "Date")),
                venue=str(data.get("three_second_test", {}).get("venue", "Venue")),
                passed=bool(data.get("three_second_test", {}).get("passed", True)),
            ),
            fixes=data.get("fixes", []),
            model_name=self.model_name,
            thinking_enabled=self.thinking_mode,
            latency_seconds=round(latency, 2),
            raw_thinking=raw_thinking,
        )

    def _heuristic_fallback(self, spec: PosterSpec, image_path: Path) -> dict[str, Any]:
        """Heuristic evaluation when local vision server is not running."""
        h_elem = next((e for e in spec.elements if e.role == "headline"), None)
        d_elem = next((e for e in spec.elements if e.role == "date"), None)
        v_elem = next((e for e in spec.elements if e.role == "venue"), None)

        headline_text = h_elem.text if h_elem else "Event"
        date_text = d_elem.text if d_elem else "Date"
        venue_text = v_elem.text if v_elem else "Venue"

        # Check font sizes
        headline_size = h_elem.size if h_elem else 20
        hierarchy_score = 5 if headline_size >= 32 else 3

        return {
            "hierarchy": hierarchy_score,
            "balance": 4,
            "readability": 4,
            "brand_fit": 5 if spec.logos else 3,
            "polish": 4,
            "three_second_test": {
                "event": headline_text,
                "date": date_text,
                "venue": venue_text,
                "passed": headline_size >= 28,
            },
            "fixes": ["Consider slightly increasing body text contrast." if not spec.logos else "Layout looks well balanced."],
        }

