---
name: poster-design-craft
description: Master doctrine for editorial poster design, compositional archetypes, authentic movement anchors, Swiss typographic scale, multi-model diffusion orchestration (Ideogram 4.0 background + Qwen-Image 2.1 RGBA hero), and zero-text gate enforcement.
---
# Poster Design Craft: Master Editorial & Art Direction Doctrine

> Operational distillation of `DESIGN.md`, *PosterGen (CVPR 2026)*, *PosterMELD (2026)*, and Swiss International Typographic style.

## 1. The Cardinal Rule: Posters are NOT Web Dashboards
An event poster is a large-format **editorial art piece**, not a mobile phone screen or SaaS dashboard.
- **NEVER DRAW CONTAINER CARDS**: Do not wrap event names, dates, or prices in rounded rectangle boxes (`add_shape_rectangle`), pill badges, or colored card backgrounds.
- **NEVER USE WEB BUTTONS**: A Call-To-Action (CTA) on a poster is a typographic link (e.g. `REGISTER: site.example/join`), NOT an HTML submit button with a colored background pill.
- **TEXT SITS DIRECTLY ON THE ATMOSPHERE**: Typography integrates directly into the background art, separated by subtle lighting gradients, optical drop shadows, or fine technical hairline rules (1px width).
- **NO DIGITAL SLOP**: No gratuitous procedural sparkles, random starfields, or digital gradient noise.

## 2. Core Philosophy & Design Hierarchy
1. **Hierarchy Before Decoration**: Every pixel on the canvas must serve visual communication. If an ornament does not guide the viewer's eye to the title, date, or message, it does not belong on the poster.
2. **Space Makes Things Matter (Negative Space)**: Empty space is an active design element, not "wasted canvas." Background art must feature deliberate, calm negative space where typography can breathe and maintain uncompromised contrast.
3. **Contrast & Authority**: Maintain commanding visual presence through scale, weight, and strict spatial relationships.

## 3. Compositional Archetypes
Analyze the brief's text density, event genre, and emotional tone, then select one of 4 proven archetypes:

| Composition Pattern | Ideal Use Cases | Structure & Eye Flow |
| :--- | :--- | :--- |
| **Archetype A: Focal Point (Centered)** | Bold graphic posters, single subject heroes, music gigs, art exhibitions | Hero anchored at $(x=50\%, y\approx 42\%)$. Typography crowns top or anchors base. Elements radiate symmetrically. Eye flow: Central hero $\rightarrow$ Headline $\rightarrow$ Date/Venue anchor $\rightarrow$ Bottom CTA. |
| **Archetype B: Z-Pattern** | Image-heavy posters, cinematic events, festivals, low-to-medium text | Top-left presenter $\rightarrow$ Top-right date badge $\rightarrow$ Diagonal slice through hero/title $\rightarrow$ Bottom-left highlights $\rightarrow$ Bottom-right CTA. |
| **Archetype C: Split Layout (50/50 or 60/40)** | Editorial, high-contrast cultural fests, conferences, academic talks | Clean horizontal or vertical division. Art zone occupies 55%, calm typographic zone occupies 45%. Zero visual clutter. |
| **Archetype D: 3-Column Grid** | Content-dense events, multi-track hackathons, symposiums, multi-stage expos | Full-width headline $\rightarrow$ Eye-level visual anchor at top of center column $\rightarrow$ Left column (Tracks) / Right column (Speakers/Prizes) $\rightarrow$ Monospace footer. |

## 4. Visual Balance & The Thumbnail Glance Test
- **The 3-Second Glance Test**: At a 300px thumbnail scale, confirm Event Title and Date are immediately legible and recognizable. If the title is unreadable or gets lost at 300px, hierarchy and contrast have failed.
- **Hero Canvas Placement & Scale**: Hero asset canvas footprint should cover 30–60% of the poster canvas height to command the composition without crowding typography. (Note: 65–80% applies to the Qwen generation frame during asset creation; 30–60% applies to the poster canvas for final placed size).
- **Spatial Balance / Center Void**: Avoid large unutilized gaps (> 400px dead canvas) between elements; maintain intentional rhythm and proportion.

## 5. Movement & Era Anchors (Anti-Slop Table)
Never prompt with generic, empty adjectives like *"modern, sleek, futuristic, eye-catching, professional"*. Those cause diffusion models to fall back to generic digital gradients and saturated yellow/cyan slop.

Always anchor the art direction in a recognized design movement:

| Movement / Era | Visual Language & Techniques | Typical Palette & Materials |
| :--- | :--- | :--- |
| **Swiss / International Typographic Style** | Asymmetric grid, massive bold grotesque type, generous white space, clean photography or geometric emblems. | Monochromatic base with bold primary accents (red, cobalt, black). |
| **Bauhaus / Constructivism** | Strong geometric primitives, diagonal tension, heavy structural bars, primary and secondary color discipline. | Raw paper, black, vermilion, cadmium yellow, industrial gray. |
| **Risograph / Screenprint** | Tactile grain, spot-color duotones, gentle ink misregistration, organic paper texture. | Fluorescent pink, sunflower yellow, teal, warm uncoated paper. |
| **Warm Paper-Cut / Relief** | Layered dimensional paper shapes, tactile drop shadows, organic daylight, natural leaf and water curves. | Terracotta, sage, oatmeal, cream, deep forest tones. |
| **Editorial / Contemporary Culture** | High-fashion serif headlines, museum-grade calm, spacious margins, subtle lighting. | Off-black, alabaster, muted ochre, bronze accents. |
| **Technical Monospace / Terminal** | Precision wireframe grid, hairline dividers, monospace data belts (for security/CTF/developer summits). | Deep obsidian, phosphor green or electric cyan, cool titanium. |

## 6. Strict Typographic Hierarchy & Scale
1. **Max 2 Typeface Families per Poster**:
   - 1 Display family for Title / Headline (`OFL-Display` or `OFL-Sans`).
   - 1 Neutral grotesque or monospace family for all body, dates, logistics, and metadata (`OFL-Sans` or `OFL-Mono`).
   - *Never* mix 3 or 4 unrelated fonts.
2. **Mathematical Scale**:
   - **Headline**: $72\text{pt} - 120\text{pt}$ (scale for canvas height, min $60\text{pt}$), max 3 lines.
   - **Subheadline / Date / Grand Prize**: $\approx \frac{1}{3}$ to $\frac{1}{4}$ of headline size ($22\text{pt} - 32\text{pt}$). Command secondary attention.
   - **Lineup & Logistics (Tertiary)**: $16\text{pt} - 20\text{pt}$. Formatted as typographic ribbons:
     `ROBO COMBAT   •   AUTONOMOUS DRONES   •   NEURAL HACK` or
     `BATTLE OF BANDS   //   HACKNIGHT   //   DJ NIGHT`
   - **Metadata / Blurb / Footer**: $12\text{pt} - 18\text{pt}$ ($14\text{pt}$ minimum for print legibility at arm's length).
3. **Contrast & Legibility (WCAG 2.1)**:
   - Body text: $\ge 4.5:1$ WCAG contrast ratio against direct background.
   - Large text ($\ge 24\text{pt}$): $\ge 3.0:1$ WCAG contrast ratio.

## 7. Palette & Color Policy (No Rainbow Lines)
- **Role-Based Color Distribution (60-30-10 Rule)**:
  - 60% Canvas Base: Background atmosphere and negative space.
  - 30% Structural: Body text, dates, logistics, venue (clean, neutral, unified).
  - 10% High-Impact Accent: Grand Prize or Registration CTA URL.
- **Single Structural Color**: All body text shares one cohesive structural tone (e.g. `#FFFFFF` on dark, or `#1F2A24` on light). Never assign random rainbow colors to metadata rows.

## 8. Depth Architecture & Layer Z-Stacking
Cinematic depth is achieved by interleaving vector elements and raster cutouts:
- **Layer 0**: Full-bleed background illustration (covers 100% of the canvas).
- **Layer 1**: Ambient scrim / subtle gradient fade / radial light spill (screen-blended color glow).
- **Layer 2**: Massive Headline Display Title ($72\text{pt} - 120\text{pt}$).
- **Layer 3**: 3D Hero Cutout Asset (with native alpha transparency). The upper crown of the hero cutout physically overlaps the lower base of the headline title letters by $30\text{px} - 50\text{px}$. This creates the optical illusion that the subject breaks forward out of the canvas.
- **Layer 4**: Foreground procedural accents (subtle dust, lighting rays, fine hairlines).
- **Layer 5**: Editorial typography (lineup, prize ribbon, dual-language venue, CTA link).
- **Layer 6**: Border rules, bleed margins, and pre-flight marks.

## 9. Asset Generation Strategy & Resolution
- **Background (Ideogram 4.0)**: Render at $896\times 1120$ (4:5 aspect ratio, multiples of 16), then upscale with Lanczos filter to target canvas ($1080\times 1350$).
- **Hero Cutout (Qwen-Image 2.1)**: Render at $768\times 768$ square frame.
  - Scope clarity: 65–80% applies to the Qwen GENERATION FRAME (asset creation); 30–60% applies to the poster CANVAS (final placed size). Different scopes, not a contradiction — say so explicitly so no agent reads them as conflicting.
- **Light Consistency**: The background prompt and hero prompt must specify the exact same light direction (e.g. "warm daylight from top-left" or "cool directional rim light from top-right").
- **Palette Harmony**: Hero and background must share the same core hue family.

## 10. Multi-Model Prompt Engineering & The Zero-Text Gate

### 10.1 Ideogram 4.0 JSON Schema
Ideogram 4.0 natively expects an ordered JSON structure:
```json
{
  "high_level_description": "A concise 1-2 sentence description of the overall scene and composition.",
  "style_description": {
    "aesthetics": "Keywords describing visual taste and mood (e.g. ethereal, high-tech, cinematic, minimalist).",
    "lighting": "Specific light sources, direction, and volumetric quality.",
    "medium": "digital_illustration",
    "art_style": "Specific artistic discipline or historical style reference.",
    "color_palette": ["#RRGGBB", "#RRGGBB", "#RRGGBB"]
  },
  "compositional_deconstruction": {
    "background": "Detailed description of the background environment and lighting gradients.",
    "elements": []
  }
}
```

### 10.2 Zero-Text Gate (pipeline-hardened)
Ideogram was specifically trained to render text when it detects words, signage, posters, labels, or telemetry in prompts. To generate **pure atmospheric background art** without any baked-in letters, words, or phantom typography:
1. **Empty Elements Array (`"elements": []`)**: `elements: []` is a HARD GATE for Layer 0 backgrounds (the pipeline prompt enforces it — per this skill's own "the gate wins" rule). Do NOT define sub-objects that could be misinterpreted as having labels or signage.
2. **Explicit Negative Directives in `art_style`**: The `art_style` field must explicitly use the exact pipeline negative string:
   `"contemporary atmospheric background key visual with clean calm negative space. PURE NON-TEXT BACKGROUND ARTWORK: ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO SIGNAGE, NO LABELS, NO WATERMARKS, NO NUMBERS."`
3. **Calm Safe-Zone Allocation in `background`**: The `background` field must explicitly specify text-safe calm zones:
   `"Deep ambient background in tones of #0B132B with soft atmospheric light spill, leaving the top 30% header zone and bottom 35% footer zone completely dark, flat, and calm for vector typography overlays."`
4. **Banned Trigger-Word List & Environmental Replacements**:
   - Never use words like: `"telemetry"`, `"screens"`, `"monitors"`, `"billboards"`, `"labels"`, `"signs"`, `"neon sign"`, `"dashboard"`, or `"written"`.
   - Use environmental words instead: `"volumetric light curtains"`, `"cosmic mist"`, `"laser beams"`, `"deep gradient field"`, `"atmospheric glow"`.

### 10.3 Qwen-Image 2.1 Hero Cutout Prompting
- Purpose: Generates the primary focal subject on an empty alpha / black background.
- Clean silhouette, directional lighting matching Layer 0.
- Standard prompt structure:
  `"Isolated 3D <subject description>, <art movement style>, directional studio lighting from <direction>, crisp outer silhouette, pure black background for alpha extraction, high detail, centered, no text, no letters."`
- Must end with: `"isolated on empty alpha channel, transparent background, clean sticker cutout, 3D render, sharp edges, no background"`.

## 11. Compositing Recipe & Lighting Integration
1. **Seamless Light Matching**: Planner enforces identical light source angle and temperature across background and hero.
2. **Gradient Scrims**: Use soft gradient fills with per-stop opacity (`paint.setFill` gradient stops) under text areas to ensure legibility without ugly card boxes.
3. **Alpha Feathering**: Ensure hero asset has clean, halo-free alpha edges before compositing.
4. **Overlap Depth**: Hero Layer 3 overlaps Headline Layer 2 by 30px–50px, establishing instant physical foreground presence.

## 12. Pre-flight Certification & Production Standards
- **Canvas Dimensions**: Standard $1080\times 1350$ (4:5) rendered at $2\times$ scale $\rightarrow$ $2160\times 2700\text{px}$ master print raster.
- **Margins & Safe Zones**: Minimum 40px–50px safety margin on all edges.
- **Physical Output**: VectorCraft headless CLI builds dual deliverables (`master_print.pdf` and `master_render_2x.png`).

## 13. Quality Review Rubric & Failure Patterns
When evaluating poster candidates, apply the following checkable rubric:
- **3-Second Glance Test**: Downscale to 300px thumbnail. Are the title and date unmistakable?
- **Web UI Check**: Zero container cards, zero button pills, zero SaaS dashboard UI.
- **Hero Stature**: Occupies 30–60% of poster canvas height; crisp silhouette; no alpha fringing.
- **Typographic Discipline**: Maximum 2 font families; clear mathematical hierarchy (headline $\ge 72\text{pt}$, body $\ge 14\text{pt}$).
- **Contrast Compliance**: Minimum 4.5:1 for body copy; 3.0:1 for display typography.

