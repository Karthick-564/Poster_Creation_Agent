---
name: poster-critique
description: Use when inspecting a rendered poster for hierarchy, readability, cutout quality or balance, or when choosing between two poster candidates. Covers probes, failure patterns and patch mapping.
---
# Poster Critique
## Procedure
1. Run deterministic checks first; call the inspector only when zero blocking issues remain.
2. Ask the probes in `references/probes.md` one at a time (3-second glance test, dominant element, covered text, negative control).
3. Take 3 samples at low temperature (T=0.1) and take the majority verdict.
4. Compare candidates or before/after pairwise, in both orders (A vs B, B vs A).
5. Map each grounded finding to an allowed typed op (`scale_font`, `move`, `set_z`, `resize_layer`, `add_scrim`, `swap_token`, `regenerate_asset`).
## Failure patterns
- Decorative layer touching headline glyphs
- Dark halo around cutouts
- Key facts (time, team size, price) in the smallest type
- Micro-labels below minimum size
- Text over busy art without a scrim
