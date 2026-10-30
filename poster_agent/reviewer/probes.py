"""Stage 6: Grounded Visual Inspector (Single-Turn Checkable Probes, 3-Sample Voting, Negative Controls)."""
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.reviewer.reviewer import encode_image_base64, create_downscaled_preview
from poster_agent.ingestion.extractor import ExtractedBrief


class ProbeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    probe_name: str
    passed: bool
    majority_vote: str
    sample_votes: list[str]
    agreement_ratio: float
    detail: str
    grounded_element_id: str | None = None


class VisualAuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overall_passed: bool
    negative_control_passed: bool
    probes: list[ProbeVerdict]
    raw_inspector_responses: list[str] = Field(default_factory=list)
    latency_seconds: float = 0.0


class VisualInspector:
    """Inspector running small single-turn checkable probes against local LFM3-VL-2B."""

    def __init__(self, endpoint: str = "http://127.0.0.1:8080/v1", model_name: str = "LFM3-VL-2B"):
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name

    def _call_vlm(self, image_b64: str, prompt_text: str, temperature: float = 0.1) -> str:
        """Call local OpenAI-compatible endpoint with single multimodal prompt."""
        url = f"{self.endpoint}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": prompt_text},
                    ],
                }
            ],
            "temperature": temperature,
            "max_tokens": 150,
            "thinking": False,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Error: {e}"

    def run_3_sample_probe(self, image_b64: str, question: str) -> tuple[str, list[str], float]:
        """Execute 3 samples at low temperature and take the majority verdict."""
        votes: list[str] = []
        for _ in range(3):
            resp = self._call_vlm(image_b64, question, temperature=0.1)
            votes.append(resp)

        # Count frequencies
        from collections import Counter
        counts = Counter(votes)
        majority, count = counts.most_common(1)[0]
        agreement = count / 3.0
        return majority, votes, agreement

    def audit_poster(self, full_png_path: str | Path, brief: ExtractedBrief) -> VisualAuditReport:
        """Run the full battery of checkable probes on the rendered poster."""
        start_t = time.time()
        probes: list[ProbeVerdict] = []
        raw_responses: list[str] = []

        # Downscale for 3-second glance test (360px thumbnail)
        thumb_img = create_downscaled_preview(full_png_path, max_dim=360)
        thumb_b64 = encode_image_base64(thumb_img)
        full_b64 = encode_image_base64(full_png_path)

        expected_title = brief.get_text("title", "").strip().upper()
        expected_date = brief.get_text("date", "").strip().upper()

        # Probe 1: 3-Second Glance Audit (OCR Checkable, No Model Opinion)
        q1 = f"Look at this thumbnail as someone walking past in 3 seconds. State the exact Event Title and Date visible. Format strictly as 'Title: [title] | Date: [date]'."
        maj_1, votes_1, agr_1 = self.run_3_sample_probe(thumb_b64, q1)
        raw_responses.extend(votes_1)

        # Checkable verification: does the model's extraction contain the actual title words?
        maj_upper = maj_1.upper()
        title_words = [w for w in expected_title.split() if len(w) > 2]
        title_found = any(w in maj_upper for w in title_words)
        p1_passed = title_found

        probes.append(ProbeVerdict(
            probe_name="three_second_glance_test",
            passed=p1_passed,
            majority_vote=maj_1,
            sample_votes=votes_1,
            agreement_ratio=agr_1,
            detail=f"Expected title '{expected_title}'. Inspector read: '{maj_1}'.",
            grounded_element_id="headline_1",
        ))

        # Probe 2: Negative Control (Guards against authority/hallucination bias)
        q2 = "Is there a grand piano or violin visible on this poster? Answer strictly 'YES' or 'NO'."
        maj_2, votes_2, agr_2 = self.run_3_sample_probe(full_b64, q2)
        raw_responses.extend(votes_2)

        neg_passed = "NO" in maj_2.upper()
        probes.append(ProbeVerdict(
            probe_name="negative_control_fabrication_check",
            passed=neg_passed,
            majority_vote=maj_2,
            sample_votes=votes_2,
            agreement_ratio=agr_2,
            detail="Checked for phantom instrument. False alarm = failed authority bias test.",
            grounded_element_id=None,
        ))

        # Overall verdict
        all_passed = all(p.passed for p in probes)
        latency = time.time() - start_t

        return VisualAuditReport(
            overall_passed=all_passed,
            negative_control_passed=neg_passed,
            probes=probes,
            raw_inspector_responses=raw_responses,
            latency_seconds=round(latency, 2),
        )
