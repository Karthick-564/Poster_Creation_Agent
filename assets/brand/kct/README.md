# Official KCT logo assets

Canonical logo slot used by the v2 pipeline:

```
assets/brand/kct/kct_logo.png
```

This file is the **official KCT secondary rectangle logo** extracted from the
Kumaraguru College of Technology Brand Style Guide 2020 (V1.00), page 8
("Colour & Monotone"), KCT Blue version. It is a high-resolution raster of the
original vector artwork, not a redraw, upscale, or recolour.

## Asset set

| File | Source | Size | Use |
| --- | --- | --- | --- |
| `kct_logo.png` | Brand guide p.8, V1 secondary KCT Blue | 2222 × 728, RGBA | **Canonical** top-right lockup |
| `kct_logo_primary.png` | Brand guide p.8, V1 primary KCT Blue | 1367 × 1367, RGBA | Primary square mark when height is not restricted |
| `kct_logo_mono.png` | Brand guide p.8, V1 secondary monotone | 2222 × 728, RGBA | Single-ink / monochrome production |
| `kct_logo_primary_mono.png` | Brand guide p.8, V1 primary monotone | 1367 × 1367, RGBA | Single-ink primary mark |
| `kct_logo_v2_secondary.png` | Brand guide p.7, V2 secondary line art | 2562 × 846, RGBA | Approved alternate; blue-on-transparent |
| `kct_logo_v2_primary.png` | Brand guide p.7, V2 primary line art | 1376 × 1377, RGBA | Approved alternate; blue-on-transparent |
| `kct_logo_web_header.png` | `kct.ac.in` header asset | 445 × 119, RGBA | Web reference only — **not print-ready** |

`provenance.json` records the exact PDF page, crop rectangle, render zoom and
SHA-256 for every file.

## Placement rules enforced by the pipeline

* Top-right corner of the contracted format.
* 10 mm clear space on every side (118.11 px at 300 dpi).
* Intrinsic aspect ratio preserved; the planner resizes the slot from the
  asset's real pixel dimensions before composition.
* A solid `#FFFFFF` field is painted behind the mark. No gradient, photo or
  texture may sit under the logo.
* No recolouring, cropping, stretching, rotation, drop shadows, outlines or
  extra elements.
* The mark is never silently substituted. If `kct_logo.png` is missing, the
  brand gate blocks delivery (or a clearly marked placeholder is used only
  when explicitly requested).

## What not to use

`assets/logo_kumaraguru.png` is an **Apex Institute of Technology demo mark**.
It is not the KCT logo and must never be used for KCT output.

`kct_logo_web_header.png` is the 445 px website header. It is useful for
recognition and provenance, but it is below the 1200 px print threshold and
must not be used for posters.
