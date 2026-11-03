"""Optional VLM/human review adapter.

The reviewer never overrides deterministic gates. It can only add a second
opinion and route a passing poster back for a better composition.
"""
from __future__ import annotations

from typing import Callable, Protocol

from .contracts import BrandContract, PosterSpec, ReviewResult


class Reviewer(Protocol):
    def review(self, image_path: str, spec: PosterSpec, brand: BrandContract) -> ReviewResult:
        ...


class CallableReviewer:
    """Wrap a plain callable so the pipeline stays dependency-free."""

    def __init__(self, fn: Callable[[str, PosterSpec, BrandContract], ReviewResult]):
        self._fn = fn

    def review(self, image_path: str, spec: PosterSpec, brand: BrandContract) -> ReviewResult:
        return self._fn(image_path, spec, brand)


class StaticReviewer:
    """Deterministic reviewer for tests and offline demos."""

    def __init__(self, score: float = 8.0, summary: str = "Static review: composition is legible and on-brand."):
        self.score = score
        self.summary = summary

    def review(self, image_path: str, spec: PosterSpec, brand: BrandContract) -> ReviewResult:
        return ReviewResult(score=self.score, summary=self.summary, raw={"engine": "static"})
