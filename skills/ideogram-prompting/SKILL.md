---
name: ideogram-prompting
description: Expert skill for synthesizing structured JSON prompts for Ideogram 4.0 diffusion models, strictly controlling text-safe negative space and preventing unwanted text hallucinations on background art.
---
# Ideogram 4.0 Prompt Engineering Skill

## 1. Official Ideogram 4.0 JSON Schema

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

## 2. Preventing Background Text Hallucinations (The Negative Text Rule)

Ideogram was specifically trained to render text when it detects words, signage, posters, labels, or telemetry in prompts.
To generate **pure atmospheric background art** without any baked-in letters, words, or phantom typography:
1. **Empty Elements Array (`"elements": []`)**: When generating Layer 0 backgrounds, the `elements` list MUST BE `[]`. Do NOT define sub-objects that could be misinterpreted as having labels or signage.
2. **Explicit Negative Directives in `art_style`**:
   The `art_style` field must explicitly state:
   `"contemporary atmospheric background key visual with clean calm negative space. PURE NON-TEXT BACKGROUND ARTWORK: ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO SIGNAGE, NO LABELS, NO WATERMARKS, NO NUMBERS."`
3. **Calm Safe-Zone Allocation in `background`**:
   The `background` field must explicitly specify text-safe calm zones:
   `"Deep ambient background in tones of #0B132B with soft atmospheric light spill, leaving the top 30% header zone and bottom 35% footer zone completely dark, flat, and calm for vector typography overlays."`
4. **Avoid Typography-Inducing Trigger Words**:
   Never use words like: `"telemetry"`, `"screens"`, `"monitors"`, `"billboards"`, `"labels"`, `"signs"`, `"neon sign"`, `"dashboard"`, or `"written"`. Use environmental words like: `"volumetric light curtains"`, `"cosmic mist"`, `"laser beams"`, `"deep gradient field"`, `"atmospheric glow"`.

