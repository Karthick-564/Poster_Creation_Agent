# ComfyUI / Diffusion Texture Layers & The Strict Truth Rule

**Status**: Architectural Doctrine & Asset Strategy  
**Project**: Automated Poster Design Agent  

---

## 1. The Core Architecture Principle: Division of Labor

The central failure mode of single-prompt end-to-end diffusion models (like Midjourney, Ideogram, or DALL-E) when generating posters is **text hallucination and layout entropy**. Diffusion models excel at organic textures, lighting, painterly depth, and atmosphere, but struggle with exact typographic kerning, strict alignment, and verbatim copy reproduction.

Conversely, vector rendering engines (VectorCraft) excel at mathematically exact vector geometry, sub-pixel typography, deterministic contrast, and strict hierarchy, but cannot generate photographic subjects or complex atmospheric lighting from scratch.

Therefore, our architecture enforces a strict division of labor:

```
+------------------------------------------------------------------------+
|                               DIFFUSION                                |
|        (ComfyUI / Ideogram / Flux: Pure Texture & Atmosphere)          |
|  - Abstract gradient washes & neon smoke                               |
|  - Crowd silhouettes, stage lighting, bokeh light streaks              |
|  - Painterly character hero cutouts & photographic textures            |
|  - STRICT TRUTH: 0% typography, 0% lettering, 0% watermarks            |
+------------------------------------------------------------------------+
                                   |
                                   v  (Layer 0 Background / Layer 3 Hero)
+------------------------------------------------------------------------+
|                               VECTORCRAFT                              |
|          (Vector Engine: Typography, Layout & Composition)             |
|  - 100% Verbatim copy & strict text hierarchy                          |
|  - Mathematical contrast enforcement & WCAG compliance                 |
|  - Non-destructive alpha scrims, radial spotlights & borders           |
|  - Asymmetric editorial grids & ticket-stub CTA containers             |
+------------------------------------------------------------------------+
```

---

## 2. The Strict Truth Rule: No Baked Text

### The Problem: Hallucinated Pseudo-Text
When diffusion prompts contain words like "poster", "headline", "title", or "signage", the model inevitably bakes illegible glyph clusters, deformed letterforms, or hallucinated words (e.g. "Clomailioka", "2030", "NEON", mangled EDM acronyms) into the pixel background. 

Once baked into a raster layer:
1. They violate the whole-token verbatim requirement.
2. They collide with vector typography, creating muddy, amateur artifacts.
3. They cannot be edited, recolored, or moved.

### Strict Prompting Discipline
To prevent baked pseudo-text at the generation source:
- **Never include negative text incantations** like "NO TEXT / NO WORDS / NO LETTERS" in prompts. Diffusion models frequently invert or misinterpret negative tokens, accidentally triggering letterform synthesis.
- **Use pure environmental descriptors**: "ambient neon lighting, deep blue atmospheric haze, cyan light beam, dark violet background texture, clean negative space, cinema 4D render, smooth gradient wash".
- **Describe subject & medium only**: "silhouette of music crowd with hands raised under laser lights, dark noir club atmosphere, volumetric fog".

---

## 3. The Background OCR Gate (`check_background_ocr`)

Prompt discipline alone is insufficient; diffusion models are stochastic. Therefore, an automated **Background OCR Gate** must inspect every generated raster layer (`layer0_bg.png`, `layer3_hero.png`) before layout assembly.

### Detection Mechanism
1. **Pytesseract / EasyOCR Scan**: Scan raster layers for alphanumeric token sequences ($\ge 3$ characters).
2. **Frequency Clustering Heuristic** (if OCR engine offline):
   - High-contrast edge clustering in expected negative-space zones.
   - Connected component analysis identifying recurring glyph-like height distributions (10–30px).
3. **Gate Verdict**:
   - **PASS**: No detected text or unmapped characters.
   - **REJECT**: If unmapped text is found, trigger up to 1 sanitized prompt retry. If retry still leaks pseudo-text, issue honest `PLANNING_HALT` or fall back to a clean deterministic vector substrate. Never ship or measure an asset with baked refusal or pseudo-text.

---

## 4. Texture & Atmosphere Layer Library

### Layer Type A: Neon Atmospheric Wash
- **Prompt**: `"Abstract cinematic atmospheric wash, deep navy #070B19 base with glowing cyan and ultraviolet laser streaks, soft bokeh haze, volumetric fog, clean dark center"`
- **VectorCraft Integration**: Placed as `layer0_bg.png` at `[0, 0, width, height]`. A `soft_scrim` is applied across the lower $40\%$ to ensure body copy contrast.

### Layer Type B: Crowd & Stage Lighting (Hero Layer)
- **Prompt**: `"Silhouette of music festival crowd with hands raised against concert stage lighting, cyan rim lighting, dark deep shadow foreground, 8k resolution"`
- **VectorCraft Integration**: Placed as `layer3_hero.png` with `blend_mode: "screen"` or `feather_radius: 20.0`. This dissolves harsh box edges into the dark background substrate.

### Layer Type C: Abstract Cybernetic Geometry
- **Prompt**: `"Subtle minimalist dark geometric wireframe grid, deep indigo backdrop, faint glowing lines, high depth of field, wide negative space"`
- **VectorCraft Integration**: Placed behind typography; VectorCraft native vector shapes (dividers, ticket containers) align directly with the atmospheric grid.

---

## 5. Pipeline Contract Summary

1. **Diffusion outputs are raw materials, not finished designs.**
2. **Every raster layer must pass `check_background_ocr` before entering the MCP composition loop.**
3. **All typography, badges, rules, buttons, and ticket stubs must be rendered natively in VectorCraft.**
