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
from poster_agent.checks.pixel_verifier import CheckIssue


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
    detected_issues: list[CheckIssue] = Field(default_factory=list)
    raw_inspector_responses: list[str] = Field(default_factory=list)
    latency_seconds: float = 0.0


def extract_vlm_text(content: str) -> str:
    """Extract clean critique text from raw VLM response or JSON wrapper."""
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            if "raw_critique" in data and data["raw_critique"]:
                return str(data["raw_critique"])
            if "fixes" in data and isinstance(data["fixes"], list) and data["fixes"]:
                return " ".join(str(f) for f in data["fixes"])
    except Exception:
        pass
    return content


class VisualInspector:
    """Inspector running checkable aesthetic and structural probes against local LFM3-VL-2B."""

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
                raw_content = data["choices"][0]["message"]["content"].strip()
                return extract_vlm_text(raw_content)
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
        """Run the comprehensive battery of checkable aesthetic & structural probes."""
        start_t = time.time()
        probes: list[ProbeVerdict] = []
        raw_responses: list[str] = []
        detected_issues: list[CheckIssue] = []

        # Downscale for 3-second glance test (360px thumbnail)
        thumb_img = create_downscaled_preview(full_png_path, max_dim=360)
        thumb_b64 = encode_image_base64(thumb_img)
        full_b64 = encode_image_base64(full_png_path)

        expected_title = brief.get_text("title", "").strip().upper()
        expected_date = brief.get_text("date", "").strip().upper()

        # Probe 1: 3-Second Glance Audit (OCR Checkable, No Model Opinion)
        q1 = "Look at this thumbnail as someone walking past in 3 seconds. State the exact Event Title and Date visible. Format strictly as 'Title: [title] | Date: [date]'."
        maj_1, votes_1, agr_1 = self.run_3_sample_probe(thumb_b64, q1)
        raw_responses.extend(votes_1)

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

        # Probe 2: Hero Dominance Probe
        q2 = "Look at the central cyber shield/hero element on this poster. Is the shield commanding and dominant (large, anchoring the poster), or is it relatively small and floating? Answer DOMINANT or TOO_SMALL followed by brief reason."
        maj_2, votes_2, agr_2 = self.run_3_sample_probe(full_b64, q2)
        raw_responses.extend(votes_2)

        p2_passed = "TOO_SMALL" not in maj_2.upper()
        probes.append(ProbeVerdict(
            probe_name="hero_dominance_probe",
            passed=p2_passed,
            majority_vote=maj_2,
            sample_votes=votes_2,
            agreement_ratio=agr_2,
            detail="Checked whether hero asset dominates the visual hierarchy vs floating clipart.",
            grounded_element_id="hero_art_1",
        ))

        # Probe 3: Spatial Center Void Probe
        q3 = "Look at the empty space in the middle between the shield and the bottom date/venue cards. Is there a large empty void / gap, or is the layout balanced? Answer BALANCED or EMPTY_VOID."
        maj_3, votes_3, agr_3 = self.run_3_sample_probe(full_b64, q3)
        raw_responses.extend(votes_3)

        p3_passed = "EMPTY_VOID" not in maj_3.upper()
        probes.append(ProbeVerdict(
            probe_name="center_void_probe",
            passed=p3_passed,
            majority_vote=maj_3,
            sample_votes=votes_3,
            agreement_ratio=agr_3,
            detail="Checked for dead empty space between central hero and metadata cards.",
            grounded_element_id="hero_art_1",
        ))

        # Probe 4: Color Harmony Probe
        q4 = "Are the colors across the date, prize box, and register button cohesive and unified, or do they clash? Answer COHESIVE or COLOR_CLASH."
        maj_4, votes_4, agr_4 = self.run_3_sample_probe(full_b64, q4)
        raw_responses.extend(votes_4)

        p4_passed = "COLOR_CLASH" not in maj_4.upper()
        probes.append(ProbeVerdict(
            probe_name="color_harmony_probe",
            passed=p4_passed,
            majority_vote=maj_4,
            sample_votes=votes_4,
            agreement_ratio=agr_4,
            detail="Checked color temperature harmony across metadata badges and interactive buttons.",
            grounded_element_id="card_date_venue",
        ))

        # Probe 5: Negative Control (Guards against authority/hallucination bias)
        q5 = "Is there a grand piano or violin visible on this poster? Answer strictly 'YES' or 'NO'."
        maj_5, votes_5, agr_5 = self.run_3_sample_probe(full_b64, q5)
        raw_responses.extend(votes_5)

        neg_passed = "NO" in maj_5.upper()
        probes.append(ProbeVerdict(
            probe_name="negative_control_fabrication_check",
            passed=neg_passed,
            majority_vote=maj_5,
            sample_votes=votes_5,
            agreement_ratio=agr_5,
            detail="Checked for phantom instrument. False alarm = failed authority bias test.",
            grounded_element_id=None,
        ))

        # Convert visual critique failures into CheckIssues for the typed patcher
        for p in probes:
            if not p.passed and p.probe_name != "negative_control_fabrication_check":
                if p.probe_name == "hero_dominance_probe":
                    detected_issues.append(CheckIssue(
                        check_name="vlm_hero_too_small",
                        severity="blocking",
                        element_id="hero_art_1",
                        detail=f"VLM Critic: {p.majority_vote}",
                        fix_hint="Enlarge hero art to command central composition",
                        recommended_op="resize_layer",
                    ))
                elif p.probe_name == "center_void_probe":
                    detected_issues.append(CheckIssue(
                        check_name="vlm_center_void",
                        severity="blocking",
                        element_id="hero_art_1",
                        detail=f"VLM Critic: {p.majority_vote}",
                        fix_hint="Shift hero art downward and expand light spill",
                        recommended_op="move",
                    ))
                elif p.probe_name == "color_harmony_probe":
                    detected_issues.append(CheckIssue(
                        check_name="vlm_color_clash",
                        severity="blocking",
                        element_id="card_date_venue",
                        detail=f"VLM Critic: {p.majority_vote}",
                        fix_hint="Harmonize color tokens to cohesive cyber emerald/cyan",
                        recommended_op="swap_token",
                    ))

        # Overall verdict
        all_passed = all(p.passed for p in probes)
        latency = time.time() - start_t

        return VisualAuditReport(
            overall_passed=all_passed,
            negative_control_passed=neg_passed,
            probes=probes,
            detected_issues=detected_issues,
            raw_inspector_responses=raw_responses,
            latency_seconds=round(latency, 2),
        )
