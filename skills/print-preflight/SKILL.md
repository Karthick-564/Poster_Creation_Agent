---
name: print-preflight
description: Use when validating and exporting print-ready master files (PDF/X-4, TIFF, PNG) for industrial print formats (A4, A3, A2, A1, 24x36in). Computes effective DPI per layer.
---
# Print Pre-Flight
## Rules
1. Calculate effective DPI for each raster layer: `effective_dpi = image_pixel_dim / (target_print_dimension_inches)`.
2. Do not falsely certify an upscaled low-res canvas as true 300 DPI if source art is 88 DPI. Report effective DPI per layer.
3. Ensure 3mm bleed exists on all 4 sides.
4. Ensure critical text and logos sit inside the 6mm safe margin.
5. Export PDF with embedded vector typography.
