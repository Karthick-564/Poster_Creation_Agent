"""Automated Layout Patcher: converts Vision LLM critiques into CSS/DOM layout mutations."""
import re
from pathlib import Path
from typing import Any
from poster_agent.reviewer.reviewer import ReviewResult


class LayoutPatcher:
    """Parses ReviewResult fixes and applies parametric CSS/DOM mutations to the poster HTML."""

    def __init__(self):
        pass

    def patch_html(self, html_content: str, review: ReviewResult) -> tuple[str, list[str]]:
        """Analyze fixes from review and mutate the HTML/CSS accordingly."""
        patched_html = html_content
        applied_patches: list[str] = []

        all_critiques = " ".join(review.fixes).lower()
        if hasattr(review, "raw_critique") and review.raw_critique:
            all_critiques += " " + str(review.raw_critique).lower()

        # 1. Patch: Disconnected / off-center lanterns
        if any(w in all_critiques for w in ["lantern", "top right corner", "off-center", "distraction"]):
            # Either hide lanterns or blend them subtly into background
            # Check if lanterns element exists in HTML
            if ".layer-foreground-lanterns" in patched_html:
                # Subdue opacity and move to organic background layer
                patched_html = re.sub(
                    r"\.layer-foreground-lanterns\s*\{[^}]*\}",
                    """.layer-foreground-lanterns {
      position: absolute;
      top: 140px;
      right: 70px;
      width: 170px;
      height: 170px;
      object-fit: contain;
      z-index: 3;
      opacity: 0.45;
      mix-blend-mode: screen;
      filter: blur(1.5px) drop-shadow(0 0 25px rgba(255, 183, 3, 0.4));
      pointer-events: none;
    }""",
                    patched_html,
                )
                applied_patches.append("Subdued floating lanterns: reduced scale from 240px to 170px, set opacity to 45% with background blur, integrating them atmospherically.")

        # 2. Patch: Bottom-heavy layout disrupting vertical flow
        if any(w in all_critiques for w in ["heavy bottom", "bottom section", "disrupts the vertical flow", "cluttered", "vertical flow"]):
            # Rebalance vertical proportions:
            # - Lift hero orb slightly up from 385px to 350px
            # - Expand bottom padding and refine grid spacing
            if ".layer-hero-orb" in patched_html:
                patched_html = re.sub(
                    r"(\.layer-hero-orb\s*\{[^}]*?top:\s*)\d+px",
                    r"\g<1>350px",
                    patched_html,
                )
                patched_html = re.sub(
                    r"(\.hero-light-spill\s*\{[^}]*?top:\s*)\d+px",
                    r"\g<1>685px",
                    patched_html,
                )
                patched_html = re.sub(
                    r"(\.layer-orbital-events\s*\{[^}]*?top:\s*)\d+px",
                    r"\g<1>350px",
                    patched_html,
                )
                patched_html = re.sub(
                    r"(\.events-microcopy-pill\s*\{[^}]*?top:\s*)\d+px",
                    r"\g<1>875px",
                    patched_html,
                )
                applied_patches.append("Elevated central hero orb and light emitters by 35px to relieve bottom vertical congestion.")

            # Enhance bottom section with frosted glass cards to establish clear Gestalt separation
            if ".layer-scene-info" in patched_html:
                patched_html = re.sub(
                    r"(\.layer-scene-info\s*\{[^}]*?gap:\s*)\d+px",
                    r"\g<1>20px",
                    patched_html,
                )
                # Replace bottom date-venue row border with distinct frosted cards
                patched_html = re.sub(
                    r"(\.info-date-venue-row\s*\{[^}]*?\})",
                    """.info-date-venue-row {
      display: grid;
      grid-template-columns: 1.15fr 1.35fr;
      gap: 32px;
      align-items: start;
      padding: 24px 28px;
      background: rgba(14, 7, 40, 0.65);
      border: 1px solid rgba(122, 231, 199, 0.22);
      border-radius: 16px;
      backdrop-filter: blur(12px);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }""",
                    patched_html,
                )
                applied_patches.append("Grouped Date & Venue into a dedicated frosted glass container (12px blur, 16px radius) to eliminate visual clutter.")

        # 3. Patch: Headline dimensional weight against cosmic background
        if any(w in all_critiques for w in ["headline", "dimensional weight", "appears flat", "title font"]):
            if ".title-path2-img" in patched_html:
                patched_html = re.sub(
                    r"(\.title-path2-img\s*\{[^}]*?filter:\s*)[^;]+;",
                    r"\g<1>drop-shadow(0 30px 60px rgba(0, 0, 0, 0.98)) drop-shadow(0 0 50px rgba(122, 231, 199, 0.75)) drop-shadow(0 0 100px rgba(255, 77, 109, 0.4));",
                    patched_html,
                )
                applied_patches.append("Enhanced 3D Title depth: added multi-stage ambient occlusion and dual-color emission glow (cyan + magenta).")

        return patched_html, applied_patches
