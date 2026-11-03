"""KCT-first candidate planner.

The planner is deliberately not a single rigid composer. It emits several
layout candidates, scores them with deterministic rules, and hands the winner
to the renderer. Generative models only supply art; geometry and copy are
contract-driven.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

from poster_agent.ingestion.extractor import ExtractedBrief

from .brand import BrandContract, FormatSpec
from .contracts import (
    Box,
    ImageSlot,
    LogoSlot,
    PosterSpec,
    QrSlot,
    TextBlock,
    TextRole,
)
from .typography import contrast_ratio, estimated_block


@dataclass(frozen=True)
class CandidateTemplate:
    id: str
    description: str
    # (role, x, y, w, h, size, weight, color_role, font_role, uppercase, align)
    slots: tuple[tuple, ...]
    logo_ratio: float = 3.0


def _block(
    block_id: str,
    role: TextRole,
    text: str,
    rect: tuple[float, float, float, float],
    size: float,
    color: str,
    font_role: str = "body",
    weight: int = 400,
    uppercase: bool = False,
    align: str = "left",
    tracking: float = 0.0,
    max_lines: int = 4,
    required: bool = True,
) -> TextBlock:
    x, y, w, h = rect
    return TextBlock(
        id=block_id,
        role=role,
        text=text.upper() if uppercase else text,
        box=Box(x=x, y=y, w=w, h=h),
        font_role=font_role,  # type: ignore[arg-type]
        size=size,
        weight=weight,
        color=color,
        align=align,  # type: ignore[arg-type]
        tracking=tracking,
        max_lines=max_lines,
        required=required,
    )


def _scale(fmt: FormatSpec, value: float) -> float:
    """Scale a 1080x1920 design value to the current canvas height."""
    return value * fmt.height / 1920.0


# Templates are authored on a 1080x1920 artboard.
_TEMPLATE_W = 1080.0
_TEMPLATE_H = 1920.0


def _norm_rect(rect: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x, y, w, h = rect
    return (
        x / _TEMPLATE_W * 1000.0,
        y / _TEMPLATE_H * 1000.0,
        w / _TEMPLATE_W * 1000.0,
        h / _TEMPLATE_H * 1000.0,
    )


def _logo_box(brand: BrandContract, fmt: FormatSpec, ratio: float) -> Box:
    clear = brand.clear_space_px(fmt)
    inset = max(clear, brand.safe_margin_px(fmt))
    width = min(fmt.width * brand.logo.max_width_pct / 100.0, fmt.width - 2 * inset)
    height = width / max(0.1, ratio)
    placement = brand.logo.placement
    x = inset if placement.endswith("left") else fmt.width - inset - width
    y = inset if placement.startswith("top") else fmt.height - inset - height
    return Box(
        x=x / fmt.width * 1000.0,
        y=y / fmt.height * 1000.0,
        w=width / fmt.width * 1000.0,
        h=height / fmt.height * 1000.0,
    )


def _expanded_px(box: Box, fmt: FormatSpec, pad: float) -> tuple[float, float, float, float]:
    x, y, w, h = box.to_px(fmt.width, fmt.height)
    return x - pad, y - pad, w + 2 * pad, h + 2 * pad


def _intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def _fit_text_rect(
    rect: tuple[float, float, float, float],
    fmt: FormatSpec,
    brand: BrandContract,
    logo_exclusion: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Keep a planned text box inside the safe area and out of the logo zone.

    Template coordinates are authored on a 1080x1920 artboard. On shorter
    formats the vertical compression can pull top copy into the logo
    exclusion or above the safe margin. Clamping here is contract work, not
    art direction: the renderer still has to prove the result with gates.
    """
    x, y, w, h = rect
    margin_x = brand.safe_margin_px(fmt) / fmt.width * 1000.0
    margin_y = brand.safe_margin_px(fmt) / fmt.height * 1000.0

    x = max(x, margin_x)
    y = max(y, margin_y)
    if x + w > 1000.0 - margin_x:
        w = max(1.0, 1000.0 - margin_x - x)
    if y + h > 1000.0 - margin_y:
        h = max(1.0, 1000.0 - margin_y - y)

    ex1, ey1, ex2, ey2 = logo_exclusion
    if _intersects((x, y, w, h), logo_exclusion):
        if x < ex1:
            # Left-aligned copy: shorten the measure rather than moving the
            # baseline, so the stack keeps its editorial rhythm.
            w = max(1.0, ex1 - x - 1.0)
        elif ey2 + h <= 1000.0 - margin_y:
            # Copy already sits under the mark: push it below the exclusion.
            y = ey2 + 1.0
        else:
            w = max(1.0, ex1 - x - 1.0)

    return x, y, w, h


TEMPLATES: tuple[CandidateTemplate, ...] = (
    CandidateTemplate(
        id="editorial-split",
        description="Left editorial stack with a right-side hero column and bottom logistics.",
        logo_ratio=3.0,
        slots=(
            ("eyebrow", "eyebrow", (48, 70, 550, 44), 22, 700, "secondary", "display", True, "left", 80, 1),
            ("headline", "headline", (48, 330, 700, 230), 100, 800, "surface", "display", True, "left", 0, 2),
            ("subheadline", "subheadline", (48, 570, 640, 85), 32, 400, "neutral", "body", False, "left", 0, 3),
            ("tagline", "tagline", (48, 660, 620, 64), 22, 600, "secondary", "body", True, "left", 40, 2),
            ("date", "date", (48, 1380, 620, 50), 30, 600, "surface", "body", False, "left", 0, 1),
            ("venue", "venue", (48, 1440, 620, 80), 32, 400, "surface", "body", False, "left", 0, 2),
            ("cta", "cta", (48, 1540, 560, 56), 30, 700, "secondary", "body", True, "left", 40, 1),
            ("closing", "closing", (48, 1620, 720, 50), 24, 500, "neutral", "body", False, "left", 0, 1),
            ("organizer", "organizer", (48, 1800, 900, 40), 22, 400, "neutral", "body", False, "left", 0, 1),
        ),
    ),
    CandidateTemplate(
        id="hero-band",
        description="Centered headline over a wide hero band, logistics anchored at the bottom.",
        logo_ratio=3.0,
        slots=(
            ("eyebrow", "eyebrow", (48, 70, 550, 44), 22, 700, "secondary", "display", True, "left", 80, 1),
            ("headline", "headline", (48, 330, 720, 250), 100, 800, "surface", "display", True, "left", 0, 2),
            ("subheadline", "subheadline", (48, 590, 720, 70), 30, 400, "neutral", "body", False, "left", 0, 2),
            ("tagline", "tagline", (48, 665, 720, 34), 18, 600, "secondary", "body", True, "left", 40, 1),
            ("date", "date", (48, 1300, 620, 50), 30, 600, "surface", "body", False, "left", 0, 1),
            ("venue", "venue", (48, 1360, 620, 80), 32, 400, "surface", "body", False, "left", 0, 2),
            ("cta", "cta", (48, 1460, 560, 56), 30, 700, "secondary", "body", True, "left", 40, 1),
            ("closing", "closing", (48, 1540, 720, 50), 24, 500, "neutral", "body", False, "left", 0, 1),
            ("organizer", "organizer", (48, 1800, 900, 40), 22, 400, "neutral", "body", False, "left", 0, 1),
        ),
    ),
    CandidateTemplate(
        id="hero-dominant",
        description="Large central hero with a compact editorial header and bottom logistics.",
        logo_ratio=3.0,
        slots=(
            ("eyebrow", "eyebrow", (48, 70, 550, 44), 22, 700, "secondary", "display", True, "left", 80, 1),
            ("headline", "headline", (48, 330, 720, 240), 100, 800, "surface", "display", True, "left", 0, 2),
            ("subheadline", "subheadline", (48, 1255, 720, 60), 26, 400, "neutral", "body", False, "left", 0, 2),
            ("tagline", "tagline", (48, 1320, 720, 34), 18, 600, "secondary", "body", True, "left", 40, 1),
            ("date", "date", (48, 1370, 620, 50), 30, 600, "surface", "body", False, "left", 0, 1),
            ("venue", "venue", (48, 1430, 620, 80), 32, 400, "surface", "body", False, "left", 0, 2),
            ("cta", "cta", (48, 1530, 560, 56), 30, 700, "secondary", "body", True, "left", 40, 1),
            ("closing", "closing", (48, 1610, 720, 50), 24, 500, "neutral", "body", False, "left", 0, 1),
            ("organizer", "organizer", (48, 1800, 900, 40), 22, 400, "neutral", "body", False, "left", 0, 1),
        ),
    ),
)


class KCTPlanner:
    """Deterministic candidate generator for the KCT vertical slice."""

    def __init__(self, templates: tuple[CandidateTemplate, ...] = TEMPLATES):
        self.templates = templates

    def plan_candidates(
        self,
        brief: ExtractedBrief,
        brand: BrandContract,
        fmt: FormatSpec,
        seed: int | None = None,
    ) -> list[PosterSpec]:
        seed_value = seed if seed is not None else self._seed(brief)
        candidates = [
            self._build(template, brief, brand, fmt, seed_value)
            for template in self.templates
        ]
        scored = [(self.score(candidate, brand, brief), candidate) for candidate in candidates]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [candidate for _, candidate in scored]

    def plan(
        self,
        brief: ExtractedBrief,
        brand: BrandContract,
        fmt: FormatSpec,
        seed: int | None = None,
    ) -> PosterSpec:
        candidates = self.plan_candidates(brief, brand, fmt, seed=seed)
        best = candidates[0]
        return best.model_copy(
            update={
                "design_notes": best.design_notes
                + [f"selected from {len(candidates)} candidates by deterministic fit score"]
            }
        )

    # ------------------------------------------------------------------
    # Candidate construction
    # ------------------------------------------------------------------
    def _build(
        self,
        template: CandidateTemplate,
        brief: ExtractedBrief,
        brand: BrandContract,
        fmt: FormatSpec,
        seed: int,
    ) -> PosterSpec:
        scale = _scale(fmt, 1.0)
        background = brand.color("primary")
        surface = brand.color("surface")
        neutral = ensure_readable(background, brand.color("neutral"), brand.min_text_contrast)
        secondary = ensure_readable(background, brand.color("secondary"), 3.0)

        def color_for(role: str) -> str:
            if role == "surface":
                return ensure_readable(background, surface, brand.min_text_contrast)
            if role == "neutral":
                return neutral
            if role == "secondary":
                return secondary
            return brand.color(role, surface)

        blocks: list[TextBlock] = []
        logo = brand.logo
        logo_box = _logo_box(brand, fmt, template.logo_ratio)
        logo_x, logo_y, logo_w, logo_h = logo_box.to_px(fmt.width, fmt.height)
        clear = brand.clear_space_px(fmt)
        logo_exclusion = (
            (logo_x - clear) / fmt.width * 1000.0,
            (logo_y - clear) / fmt.height * 1000.0,
            (logo_x + logo_w + clear) / fmt.width * 1000.0,
            (logo_y + logo_h + clear) / fmt.height * 1000.0,
        )
        for (
            block_id,
            role,
            rect,
            size,
            weight,
            color_role,
            font_role,
            uppercase,
            align,
            tracking,
            max_lines,
        ) in template.slots:
            text = self._text_for(role, brief)
            if not text:
                continue
            x, y, w, h = rect
            scaled_rect = _fit_text_rect(
                _norm_rect((x, y, w, h)),
                fmt,
                brand,
                logo_exclusion,
            )
            blocks.append(
                _block(
                    block_id=block_id,
                    role=role,
                    text=text,
                    rect=scaled_rect,
                    size=max(12.0, size * scale),
                    color=color_for(color_role),
                    font_role=font_role,
                    weight=weight,
                    uppercase=uppercase,
                    align=align,
                    tracking=tracking,
                    max_lines=max_lines,
                )
            )

        logo_slot = LogoSlot(
            asset=logo.asset,
            box=logo_box,
            placement=logo.placement,
            clear_space_mm=logo.clear_space_mm,
            solid_field=logo.field_color,
            preserve_aspect=logo.preserve_aspect,
        )

        hero_rect = {
            "editorial-split": (460, 760, 500, 600),
            "hero-band": (48, 710, 912, 550),
            "hero-dominant": (48, 590, 912, 650),
        }[template.id]
        hx, hy, hw, hh = hero_rect
        hero_box = _norm_rect(hero_rect)
        hero = ImageSlot(
            id="hero",
            role="hero",
            source="qwen",
            prompt=self._hero_prompt(brief, brand),
            box=Box(x=hero_box[0], y=hero_box[1], w=hero_box[2], h=hero_box[3]),
            transparent=True,
            blend="normal",
            required=True,
        )
        background_slot = ImageSlot(
            id="background",
            role="background",
            source="ideogram",
            prompt=self._background_prompt(brief, brand),
            box=Box(x=0, y=0, w=1000, h=1000),
            transparent=False,
            required=True,
        )

        qr_payload = (
            brief.get_asset_ref("qr_link")
            or brief.get_asset_ref("qr_url")
            or brief.get_text("qr_link")
            or brief.get_text("qr_url")
        )
        qr = None
        if qr_payload:
            qx, qy, qw, qh = {
                "editorial-split": (740, 1450, 220, 220),
                "hero-band": (740, 1380, 220, 220),
                "hero-dominant": (740, 1450, 220, 220),
            }[template.id]
            qbox = _norm_rect((qx, qy, qw, qh))
            qr_label = brand.qr.label
            cta_text = brief.get_text("cta").strip()
            if cta_text and cta_text.lower() == qr_label.strip().lower():
                qr_label = "SCAN QR CODE"
            qr = QrSlot(
                payload=qr_payload,
                box=Box(x=qbox[0], y=qbox[1], w=qbox[2], h=qbox[3]),
                label=qr_label,
                min_size_px=brand.qr.min_size_px,
            )

        return PosterSpec(
            school_id=brand.school_id,
            candidate_id=template.id,
            format=fmt,
            palette=brand.palette_list(),
            background_color=background,
            text_blocks=blocks,
            image_slots=[background_slot, hero],
            logo_slots=[logo_slot],
            qr=qr,
            required_elements=list(brand.mandatory_elements),
            design_notes=[template.description],
            seed=seed,
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def score(self, spec: PosterSpec, brand: BrandContract, brief: ExtractedBrief) -> float:
        fmt = spec.format
        width, height = fmt.width, fmt.height
        margin = brand.safe_margin_px(fmt)
        score = 100.0

        block_rects: list[tuple[str, tuple[float, float, float, float]]] = []
        for block in spec.text_blocks:
            x, y, w, h = block.box.to_px(width, height)
            block_rects.append((block.id, (x, y, w, h)))
            if x < margin - 0.5 or y < margin - 0.5 or x + w > width - margin + 0.5 or y + h > height - margin + 0.5:
                score -= 12.0
            if contrast_ratio(spec.background_color, block.color) < brand.min_text_contrast:
                score -= 15.0
            fit = estimated_block(
                text=block.text,
                target_size=block.size,
                min_size=max(12.0, block.size * 0.62),
                box_width=w,
                box_height=h,
                max_lines=block.max_lines,
                uppercase=block.text.isupper(),
                tracking=block.tracking,
                line_height=block.line_height,
            )
            if not fit["fits"]:
                score -= 25.0
            elif fit["shrunk"]:
                score -= 3.0

        # Logo clear space may not contain type or a hero.
        for logo in spec.logo_slots:
            exclusion = _expanded_px(logo.box, fmt, brand.clear_space_px(fmt))
            for block_id, rect in block_rects:
                if _intersects(exclusion, rect):
                    score -= 40.0
            for image in spec.image_slots:
                if image.role == "hero" and _intersects(exclusion, image.box.to_px(width, height)):
                    score -= 40.0

        # Type may not collide with type or the hero cutout.
        for i, (id_a, rect_a) in enumerate(block_rects):
            for id_b, rect_b in block_rects[i + 1 :]:
                if _intersects(rect_a, rect_b):
                    score -= 30.0
        for image in spec.image_slots:
            if image.role != "hero":
                continue
            hero_rect = image.box.to_px(width, height)
            for _, rect in block_rects:
                if _intersects(hero_rect, rect):
                    score -= 35.0

        # Reward a hero that occupies a meaningful share of the canvas.
        for image in spec.image_slots:
            if image.role == "hero":
                _, _, w, h = image.box.to_px(width, height)
                share = (w * h) / (width * height)
                score += min(8.0, share * 20.0)

        # Vertical rhythm: reward candidates that put content in all five bands.
        bands = set()
        for _, (x, y, w, h) in block_rects:
            top, bottom = y / height, (y + h) / height
            for idx, (start, end) in enumerate(
                ((0.0, 0.15), (0.15, 0.35), (0.35, 0.55), (0.55, 0.80), (0.80, 1.0))
            ):
                if not (bottom < start or top > end):
                    bands.add(idx)
        score += len(bands) * 1.5

        # Required copy present.
        roles = {block.role for block in spec.text_blocks}
        required_aliases = {"title": "headline", "logo": None}
        for element in brand.mandatory_elements:
            if element == "logo":
                if not spec.logo_slots:
                    score -= 20.0
                continue
            role = required_aliases.get(element, element)
            if role and role not in roles:
                score -= 18.0

        # Do not silently drop optional-but-supplied copy. A candidate that
        # loses the tagline or closing line is worse than one with a smaller hero.
        for field, role in (
            ("tagline", "tagline"),
            ("subtitle", "subheadline"),
            ("closing", "closing"),
            ("cta", "cta"),
            ("venue", "venue"),
        ):
            if self._text_for(field, brief) and role not in roles:
                score -= 8.0
        if (brief.get_asset_ref("qr_link") or brief.get_asset_ref("qr_url")) and not spec.qr:
            score -= 12.0
        return round(score, 3)

    # ------------------------------------------------------------------
    # Copy and prompts
    # ------------------------------------------------------------------
    def _text_for(self, role: str, brief: ExtractedBrief) -> str:
        if role == "eyebrow":
            return brief.get_text("eyebrow") or brief.get_text("organizer")
        if role == "headline":
            return brief.get_text("title")
        if role == "subheadline":
            return brief.get_text("subtitle") or brief.get_text("blurb")
        if role == "tagline":
            return brief.get_text("tagline")
        if role == "date":
            date = brief.get_text("date")
            time = brief.get_text("time")
            if date and time:
                return f"{date} | {time}"
            return date or time
        if role == "venue":
            return brief.get_text("venue")
        if role == "cta":
            return brief.get_text("cta")
        if role == "closing":
            return brief.get_text("closing")
        if role == "organizer":
            return brief.get_text("organizer") or brief.get_text("partner")
        if role == "body":
            return brief.get_text("blurb")
        return brief.get_text(role)

    def _background_prompt(self, brief: ExtractedBrief, brand: BrandContract) -> str:
        mood = brief.get_text("mood") or "editorial, confident, institutional"
        art = brief.get_text("art")
        return (
            "Full-bleed poster background, no text, no letters, no logos, no people. "
            f"Event: {brief.get_text('title')}. Mood: {mood}. "
            f"Palette: {', '.join(brand.palette_list())}. "
            f"Brand rules: {' '.join(brand.background_rules)} "
            "Leave a calm, low-contrast area in the lower-left for typography and a clean "
            "solid field in the top-right for the institutional logo. "
            + (f"Art direction: {art}. " if art else "")
            + "Premium editorial composition, generous negative space, print-ready."
        )

    def _hero_prompt(self, brief: ExtractedBrief, brand: BrandContract) -> str:
        art = brief.get_text("art") or (
            f"a single sculptural hero object representing {brief.get_text('title')}"
        )
        return (
            f"{art}. One isolated subject, centered, no text, no logos, no frame, no stand, "
            f"no background, transparent alpha, crisp cutout edges. Brand accents: "
            f"{brand.color('secondary')} and {brand.color('neutral')}. "
            "Soft studio rim light, high detail, editorial 3D render."
        )

    @staticmethod
    def _seed(brief: ExtractedBrief) -> int:
        payload = "|".join(
            f"{key}={field.text}" for key, field in sorted(brief.fields.items())
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)


def ensure_readable(background: str, preferred: str, minimum: float) -> str:
    if contrast_ratio(background, preferred) >= minimum:
        return preferred
    return "#FFFFFF" if contrast_ratio(background, "#FFFFFF") >= contrast_ratio(background, "#000000") else "#000000"


def rescale_logo_to_asset(
    spec: PosterSpec,
    brand: BrandContract,
    asset_width: int,
    asset_height: int,
) -> PosterSpec:
    """Preserve the logo's intrinsic aspect ratio using its top/right anchors."""
    if not spec.logo_slots or asset_height <= 0:
        return spec
    fmt = spec.format
    clear = brand.clear_space_px(fmt)
    inset = max(clear, brand.safe_margin_px(fmt))
    ratio = asset_width / asset_height
    logo = spec.logo_slots[0]
    x, y, w, h = logo.box.to_px(fmt.width, fmt.height)
    new_height = w / ratio
    placement = logo.placement
    if placement.startswith("top"):
        new_y = inset
    else:
        new_y = fmt.height - inset - new_height
    if placement.endswith("left"):
        new_x = inset
    else:
        new_x = fmt.width - inset - w
    new_box = Box(
        x=new_x / fmt.width * 1000.0,
        y=new_y / fmt.height * 1000.0,
        w=w / fmt.width * 1000.0,
        h=new_height / fmt.height * 1000.0,
    )
    updated_logo = logo.model_copy(update={"box": new_box})
    return spec.model_copy(update={"logo_slots": [updated_logo]})
