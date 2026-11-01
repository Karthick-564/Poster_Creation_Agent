# DESIGN.md — Poster Design System Specification & Art Direction Framework

> Inspired by Brian Gardner's `DESIGN.md` specification standard, *PosterGen (CVPR 2026)*, *PosterMELD (2026)*, and professional graphic design principles.
> This document specifies the visual rules, architectural constraints, and prompt-engineering directives for the AI Planner and Renderer.
> Operational distillation of this standard (movement table, compositing recipe, review rubric) lives in `skills/poster-design-craft/SKILL.md`; keep the two in agreement.

---

## 1. Core Philosophy: Restraint, Not Digital Slop

1. **Hierarchy Before Decoration**: Every pixel on the canvas must serve visual communication. If an ornament does not guide the viewer's eye to the title, date, or message, it does not belong on the poster.
2. **Space Makes Things Matter (Negative Space)**: Empty space is an active design element, not "wasted canvas." Background art must feature deliberate, calm negative space where typography can breathe and maintain uncompromised contrast.
3. **No Web UI Clutter**: Posters are large-format editorial artworks, not mobile apps or SaaS dashboards. 
   - No floating rounded rectangle cards.
   - No web submit buttons or pill buttons for CTAs.
   - No gratuitous procedural sparkles, random starfields, or digital gradient noise.
4. **Authentic Era & Movement Anchoring**: Instead of vague prompts ("modern, sleek, futuristic") that collapse diffusion models into generic yellow/cyan slop, every poster must be anchored in a concrete design movement:
   - *Swiss / International Typographic Style*: Asymmetric grids, massive clean grotesque typography, mathematical whitespace, photography or bold geometric symbols.
   - *Bauhaus / Constructivism*: Primary geometric forms, diagonal dynamism, structural bars, high contrast.
   - *Risograph / Screenprint*: Grain texture, duotone or spot color overlays, tactile misregistration, paper warmth.
   - *Editorial / High-Culture*: Elegant serif typography, generous margins, restrained focal imagery, museum-grade calm.
   - *Paper-Cut / Organic Layered*: Tactile cut-out relief, soft drop shadows, warm daylight, natural fiber textures.
   - *Technical Terminal / Cyberpunk*: Clean monospace grids, hairline rules, tactical wireframes (only when explicitly requested by a cybersecurity/tech brief).

---

## 2. The 4 Compositional Archetypes

The AI Planner must analyze the brief's text density and mood, then select exactly one of these 4 archetypes:

### Archetype A: Focal Point (Centered Radiance)
* **Best for**: Bold graphic posters, single subject heroes, music gigs, rallies, art exhibitions.
* **Layout**:
  - The hero subject is anchored strictly at the optical center ($x = 50\%$, $y \approx 42\%$).
  - All secondary metadata, hairline rules, and accents radiate outward.
  - The headline is either crowned directly above the hero or locks into its base.
* **Eye Flow**: Central hero $\rightarrow$ Headline $\rightarrow$ Date/Venue anchor $\rightarrow$ Bottom CTA.

### Archetype B: Z-Pattern (Editorial Scan)
* **Best for**: Low-to-medium text posters, cinematic announcements, festival headliners.
* **Eye Flow**:
  1. Top-Left: Event presenter / institutional mark.
  2. Top-Right: Event date / badge / edition.
  3. Diagonal: Slices down through the primary hero artwork and massive title.
  4. Bottom-Left: Highlight events / lineup ribbons.
  5. Bottom-Right: Primary call to action and registration URL.

### Archetype C: Split Layout (50/50 or 60/40)
* **Best for**: High-contrast editorial, modern corporate, exhibition catalogs, speaker showcases.
* **Layout**:
  - Clear horizontal or vertical division.
  - One zone (e.g. upper 55%) is dedicated to rich, full-bleed artwork.
  - The other zone (e.g. lower 45%) is a solid or calm atmospheric field with pristine typographic layout.
  - No messy overlap; crystal-clear separation between imagery and dense text.

### Archetype D: 3-Column Grid (Content-Dense & Academic)
* **Best for**: Hackathons with multi-track schedules, symposiums, multi-stage festivals, conferences.
* **Layout**:
  - Header: Massive headline spanning all 3 columns.
  - Mid-section: Visual anchor at eye-level (top of center column) flanked by Left Column (Tracks/Schedule) and Right Column (Speakers/Prizes).
  - Footer: Monospace technical details, venue coordinates, and registration barcode/CTA.

---

## 3. Strict Typographic Constraints (Hard Rules)

1. **Max 2 Typeface Families per Poster**:
   - Primary: Display font for headline (`OFL-Display` or `OFL-Sans`).
   - Secondary: Structural text for body, metadata, logistics (`OFL-Sans` or `OFL-Mono`).
   - *Never* mix 3 or 4 unrelated fonts.
2. **Mathematical Scale**:
   - **Headline**: $72\text{pt} - 120\text{pt}$ (proportional to canvas height), maximum 3 lines. Never shrink below $60\text{pt}$.
   - **Subheadline**: $\approx \frac{1}{3}$ to $\frac{1}{4}$ of headline size ($24\text{pt} - 32\text{pt}$).
   - **Body & Metadata**: Minimum $14\text{pt} - 18\text{pt}$ for print legibility at arm's length.
3. **Contrast & Legibility (WCAG 2.1)**:
   - Body text: Minimum $4.5:1$ contrast ratio against its direct background.
   - Large display text ($\ge 24\text{pt}$): Minimum $3.0:1$ contrast ratio.
4. **No Rainbow Lines**:
   - All body text shares one cohesive structural color (e.g. `#FFFFFF` on dark, or `#1F2A24` on light).
   - Accents (pop colors) are strictly reserved for the single highest-impact data point: the **Grand Prize** or the **CTA URL**.

---

## 4. Multi-Layer Diffusion Prompt Engineering

### 4.1 Ideogram (Layer 0 Background Art)
* **Purpose**: Generates the atmospheric, environmental background with **guaranteed zero text**.
* **Negative Regulations (What it must NOT do)**:
  - Must never contain baked-in letters, signs, badges, watermarks, or pseudo-words.
  - Must never contain isolated floating cards or fake UI widgets.
* **Prompt Construction**:
  ```json
  {
    "high_level_description": "<Art style anchor> background scene for <event type>, atmospheric lighting, wide view, empty center calm zone.",
    "style_description": {
      "aesthetics": "<Movement anchor, e.g. Bauhaus minimalism / warm paper-cut / Risograph spot color>",
      "lighting": "<Directional lighting matching hero, e.g. soft warm daylight from top-left>",
      "medium": "digital_illustration",
      "art_style": "PURE NON-TEXT BACKGROUND ARTWORK: ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO SIGNAGE, NO LABELS, NO WATERMARKS.",
      "color_palette": ["<canvas_base>", "<surface_tone>", "<accent_tone>"]
    },
    "compositional_deconstruction": {
      "background": "<Atmospheric description leaving upper 30% and lower 40% calm for vector typography overlay>",
      "elements": []
    }
  }
  ```

### 4.2 Qwen-Image 2.1 (Layer 3 Foreground Hero Cutout)
* **Purpose**: Generates the primary focal subject on a **transparent alpha background**.
* **Negative Regulations**:
  - Must be a single, cohesive, isolated asset with a clean silhouette.
  - Zero background scene, zero frames, zero borders.
* **Prompt Construction**:
  ```text
  Isolated 3D <subject description>, <art movement style>, studio lighting matching <light direction>, crisp defined outer edges, clean silhouette, pure black background for alpha extraction, high detail, centered, no text, no letters.
  ```

### 4.3 Seamless Layer Combination (Eliminating Blend Issues)
1. **Light Direction Matching**: The planner must enforce the same lighting direction across both prompts (e.g., "warm rim light from top-right").
2. **Palette Bridge**: The background and hero must share the same 2 primary hue families.
3. **Depth Z-Stacking**:
   - Layer 0: Background art (100% canvas).
   - Layer 1: Ambient scrim / subtle gradient fade (transparent to canvas base) under text areas.
   - Layer 2: Vector Headline typography.
   - Layer 3: Hero asset alpha cutout. The upper edge of the hero intentionally overlaps the lower base of the headline by $30\text{px} - 50\text{px}$ for cinematic depth.
   - Layer 4: Crisp vector body typography and technical metadata rules.

