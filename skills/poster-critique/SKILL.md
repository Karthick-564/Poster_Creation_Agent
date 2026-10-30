---
name: poster-critique
description: Use when inspecting a rendered poster for hierarchy, readability, cutout quality, spatial balance, or color harmony. Covers checkable probes, visual failure patterns, and typed patch operations.
---
# Poster Critique Skill

## Inspection Procedure
1. **Deterministic Pre-flight**: Run mechanical checks first (bounding box overlaps, sampled pixel contrast, margin overflow).
2. **Visual Language Model (VLM) Probes**: Run focused, checkable probes via 3-sample low-temperature (T=0.1) voting against the local inspector model (`LFM3-VL-2B`):
   - **Glance Test (3-Second Readability)**: At 360px thumbnail scale, confirm Event Title and Date are immediately legible.
   - **Hero Dominance**: Confirm the hero asset anchors the composition (>= 35% of poster height, central focal point).
   - **Spatial Balance / Center Void**: Check that there is no dead empty gulf (> 400px unutilized canvas) between elements.
   - **Color Harmony**: Check that typography, card backgrounds, and button accents belong to a cohesive palette (e.g. cyber neon emerald + cyan) rather than clashing circus colors.
   - **Negative Control**: Confirm the inspector does not hallucinate non-existent items (guard against authority bias).
3. **Pairwise Comparison**: When evaluating before/after rounds, compare A vs B and B vs A to prevent presentation order bias.
4. **Typed Op Dispatch**: Map each flagged flaw to an atomic typed patch operation.

## Key Visual Failure Patterns & Patch Mapping
| Flaw Pattern | Visual Symptom | Allowed Typed Operation |
| :--- | :--- | :--- |
| `hero_too_small` | Tiny floating icon/shield (< 30% height), lacks authority | `resize_layer("hero_art_1", factor=1.75)` + `move("hero_art_1", dy=+40)` |
| `center_void` | Massive dead gap between hero and metadata | `move("card_date_venue", dy=-60)` + `resize_layer("hero_art_1", factor=1.3)` |
| `color_clash` | Circus colors (e.g. amber date + red prize + pastel mint CTA) | `swap_token(element_id, target_hex)` (e.g. unify to `#00FF66` / `#00F3FF`) |
| `low_contrast` | Sampled text pixel contrast ratio < 4.5:1 against background | `add_scrim(element_id, opacity=0.75)` |
| `margin_overflow` | Text or interactive elements clip within 50px of canvas edges | `scale_font(element_id, factor=0.88)` |
| `occlusion_detected` | Decorative asset or hero art overlaps headline text | `set_z(element_id, z=25)` or `move("hero_art_1", dy=+50)` |
| `amateur_typography` | Squished 3D raster text or unreadable fonts | Switch to crisp vector display typography with proper letter-spacing |
