# VectorCraft MCP Server Tool Matrix & DSL Inventory

**Date**: 2026-11-03  
**Status**: Verified Live on Windows Host with VectorCraft CLI v0.19.0

---

## 1. Tool Matrix & Actionable Geometry

The table below enumerates all VectorCraft MCP server authoring tools exposed over JSON-RPC 2.0 stdio, detailing their input schemas, live return payloads, and actionable geometry.

| Tool Name | Input Parameters | Return Payload | Actionable Geometry Returned? | Notes / Safety Rails |
| :--- | :--- | :--- | :--- | :--- |
| `create_doc` | `width: float`<br>`height: float` | `{"status": "ok", "doc_width": 1080.0, "doc_height": 1350.0, "session_file": "runs/.../session.vcs"}` | **YES**: `doc_width`, `doc_height` define canvas coordinate space. | Initializes fresh document buffer, resets manifest, saves initial `.vcs`. |
| `load_brief` | `path: str` | `{"status": "ok", "path": "briefs/...", "field_count": 15, "fields": [...]}` | **NO**: Locks copy strings into memory. | Validates project-root confinement. Whole-token verbatim validator uses locked copy. |
| `add_shape_rectangle` | `x, y, width, height: float`<br>`fill?: str`<br>`stroke?: str`<br>`stroke_width?: float`<br>`radius?: float` | `{"status": "ok", "rect": [x, y, w, h], "fill": "#070B19", "command_count": 5}` | **YES**: Returns exact bounding box `rect: [x, y, w, h]`. | Emits paint state *before* shape creation per VectorCraft paint ordering contract. |
| `add_text` | `text: str`<br>`x, y, size: float`<br>`font?: str`<br>`style?: str`<br>`color?: str`<br>`role?: str` | `{"status": "ok", "row_id": "headline_1", "bounds": {"x": 60.0, "y": 150.0, "width": 792.0, "height": 92.0}, "command_count": 8}` | **YES**: `bounds` with `{x, y, width, height}` derived from font metrics. | **Whole-token verbatim enforcement**: rejects non-brief text with `VerbatimValidationError`. |
| `place_image` | `path: str`<br>`rect?: [x, y, w, h]` | `{"status": "ok", "image_path": "...", "rect": [100, 300, 400, 400], "command_count": 6}` | **YES**: Returns destination placement rectangle `rect`. | Validates path is within project root; sets `hero_rect` if rect is provided. |
| `soft_scrim` | `x, y, width, height: float`<br>`stops?: list[tuple]`<br>`direction?: str` | `{"status": "ok", "scrim": {"x": x, "y": y, "width": w, "height": h, "direction": "to_bottom"}, "command_count": int}` | **YES**: Returns bounding box coordinates. | Linear gradient with per-stop alpha (`opacity`) so underlying art shows through without clipping. |
| `radial_light` | `cx, cy: float`<br>`rx?, ry?, radius?: float`<br>`color?: str`<br>`opacity?: float` | `{"status": "ok", "radial_light": {"cx": cx, "cy": cy, "radius": r, "color": "#00F5D4"}, "command_count": int}` | **YES**: Returns center coordinate and effective radius. | Screen-blended atmospheric glow or spotlight spill. |
| `measure` | *(None)* | `{"passed": bool, "failure_count": int, "failures": [...], "score": float, "v_band_coverage_pct": float}` | **YES**: Per-gate failure records detailing exact escaping/colliding coordinates and contrast ratios. | **Pure-math instant gate (<1ms)**: canvas bounds, row overlaps, hero overlap, dedupe, required content, v-band coverage, and composition-time contrast. |
| `render_preview` | `scale?: float (default 0.5)` | `{"status": "ok", "preview_path": "...", "scale": 0.25, "command_count": int, "execution_time_sec": 2.52}` | **YES**: Generates real raster preview PNG in session directory. | Calls VectorCraft CLI headlessly at specified scale factor. |
| `save_session` | `path?: str` | `{"status": "ok", "session_path": "...", "command_count": int}` | **YES**: Saves human-editable `.vcs` format with full manifest and command stream. | Defaults to `session.vcs` in session directory. |
| `load_session` | `path: str` | `{"status": "ok", "session_path": "...", "command_count": int, "doc_width": 1080.0, "doc_height": 1350.0}` | **YES**: Restores artboard dimensions and text manifest. | Re-instantiates renderer from any saved `.vcs` file. |
| `export` | `output_png: str`<br>`output_pdf?: str` | `{"status": "ok", "output_png": "...", "output_pdf": "...", "score": 10.0, "command_count": int, "execution_time_sec": 3.08}` | **YES**: Produces final high-resolution print PDF and 2x PNG deliverables. | **Honest Export Rail**: strictly blocked (`ExportBlockedError`) if `measure()` reports $\ge 1$ failing gates. |

---

## 2. VectorCraft DSL Inventory & Design Capabilities

VectorCraft CLI (v0.19.0) provides an expressive vector/raster rendering engine. Below is the inventory of what is natively available in the engine DSL versus what is currently exposed via MCP:

### A. Paint, Fills & Gradients
- **Solid Colors**: Hex strings (`#RGB`, `#RRGGBB`). Active paint applies on creation.
- **Linear Gradients (`paint.setFill`)**: Multi-stop linear vectors defined by `start: [x1, y1]` and `end: [x2, y2]` (or `angle`).
- **Radial Gradients**: Multi-stop radial vectors with `start: [cx, cy]`, `aspect: float`, `focal: [xf, yf]`.
- **Per-Stop Alpha**: Crucial capability — gradient stops accept `opacity: 0.0..1.0`, enabling feathering and non-destructive overlays.
- **Paint Ordering**: `paint.setFill` / `paint.setStroke` must be emitted **before** the shape command.

### B. Transparency & Blend Modes (`transparency.set`)
- **16 Blend Modes Supported**: `normal`, `darken`, `multiply`, `colorBurn`, `lighten`, `screen`, `colorDodge`, `overlay`, `softLight`, `hardLight`, `difference`, `exclusion`, `hue`, `saturation`, `color`, `luminosity`.
- **Opacity**: 0 to 100% per-node transparency.
- **Isolation & Knockout**: Native PDF transparency group controls.

### C. Live Raster Effects (`effect.apply` / `appearance.addEffect`)
- **Drop Shadow (`stylize.dropShadow`)**: Configurable `mode`, `opacity`, `x`, `y`, `blur`, `color`.
- **Outer Glow (`stylize.outerGlow`)**: Screen/dodge blend outer glow with radius and color.
- **Feather (`stylize.feather`)**: Softens hard vector and image boundaries via Gaussian alpha roll-off.
- **Gaussian Blur (`blur.gaussian`)**: Multi-scale blur for background softening or depth-of-field simulation.
- **Grain & Texture (`texture.grain`, `artistic.filmGrain`)**: 10 distinct grain styles (`regular`, `soft`, `sprinkles`, `contrasty`, `stippled`, etc.) at 300 DPI print resolution.

### D. Advanced Typography
- **Native Font Loading**: TrueType / OpenType font scanning from `VectorCraftData/Fonts`.
- **Area Text**: Bounding-box wrapping with `fit: "autoHeight"` or `fit: "shrinkText"`.
- **Headline Fitting (`text.fitHeadline`)**: Swiss headline lockup where tracking auto-expands to fill the frame width.
- **Kerning & Tracking**: 1/1000 em tracking, custom leading, optical alignment.

---

## 3. What Was Missing for "Genuinely Designed" Posters

1. **Direct Blend & Effect Controls in MCP**:
   While VectorCraft has `transparency.set` and `effect.apply`, MCP only had `soft_scrim` and `radial_light`. Exposing `set_transparency` and `add_effect` allows the designer to apply neon glows, soft shadows, and screen blends directly to hero cutouts, color blocks, and headline layers.
2. **Hero Asset Integration & Feathering**:
   Placing raw rectangular photos (like `layer3_hero.png` in `runs/noir_beats_v8`) results in harsh black boxes. Applying alpha feathering (`stylize.feather`), drop shadow, or screen blending turns a pasted box into an integrated stage element.
3. **Shape Geometry (Ellipses, Lines & Polygons)**:
   Exposing `add_shape_ellipse` and `add_path` enables badge containers, ticket stubs, diagonal energy cuts, and neon borders.
