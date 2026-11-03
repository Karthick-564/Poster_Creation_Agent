# Official KCT logo slot

Place the official Kumaraguru College of Technology mark here as:

```
assets/brand/kct/kct_logo.png
```

Requirements:

- Transparent PNG (or a PNG that composites cleanly on the contracted solid
  field).
- At least 1200 px wide for print use.
- Do not crop, recolor, stretch, or add effects.
- The pipeline rescales the placement box to the asset's intrinsic aspect ratio
  and keeps the contracted 10 mm clear space around it.

**Do not use `assets/logo_kumaraguru.png`.** That file is an Apex Institute of
Technology demo mark and was the source of the legacy pipeline's brand
contamination. Until the official asset is present, v2 mock runs use a clearly
marked placeholder and the `logo_placeholder` warning remains in the audit
trail.
