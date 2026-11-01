---
name: poster-design-studio
description: Master skill for AI art direction, composition patterns (Z-Pattern, Focal Point, 3-Column Grid, Split Layout), typography hierarchy, era/movement anchoring, and multi-model diffusion orchestration (Ideogram background + Qwen-Image RGBA hero).
---
# Poster Design Studio: Art Direction & Composition Skill

> Based on Brian Gardner's `DESIGN.md`, *PosterGen (CVPR 2026)*, *PosterMELD (2026)*, and professional editorial graphic design principles.

## 1. Compositional Pattern Selection

Analyze the brief's text density, event genre, and emotional tone, then select one of 4 proven patterns:

| Composition Pattern | Ideal Use Cases | Structure & Eye Flow |
| :--- | :--- | :--- |
| **Focal Point (Centered)** | Bold graphic posters, single subject heroes, music gigs, art exhibitions | Hero anchored at $(x=50\%, y\approx 42\%)$. Typography crowns top or anchors base. Elements radiate symmetrically. |
| **Z-Pattern** | Image-heavy posters, cinematic events, festivals | Top-left presenter $\rightarrow$ Top-right date badge $\rightarrow$ Diagonal slice through hero/title $\rightarrow$ Bottom-left highlights $\rightarrow$ Bottom-right CTA. |
| **Split Layout (50/50 or 60/40)** | Editorial, high-contrast cultural fests, conferences, academic talks | Clean horizontal or vertical division. Art zone occupies 55%, calm typographic zone occupies 45%. Zero visual clutter. |
| **3-Column Grid** | Content-dense events, multi-track hackathons, symposiums, multi-stage expos | Full-width headline $\rightarrow$ Eye-level visual anchor at top of center column $\rightarrow$ Left column (Tracks) / Right column (Speakers/Prizes) $\rightarrow$ Monospace footer. |

---

## 2. Eliminating AI Slop: Movement & Era Anchors

Never prompt with generic, empty adjectives like *"modern, sleek, futuristic, eye-catching, professional"*. Those cause diffusion models to fall back to generic digital gradients and saturated yellow/cyan slop.

Always anchor the art direction in a recognized design movement:
* **Swiss / International Typographic Style**: Asymmetric grid, massive bold grotesque type, generous white space, clean photography or geometric emblems.
* **Bauhaus / Constructivism**: Strong geometric primitives, diagonal tension, heavy structural bars, primary and secondary color discipline.
* **Risograph / Screenprint**: Tactile grain, spot-color duotones, gentle ink misregistration, organic paper texture.
* **Warm Paper-Cut / Relief**: Layered dimensional paper shapes, tactile drop shadows, organic daylight, natural leaf and water curves.
* **Editorial / Contemporary Culture**: High-fashion serif headlines, museum-grade calm, spacious margins, subtle lighting.
* **Technical Monospace / Terminal**: Precision wireframe grid, hairline dividers, monospace data belts (for security/CTF/developer summits).

---

## 3. Strict Typographic Hierarchy (Hard Rules)

1. **Max 2 Typeface Families per Poster**:
   - 1 Display family for Title / Headline.
   - 1 Neutral grotesque or monospace family for all body, dates, logistics, and metadata.
2. **Mathematical Scale**:
   - **Headline**: $72\text{pt} - 120\text{pt}$ (scale for canvas height), max 3 lines.
   - **Subheadline**: $\approx \frac{1}{3}$ to $\frac{1}{4}$ of headline size ($24\text{pt} - 32\text{pt}$).
   - **Body / Metadata**: $14\text{pt} - 18\text{pt}$ minimum for print legibility at arm's length.
3. **Contrast Rules**:
   - Body text: $\ge 4.5:1$ WCAG contrast ratio against its direct background.
   - Large text ($\ge 24\text{pt}$): $\ge 3.0:1$ WCAG contrast ratio.
4. **Role-Based Color Assignment (No Rainbow Lines)**:
   - 60% Canvas Base (Background / negative space).
   - 30% Structural (Body text, logistics, dates, venue).
   - 10% High-Impact Accent (Grand Prize, Registration CTA URL).

---

## 4. Multi-Model Asset Generation & Seamless Blending

### 4.1 Ideogram 4.0: Atmospheric Background Art (Layer 0)
* **Rule**: Ideogram must generate **only the environmental background** with dedicated calm negative space for text overlays.
* **Negative Prompting**:
  `"PURE NON-TEXT BACKGROUND ARTWORK: ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO SIGNAGE, NO LABELS, NO WATERMARKS, NO NUMBERS."`
* **Elements Array**: Always pass `"elements": []` so Ideogram does not generate labeled sub-objects.
* **Negative Space Requirement**: Prompt must specify calm zones:
  `"Empty calm center and lower zones leaving clean negative space for typography overlay."`

### 4.2 Qwen-Image 2.1: Isolated 3D Hero Cutout (Layer 3)
* **Rule**: Qwen generates a single high-definition isolated hero subject on pure transparent or black background for alpha extraction.
* **Prompt**:
  `"Isolated 3D <subject>, <design movement anchor>, directional studio lighting from <direction>, crisp outer silhouette, pure black background, no text, no letters."`

### 4.3 Seamless Combination Directives
1. **Light Consistency**: The background prompt and hero prompt must specify the exact same light direction (e.g. "warm daylight from top-left" or "cool directional rim light from top-right").
2. **Palette Harmony**: The hero and background must share the same core hue family (derived from brief or hero).
3. **Depth Stacking**:
   - Layer 0: Background art.
   - Layer 1: Scrim / subtle lighting gradient bridge.
   - Layer 2: Vector Title typography.
   - Layer 3: Hero asset alpha cutout overlapping lower title by $30\text{px} - 50\text{px}$.
   - Layer 4: Vector body typography and hairline dividers.

