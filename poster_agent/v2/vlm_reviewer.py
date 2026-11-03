"""VLM reviewer adapter for v2 specs.

Reuses the proven OpenAI-compatible vision endpoint and image encoding from
``poster_agent.reviewer.reviewer``, but speaks the v2 contract. The reviewer
scores craft and routes actionable fixes back to a stage. It never overrides a
deterministic gate failure.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from poster_agent.config.settings import ReviewerConfig, get_config
from poster_agent.reviewer.reviewer import REVIEWER_SYSTEM_RUBRIC, create_downscaled_preview, encode_image_base64

from .contracts import BrandContract, PosterSpec, ReviewIssue, ReviewResult


def _stage_for_fix(fix: str) -> str:
    text = fix.lower()
    if any(word in text for word in ("logo", "brand mark", "seal", "hero")):
        return "assets"
    if any(
        word in text
        for word in (
            "headline",
            "text",
            "type",
            "contrast",
            "layout",
            "hierarchy",
            "spacing",
            "margin",
            "crowd",
            "negative space",
        )
    ):
        return "plan"
    if any(word in text for word in ("artwork", "background", "illustration", "image")):
        return "assets"
    if any(word in text for word in ("render", "raster", "export", "artifact", "glitch", "blur")):
        return "compose"
    return "plan"


class PosterReviewerV2:
    """Vision critic for the v2 pipeline."""

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
        try:
            from openai import OpenAI

            return OpenAI(base_url=self.endpoint, api_key="local-no-key-required")
        except ImportError:
            return None

    def _call_http(self, payload: dict[str, Any]) -> str:
        import urllib.request

        url = self.endpoint.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
            return body.get("choices", [{}])[0].get("message", {}).get("content", "{}")

    def review(self, image_path: str, spec: PosterSpec, brand: BrandContract) -> ReviewResult:
        prompt = self._review_prompt(spec, brand)
        try:
            full_b64 = encode_image_base64(create_downscaled_preview(image_path, max_dim=768))
            thumb_b64 = encode_image_base64(create_downscaled_preview(image_path, max_dim=360))
            user_content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{full_b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{thumb_b64}"}},
            ]
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
            if self.thinking_mode:
                kwargs["extra_body"] = {"thinking": True}
            client = self._get_client()
            content = (
                client.chat.completions.create(**kwargs).choices[0].message.content
                if client is not None
                else self._call_http(kwargs)
            )
            data = self._parse_json(content or "{}")
        except Exception as exc:
            return ReviewResult(
                score=brand.review_threshold,
                summary=f"VLM review unavailable: {exc}",
                issues=[
                    ReviewIssue(
                        code="review_unavailable",
                        stage="review",
                        severity="warning",
                        message=f"VLM review endpoint unavailable: {exc}",
                        fix_hint="Start the local vision endpoint to enable review routing.",
                    )
                ],
                raw={"engine": "vlm", "error": str(exc)},
            )

        return self._to_result(data, brand)

    # ------------------------------------------------------------------
    def _review_prompt(self, spec: PosterSpec, brand: BrandContract) -> str:
        text = {
            "school": brand.name,
            "candidate": spec.candidate_id,
            "format": f"{spec.format.width}x{spec.format.height}",
            "palette": spec.palette,
            "logo_rules": brand.logo.model_dump(),
            "background_rules": brand.background_rules,
            "text": [
                {"role": block.role, "text": block.text, "size": round(block.size, 1)}
                for block in spec.text_blocks
            ],
            "required_elements": spec.required_elements,
        }
        return (
            "Here is the v2 poster contract and plan:\n"
            f"```json\n{json.dumps(text, indent=2)}\n```\n\n"
            "Image 1 is the full poster. Image 2 is the 3-second glance copy. "
            "Judge hierarchy, balance, readability, brand fit and polish strictly. "
            "Set three_second_test.passed to false if the event, date or venue is not "
            "instantly legible. Return the rubric JSON exactly."
        )

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        if "</think>" in content:
            content = content.split("</think>", 1)[1]
        match = re.search(r"(\{.*\})", content, re.DOTALL)
        if match:
            content = match.group(1)
        try:
            return json.loads(content)
        except Exception:
            data: dict[str, Any] = {}
            for key in ("hierarchy", "balance", "readability", "brand_fit", "polish"):
                found = re.search(rf'"{key}":\s*(\d+)', content)
                if found:
                    data[key] = int(found.group(1))
            passed = re.search(r'"passed":\s*(true|false)', content, re.IGNORECASE)
            if passed:
                data["three_second_test"] = {"passed": passed.group(1).lower() == "true"}
            fixes = re.findall(r'"fixes":\s*\[(.*?)\]', content, re.DOTALL)
            if fixes:
                data["fixes"] = [part.strip().strip('"') for part in fixes[0].split(",") if part.strip()]
            return data

    @staticmethod
    def _to_result(data: dict[str, Any], brand: BrandContract) -> ReviewResult:
        scores = [
            int(data.get(key, 3))
            for key in ("hierarchy", "balance", "readability", "brand_fit", "polish")
        ]
        average = sum(scores) / len(scores)
        score = round(max(0.0, min(10.0, average * 2.0)), 2)
        issues: list[ReviewIssue] = []

        three_second = data.get("three_second_test") or {}
        if three_second.get("passed") is False:
            issues.append(
                ReviewIssue(
                    code="three_second_test",
                    stage="plan",
                    severity="blocking",
                    message="The event, date or venue is not legible within a three-second glance.",
                    fix_hint="Increase hierarchy and contrast for the event, date and venue.",
                )
            )

        for fix in data.get("fixes", [])[:6]:
            if not isinstance(fix, str) or not fix.strip():
                continue
            issues.append(
                ReviewIssue(
                    code="vlm_fix",
                    stage=_stage_for_fix(fix),  # type: ignore[arg-type]
                    severity="warning",
                    message=fix.strip(),
                    fix_hint=fix.strip(),
                )
            )

        return ReviewResult(
            score=score,
            issues=issues,
            summary=f"VLM craft score {score:.1f}/10 across hierarchy, balance, readability, brand fit and polish.",
            raw=data,
        )
