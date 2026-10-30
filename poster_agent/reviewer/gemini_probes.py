"""Stage 6: Gemini-powered Multimodal Grounded Visual Inspector."""
import time
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.gemini_client import GeminiClient
from poster_agent.ingestion.extractor import ExtractedBrief
from poster_agent.checks.pixel_verifier import CheckIssue
from poster_agent.reviewer.probes import ProbeVerdict, VisualAuditReport


class GeminiVisualInspector:
    """Inspector running grounded aesthetic & structural critiques using Gemini Multimodal Vision."""

    def __init__(self, client: GeminiClient | None = None):
        self.client = client or GeminiClient()

    def audit_poster(self, full_png_path: str | Path, brief: ExtractedBrief) -> VisualAuditReport:
        """Inspect the rendered poster across all design and readability dimensions."""
        start_t = time.time()
        probes: list[ProbeVerdict] = []
        detected_issues: list[CheckIssue] = []

        expected_title = brief.get_text("title", "").strip()
        expected_date = brief.get_text("date", "").strip()

        vision_prompt = f"""You are a master poster critic and art director inspecting a high-resolution tournament poster render.
Brief Expected Values:
- Expected Title: "{expected_title}"
- Expected Date: "{expected_date}"

Inspect the provided poster image rigorously across 5 dimensions:
1. 3-Second Glance Test: Look at the poster as someone walking past in 3 seconds. State the exact Event Title and Date visible. Do they match the expected brief values?
2. Hero Dominance: Inspect the central cyber shield/hero element. Is it commanding, prominent and large (anchoring the composition), or is it small, floating, or undersized like clipart?
3. Spatial Void: Inspect the vertical balance between the central hero shield, category belt, and bottom metadata cards. Is there a large empty dark chasm / dead void, or is the layout balanced and well-filled?
4. Color Harmony: Examine the colors across the date, prize badge, category badges, and registration button. Are the colors cohesive and unified in a high-voltage cyber palette (electric emerald + cyan), or do they clash with jarring discordant colors?
5. Negative Control: Is there a grand piano or violin visible on this poster? (YES or NO)

Return strictly valid JSON with this schema:
{{
  "glance_test": {{
    "passed": true,
    "read_title": "string",
    "read_date": "string",
    "detail": "string"
  }},
  "hero_dominance": {{
    "verdict": "DOMINANT or TOO_SMALL",
    "detail": "string"
  }},
  "spatial_void": {{
    "verdict": "BALANCED or EMPTY_VOID",
    "detail": "string"
  }},
  "color_harmony": {{
    "verdict": "COHESIVE or COLOR_CLASH",
    "detail": "string"
  }},
  "negative_control": {{
    "phantom_instrument_present": false,
    "detail": "string"
  }},
  "overall_critique_summary": "string"
}}
"""

        critique = self.client.critique_image(
            image_input=full_png_path,
            prompt=vision_prompt,
            temperature=0.1,
        )

        # 1. Glance Test
        g_data = critique.get("glance_test", {})
        g_passed = bool(g_data.get("passed", False))
        # Automatic title match check
        read_t = g_data.get("read_title", "").upper()
        if expected_title.upper() in read_t or all(w in read_t for w in expected_title.upper().split() if len(w) > 2):
            g_passed = True

        probes.append(ProbeVerdict(
            probe_name="three_second_glance_test",
            passed=g_passed,
            majority_vote=f"Title: {g_data.get('read_title')} | Date: {g_data.get('read_date')}",
            sample_votes=[str(g_data)],
            agreement_ratio=1.0,
            detail=g_data.get("detail", f"Title legibility audit against '{expected_title}'."),
            grounded_element_id="headline_1",
        ))

        # 2. Hero Dominance
        hd_data = critique.get("hero_dominance", {})
        hd_verdict = hd_data.get("verdict", "DOMINANT").upper()
        hd_passed = "TOO_SMALL" not in hd_verdict

        probes.append(ProbeVerdict(
            probe_name="hero_dominance_probe",
            passed=hd_passed,
            majority_vote=hd_verdict,
            sample_votes=[hd_verdict],
            agreement_ratio=1.0,
            detail=hd_data.get("detail", "Checked hero asset dominance in hierarchy."),
            grounded_element_id="hero_art_1",
        ))

        # 3. Spatial Void
        sv_data = critique.get("spatial_void", {})
        sv_verdict = sv_data.get("verdict", "BALANCED").upper()
        sv_passed = "EMPTY_VOID" not in sv_verdict

        probes.append(ProbeVerdict(
            probe_name="center_void_probe",
            passed=sv_passed,
            majority_vote=sv_verdict,
            sample_votes=[sv_verdict],
            agreement_ratio=1.0,
            detail=sv_data.get("detail", "Checked vertical rhythm and empty chasm balance."),
            grounded_element_id="hero_art_1",
        ))

        # 4. Color Harmony
        ch_data = critique.get("color_harmony", {})
        ch_verdict = ch_data.get("verdict", "COHESIVE").upper()
        ch_passed = "COLOR_CLASH" not in ch_verdict

        probes.append(ProbeVerdict(
            probe_name="color_harmony_probe",
            passed=ch_passed,
            majority_vote=ch_verdict,
            sample_votes=[ch_verdict],
            agreement_ratio=1.0,
            detail=ch_data.get("detail", "Checked cyber color temperature cohesion."),
            grounded_element_id="card_date_venue",
        ))

        # 5. Negative Control
        nc_data = critique.get("negative_control", {})
        nc_present = bool(nc_data.get("phantom_instrument_present", False))
        nc_passed = not nc_present

        probes.append(ProbeVerdict(
            probe_name="negative_control_fabrication_check",
            passed=nc_passed,
            majority_vote="NO" if nc_passed else "YES",
            sample_votes=["NO" if nc_passed else "YES"],
            agreement_ratio=1.0,
            detail="Checked for phantom instrument. Guards against hallucination.",
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
                        detail=f"Gemini Critic: {p.majority_vote}",
                        fix_hint="Enlarge hero art to command central composition",
                        recommended_op="resize_layer",
                    ))
                elif p.probe_name == "center_void_probe":
                    detected_issues.append(CheckIssue(
                        check_name="vlm_center_void",
                        severity="blocking",
                        element_id="hero_art_1",
                        detail=f"Gemini Critic: {p.majority_vote}",
                        fix_hint="Shift hero art downward towards center",
                        recommended_op="move",
                    ))
                elif p.probe_name == "color_harmony_probe":
                    detected_issues.append(CheckIssue(
                        check_name="vlm_color_clash",
                        severity="blocking",
                        element_id="card_date_venue",
                        detail=f"Gemini Critic: {p.majority_vote}",
                        fix_hint="Harmonize color tokens to cohesive cyber emerald/cyan",
                        recommended_op="swap_token",
                    ))

        all_passed = all(p.passed for p in probes)
        latency = round(time.time() - start_t, 2)

        return VisualAuditReport(
            overall_passed=all_passed,
            negative_control_passed=nc_passed,
            probes=probes,
            detected_issues=detected_issues,
            raw_inspector_responses=[critique.get("overall_critique_summary", "")],
            latency_seconds=latency,
        )
