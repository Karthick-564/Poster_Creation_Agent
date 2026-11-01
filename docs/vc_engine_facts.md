# VectorCraft Engine Facts & Verified Command Shapes

This document records the exact command IDs, parameter schemas, and behavioral facts discovered from `vectorcraft-cli commands` (v0.19.0) and confirmed in engine source (`tools/vectorcraft/crates/engine/`, `crates/color/`, `crates/effects/`).

---

## 1. Paint Ordering & Engine Creation Contract
- **Source Fact**: `tools/vectorcraft/crates/engine/src/cmd/paint.rs` and `draw2/`
- **Rule**: When shapes are created (`shape.rectangle`, `shape.ellipse`, `path.create`, `shape.star`), they immediately take the paint look that is *currently active* in the session state (`add_art_turned → new_art_look(s.paint.fill, s.paint.stroke)`).
- **Consequence**: Emitting `paint.setFill` or `paint.setStroke` *after* the shape-creation command does NOT apply to the created shape; instead, it sets the paint for the *subsequent* shape.
- **Fix**: To style a new shape, `paint.setFill` / `paint.setStroke` / `stroke.set` must be emitted **before** the shape-creation command.

---

## 2. Gradient Fill (`paint.setFill`)
- **Command ID**: `paint.setFill`
- **Param Schema**:
  ```json
  {
    "gradient": {
      "kind": "linear" | "radial" | "freeform",
      "method": "classic" | "perceptual",
      "stops": [
        {
          "offset": 0.0,
          "color": "#000000",
          "opacity": 1.0,
          "midpoint": 0.5
        },
        {
          "offset": 1.0,
          "color": "#000000",
          "opacity": 0.0
        }
      ],
      "angle": 90.0,
      "start": [0, 0],
      "end": [0, 1350],
      "aspect": 100.0,
      "focal": [0, 0],
      "dither": true
    },
    "id": "<target_node_id>",
    "ids": ["<target_node_id>"]
  }
  ```
- **Key Facts**:
  - `stops`: Array of at least 2 stops. Each stop accepts `offset` (0.0 to 1.0), `color` (`#rrggbb`), `opacity` (0.0 to 1.0 or 0 to 100), and optional `midpoint` (0.13 to 0.87).
  - **Alpha Support**: Per-stop `opacity` is natively supported inside `stops`, meaning smooth gradient fades over images (soft scrims) can be created without punching opaque holes.
  - Linear vectors are defined by `start: [x1, y1]` and `end: [x2, y2]` (or `angle: degrees`). Radial gradients additionally support `aspect` (% ratio of height/width) and `focal: [xf, yf]`.

---

## 3. Blend Modes & Object Transparency (`transparency.set`)
- **Command ID**: `transparency.set`
- **Source Reference**: `tools/vectorcraft/crates/engine/src/cmd/paint.rs:857`, `tools/vectorcraft/crates/color/src/blend.rs:6`
- **Param Schema**:
  ```json
  {
    "id": "<target_node_id>",
    "ids": ["<target_node_id>"],
    "opacity": 0..100,
    "blend": "normal" | "darken" | "multiply" | "colorBurn" | "lighten" | "screen" | "colorDodge" | "overlay" | "softLight" | "hardLight" | "difference" | "exclusion" | "hue" | "saturation" | "color" | "luminosity",
    "isolate": false,
    "knockout": "on" | "off" | "neutral"
  }
  ```
- **Key Facts**:
  - `blend` string is parsed case- and space-insensitively (`BlendMode::parse`).
  - Supports all 16 standard PDF/Illustrator blend modes (including `screen`, `multiply`, `overlay`, `softLight`).
  - If `id` / `ids` is omitted, targets the current selection (the last created node).

---

## 4. Document Raster Effects Settings (`document.rasterEffectsSettings`)
- **Command ID**: `document.rasterEffectsSettings`
- **Source Reference**: `tools/vectorcraft/crates/engine/src/cmd/rasterfx.rs:36`
- **Param Schema**:
  ```json
  {
    "resolution": 300,
    "colorModel": "rgb",
    "background": "transparent",
    "antiAlias": true,
    "clippingMask": false,
    "addAround": 0.0
  }
  ```
- **Key Facts**:
  - `resolution`: Accepts numeric ppi (1 to 2400) or strings (`"screen"` = 72, `"medium"` = 150, `"high"` = 300).
  - Used for all live raster effects (drop shadows, blurs, glows, feathers) when exported to PDF or raster formats.
  - Setting `resolution: 300` guarantees print-ready raster effect rendering at 300 DPI.

---

## 5. Live Effects (`effect.apply` vs `appearance.addEffect`)
- **Command ID**: `effect.apply` (aliased as `appearance.addEffect`)
- **Source Reference**: `tools/vectorcraft/crates/effects/src/catalog.rs`, `tools/vectorcraft/crates/engine/src/cmd/effectcmd.rs`
- **Param Schema**:
  ```json
  {
    "effect": "<effect_id>",
    "params": { ... },
    "id": "<target_node_id>",
    "ids": ["<target_node_id>"]
  }
  ```
- **Key Effects**:
  - **Drop Shadow** (`stylize.dropShadow`):
    `params: {"mode": "multiply", "opacity": 75.0, "x": 0.0, "y": 8.0, "blur": 10.0, "color": "#000000", "shade": "color"}`
  - **Feather** (`stylize.feather`):
    `params: {"radius": 5.0}`
  - **Gaussian Blur** (`blur.gaussian`):
    `params: {"radius": 5.0}`
  - **Outer Glow** (`stylize.outerGlow`):
    `params: {"mode": "screen", "opacity": 75.0, "blur": 8.0, "color": "#00F5D4"}`

---

## 6. Text Manipulation & Typography
- **Source Reference**: `tools/vectorcraft/crates/engine/src/cmd/typecmd.rs`
- **`text.create`**:
  `params: {x, y, text, size?, font?, style?, color?, justify?, area?: {width, height, fit?: "none"|"autoHeight"|"shrinkText"}}`
  `result: {id: <node_id>, bounds: {x, y, width, height}, overflow?: [<id>]}`
- **`text.setStyle`**:
  `params: {id?, ids?, font?, style?, size?, leading?: pt|"auto", tracking?: 1/1000 em, justify?, fill?}`
  `result: {ids: [...], overflow?: [...]}`
- **`text.fitHeadline`**:
  `params: {id?, ids?}`
  `result: {tracking: <float>}`
  Tracks the first line of area type so it exactly fills the frame width (Swiss headline lockup).
- **`text.createInPath`**:
  `params: {path: <path_id>, mode: "area"|"onPath", text?, at?: [x, y], size?, font?, style?, color?, fit?, justify?}`
  `result: {id: <node_id>, bounds: {x, y, width, height}, overflow?: [<id>]}`
  Turns a previously created vector path into an on-path or area baseline. The path's stroke/fill paint is dropped.

---

## 7. Grain & Texture Effects
- **Texture Grain** (`texture.grain`):
  `params: {"intensity": 40.0, "contrast": 50.0, "grainType": "regular"}`
  (Available grain types: `"regular"`, `"soft"`, `"sprinkles"`, `"clumped"`, `"contrasty"`, `"enlarged"`, `"stippled"`, `"horizontal"`, `"vertical"`, `"speckle"`)
- **Film Grain** (`artistic.filmGrain`):
  `params: {"grain": 4.0, "highlightArea": 0.0, "intensity": 10.0}`

---

## 8. Shared Fonts Resolution
- **Source Reference**: `tools/vectorcraft/apps/vectorcraft/src/prefs_dir.rs:22`, `tools/vectorcraft/apps/vectorcraft/src/profile.rs:27`
- **Resolution Algorithm**:
  1. If `VECTORCRAFT_CONFIG_DIR` environment variable is set: `<VECTORCRAFT_CONFIG_DIR>/Fonts`
  2. If portable marker (`portable.txt` or `VectorCraft.portable`) exists in the directory containing the VectorCraft executable:
     `<executable_dir>/VectorCraftData/Fonts`
  3. Platform convention:
     - Windows: `%APPDATA%/VectorCraft/Fonts`
     - macOS: `~/Library/Application Support/VectorCraft/Fonts`
     - Linux: `$XDG_CONFIG_HOME/vectorcraft/Fonts` or `~/.config/vectorcraft/Fonts`
- **Behavior**: VectorCraft CLI and GUI dynamically load and scan all TrueType/OpenType files found in this shared folder.
