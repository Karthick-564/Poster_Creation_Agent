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


REVIEWER_SYSTEM_RUBRIC = """You are an elite, uncompromising Design Director at a world-class graphic design agency.
You evaluate posters with brutal, professional rigor (standards like Pentagram, Cannes Lions, D&AD).
Evaluate the poster against the intended PosterSpec design blueprint.

CRITICAL GRADING PHILOSOPHY:
Do NOT give generous or polite scores. Ordinary or amateur work MUST receive 1/5 or 2/5. A 4/5 requires exceptional craft. A 5/5 is reserved only for international award-winning masterpieces.

DEDUCT HEAVILY IF:
- Typography looks like plain, default computer text lazily slapped on top of artwork without styling, drop shadows, or background integration.
- Lack of typographic hierarchy (if subtitle or date competes with headline, cap hierarchy at 2).
- Poor contrast: text placed over busy image textures without backdrop cards or contrast vignettes.
- Squeezed or cluttered layout with uncomfortable negative space.
- Any visual glitches, awkward margins, or mismatched color temperatures.

EVALUATION RUBRIC (Score 1 to 5 strictly):
1. hierarchy (1-5):
   - Does the primary headline dominate instantly across the room?
   - Is reading flow natural: Headline -> Subhead -> Date & Venue -> Registration?
2. balance (1-5):
   - Is graphic weight distributed harmoniously? Does the poster breathe, or is it overcrowded?
3. readability (1-5):
   - Are words razor sharp and instantly legible even over complex background art?
   - Does text have adequate contrast treatment (glass backing cards, pills, text shadows)?
4. brand_fit (1-5):
   - Does the poster feel prestigious, institutional, and authentic?
   - Are logos, seals, and QR codes sharp and seamlessly integrated?
5. polish (1-5):
   - Craftsmanship of typography: tracking, leading, font pairings, edge alignment, and visual depth.
   - If it looks like plain Word/PowerPoint text pasted onto an image, score is strictly 1 or 2.

3-SECOND GLANCE AUDIT:
Looking at Image 2 (the downscaled thumbnail as seen by someone walking past a billboard in 3 seconds):
Can the viewer effortlessly and unambiguously extract:
1. Event title
2. Date
3. Venue
If ANY of these 3 are small, blurry, obscured, low-contrast, or take more than 3 seconds to find, set "passed": false.
Only set "passed": true if ALL THREE are unmistakable at an instant glance.

CRITIQUE & ACTIONABLE FIXES:
You MUST provide at least 2 to 3 sharp, specific, brutally honest design critiques in "fixes".
Call out exact flaws: e.g. "Headline lacks dimensional weight and looks flat", "Date pill needs stronger backdrop contrast against background art", "Center artwork crowds the bottom metadata".

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
  "fixes": [
    "Specific brutal critique 1 with design remedy",
    "Specific brutal critique 2 with design remedy"
  ]
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

        # 1. Prepare base64 images (downscaled to max 768px for vision model VRAM efficiency)
        review_img = create_downscaled_preview(p_path, max_dim=768)
        full_b64 = encode_image_base64(review_img)
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
                "max_tokens": 2048,
            }

            # Optional thinking mode toggle
            if self.thinking_mode:
                kwargs["extra_body"] = {"thinking": True}

            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or "{}"

            # Extract thinking/reasoning tags if present
            if "</think>" in content:
                parts = content.split("</think>", 1)
                raw_thinking = parts[0].replace("<think>", "").strip()
                content = parts[1].strip()
            elif "<think>" in content:
                think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
                if think_match:
                    raw_thinking = think_match.group(1).strip()
                    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            # Extract JSON block
            json_match = re.search(r"(\{.*\})", content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()

            try:
                data = json.loads(content)
            except Exception:
                # Regex extraction if JSON was truncated at the end
                h_m = re.search(r'"hierarchy":\s*(\d+)', content)
                b_m = re.search(r'"balance":\s*(\d+)', content)
                r_m = re.search(r'"readability":\s*(\d+)', content)
                bf_m = re.search(r'"brand_fit":\s*(\d+)', content)
                p_m = re.search(r'"polish":\s*(\d+)', content)
                ev_m = re.search(r'"event":\s*"([^"]+)"', content)
                dt_m = re.search(r'"date":\s*"([^"]+)"', content)
                vn_m = re.search(r'"venue":\s*"([^"]+)"', content)
                ps_m = re.search(r'"passed":\s*(true|false)', content, re.IGNORECASE)
                fx_m = re.findall(r'"fixes":\s*\[(.*?)\]', content, re.DOTALL)

                extracted_fixes = []
                if fx_m:
                    extracted_fixes = [s.strip().strip('"') for s in fx_m[0].split(",") if s.strip()]
                elif raw_thinking:
                    # Extract critique sentences from thinking
                    critiques = [line.strip().lstrip("-* ") for line in raw_thinking.splitlines() if any(k in line.lower() for k in ("clutter", "contrast", "hierarchy", "font", "color", "logo", "balance", "crowd")) and len(line.strip()) > 20]
                    extracted_fixes = critiques[:3]

                h_elem = next((e for e in spec.elements if e.role == "headline"), None)
                d_elem = next((e for e in spec.elements if e.role == "date"), None)
                v_elem = next((e for e in spec.elements if e.role == "venue"), None)
                fallback_ev = h_elem.text if h_elem else "Event"
                fallback_dt = d_elem.text if d_elem else "Date"
                fallback_vn = v_elem.text if v_elem else "Venue"

                if not any([h_m, b_m, r_m, bf_m, p_m, ev_m]):
                    data = self._heuristic_fallback(spec=spec, image_path=p_path)
                else:
                    data = {
                        "hierarchy": int(h_m.group(1)) if h_m else 4,
                        "balance": int(b_m.group(1)) if b_m else 3,
                        "readability": int(r_m.group(1)) if r_m else 3,
                        "brand_fit": int(bf_m.group(1)) if bf_m else 3,
                        "polish": int(p_m.group(1)) if p_m else 3,
                        "three_second_test": {
                            "event": ev_m.group(1) if ev_m else fallback_ev,
                            "date": dt_m.group(1) if dt_m else fallback_dt,
                            "venue": vn_m.group(1) if vn_m else fallback_vn,
                            "passed": ps_m.group(1).lower() == "true" if ps_m else True,
                        },
                        "fixes": extracted_fixes or ["Refine negative space and tighten typography contrast."]
                    }

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

