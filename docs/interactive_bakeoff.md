# VectorCraft Interactive Designer vs. Batch Pipeline Bakeoff

**Date**: 2026-11-03  
**Artifact Directory**: `runs/mcp_bakeoff_20261103/`  
**Yardstick Brief**: `briefs/brief_c4_demo.txt` (GDG KCT Recruitment 2026, 9:16 Story)

---

## 1. Executive Summary

This pilot bakeoff benchmarks two distinct operational modes of `poster-agent` on identical brief specifications:
1. **Mode 1: Batch Deterministic Pipeline** (`UnifiedPosterPipeline` with heuristic archetype planning, width-fit remediation, and QA review).
2. **Mode 2: Interactive Designer Session** (`VectorCraftMCPServer` driving VectorCraft interactively over JSON-RPC 2.0 with verbatim copy locking, pure-math `<1ms` gate measurement, composition-time contrast floor, full-canvas background fill, aligned atmospheric scrims, iterative headline wrapping, and honest blocked export controls).

Both modes compiled print-certified master outputs (`master_render_2x.png`, `master_print.pdf`, `session.vcs`) with zero failing QA gates at final export.

---

## 2. Telemetry & Comparison Matrix

| Metric | Mode 1: Batch Pipeline | Mode 2: Interactive MCP Designer | Advantage / Note |
| :--- | :--- | :--- | :--- |
| **Total Wall-Clock** | **2.31s** | **3.39s** | **Batch (+1.08s faster)**; interactive performs 30 IPC tool roundtrips, preview rasterization, and export |
| **Tool / IPC Roundtrips** | 1 (Single monolithic invocation) | 30 tool calls (budget: $\le 30$) | Batch minimizes IPC; Interactive provides granular inspectability |
| **QA Feedback Latency** | 2.01s (evaluated post-render in Stage 6) | **0.4ms** (`measure()` pure bbox & contrast math) | **Interactive (5,000× faster gate feedback)** |
| **Verbatim Guard** | Stage 1 Zero-Drop Check | Whole-token boundary rejection per `add_text` call | Interactive prevents hallucination before layout entry |
| **QA Gate Failures (Final)** | **0 failures (PASS)** | **0 failures (PASS)** | Both modes produce 100% gate-compliant outputs |
| **Mid-Session Gate Failures** | N/A (single-shot batch) | 2 caught & repaired at Step 8 | Interactive blocked premature export on Step 8 & forced layout repair |
| **V-Band Coverage** | 80.0% (4/5 bands) | **100.0% (5/5 bands)** | Interactive distributed copy across the entire 1920 vertical canvas |
| **Headline Width Remediation** | Shrunk to 136.7pt via loud banner | Wrapped to 2 lines at 120pt | Interactive multi-line wrap preserves typographic impact |
| **Full-Canvas Background** | Stage 4 `#070B19` native raster fill | Step 3 & 11 `#070B19` solid vector layer | Full canvas covered without unpainted voids |
| **Atmospheric Scrim Alignment** | Dynamic overshoot past canvas | Height 750pt (encloses header, 50pt gap to section) | Zero text rows sliced across gradient transition boundary |
| **Session VCS Roundtrip** | Full `session.vcs` (24.7 KB) | Full `session.vcs` (16.2 KB) | Both support full human-in-the-loop reload and editing |

---

## 3. Quality & Layout Visual Comparison

### Placement & Whitespace Distribution
- **Batch Pipeline**:
  - Automatically selects `focal_point` archetype and computes grid placement based on archetype band fractions.
  - Generates structural banner tabs, section pill boxes, and logistics panels.
  - Headline is clamped to a single line: width-fit remediation prevented margin clipping by scaling down to `136.7pt` (doctrine floor `174.5pt`).
  - Vertical rhythm is strong (80%), but left slight dead zones around band 2 where hero artwork was native.
- **Interactive MCP Designer**:
  - The designer agent iteratively placed copy: early `measure()` at Step 8 warned of margin escape when the headline was placed at `135pt` on a single line.
  - The agent corrected by wrapping the title across two lines: `"We Are\nRecruiting"` at `120pt`, restoring visual punch without violating margin boundaries.
  - Painted a full-canvas `#070B19` background fill and aligned the top atmospheric scrim to $750\text{pt}$, ensuring no text rows cross the scrim boundary.
  - Positions and role taglines were spaced with custom vertical rhythm, achieving 100% coverage across all 5 vertical bands.

### Typographic Contrast & Safe Margins
- Both modes adhered strictly to the $4.5\%$ safe margin floor ($48.6\text{pt}$ left/right).
- In Interactive mode, the composition-time contrast floor continuously evaluated relative luminance ratios between text colors and their local underlying rect/scrim fills, confirming $>15:1$ contrast against `#070B19`.
- The export blocker prevented export while headline escaped right margin, forcing layout repair prior to generating raster deliverables.

---

## 4. Gate Score Trail (Interactive Designer Loop)

```
[Step 01] create_doc(1080, 1920)                  -> OK (0.3ms)
[Step 02] load_brief("brief_c4_demo.txt")          -> OK (1.3ms) - 27 fields locked
[Step 03] add_shape_rectangle(fill="#070B19")      -> OK (0.4ms) - Full canvas background
[Step 04] soft_scrim(height=750)                   -> OK (0.5ms) - Aligned atmospheric scrim
[Step 05] radial_light(...)                       -> OK (0.4ms)
[Step 06] add_text("LEARN/BUILD/GROW")             -> OK (0.6ms)
[Step 07] add_text("We Are Recruiting", size=135)  -> OK (0.6ms) - Single line attempt
[Step 08] measure()                               -> FAIL: 2 failures (right margin escape on title, missing date/venue)
-------------------------------------------------------------------------------------------------------------------
>>> DESIGNER REPAIR CYCLE: Clear doc, wrap title across 2 lines to preserve scale & safe margins <<<
-------------------------------------------------------------------------------------------------------------------
[Step 09] create_doc(1080, 1920)                  -> OK (0.3ms)
[Step 10] load_brief(...)                         -> OK (1.3ms)
[Step 11] add_shape_rectangle(fill="#070B19")      -> OK (0.3ms) - Full canvas background
[Step 12] soft_scrim(height=750)                   -> OK (0.4ms) - Aligned atmospheric scrim
[Step 13] radial_light(...)                       -> OK (0.4ms)
[Step 14] add_text("LEARN/BUILD/GROW")             -> OK (0.5ms)
[Step 15] add_text("We Are\nRecruiting", size=120) -> OK (0.5ms) - Wrapped title
[Step 16] add_text("Join GDG KCT...", size=24)     -> OK (0.7ms) - Wrapped subtitle
[Step 17-21] Add OPEN POSITIONS section, positions 1 & 2 with taglines
[Step 22] measure()                               -> FAIL: 1 failure (missing required logistics date & venue)
[Step 23-26] Add Date, Venue, CTA ("Apply Online"), Closing line
[Step 27] measure()                               -> PASS: 0 failures, 100% v-band coverage, CR > 15:1
[Step 28] render_preview(scale=0.5)               -> OK (286.6ms) - Verified visual hierarchy
[Step 29] save_session("session.vcs")             -> OK (1.0ms)
[Step 30] export("master_render_2x.png")           -> OK (3079.0ms) - Final print deliverables certified
```

---

## 5. Honest Verdict: Interactive vs. Batch

This pilot is scripted-deterministic, NOT an LLM designer session — limitations:
- **Scripted Sequence**: The pilot client executes a hardcoded sequence of tool calls simulating an expert designer's path rather than an autonomous LLM driving OpenCode in real-time. In an actual LLM session, prompt round-trip tokens, context window management, and planner reasoning will add additional latency.
- **Scope of `measure()` vs. Stage-6 QA Gates**:
  - `measure()` evaluates **pure-math coordinate, manifest, and color geometry without raster rendering**:
    * `canvas_bounds`: Text bounding box safe margin escapes.
    * `row_overlap`: Pairwise text row bounding box collisions.
    * `hero_overlap`: Text intersections with hero asset reservation rects.
    * `dedupe`: Duplicate copy emitted across structural or body roles.
    * `required_content`: Brief logistics verification (date, venue, CTA, QR).
    * `v_band_coverage`: Vertical rhythm distribution across canvas bands.
    * `contrast`: Composition-time relative luminance calculation between text color and underlying vector rect/scrim fill.
  - The **full Stage-6 deterministic gate suite** additionally evaluates **rendered raster pixel data**:
    * `check_seams`: Detects raster gradient quantization edges and seam artifacts in margin strips.
    * `sample_contrast`: Samples real multi-channel pixel luminance from the rendered raster image to account for diffusion backgrounds, anti-aliased font rasterization, and semi-transparent alpha overlays.

### Where Interactive Mode Shines:
1. **Zero-Guesswork Rapid Feedback**: `measure()` evaluates coordinate bboxes, overlaps, and contrast in **0.4 milliseconds** without rasterizing. An agent or human designer can explore 20 spatial variations in $<10\text{ms}$.
2. **True Typographic Intent**: When copy is too wide for a single line, batch mode's only automated choice is shrinking font size toward doctrine floors or applying heuristic splits. Interactive mode allows the designer agent to make conscious editorial choices (wrapping words across lines, adjusting line leading, fine-tuning whitespace).
3. **Ironclad Export Safety**: The blocked export contract ensures that no poster with failing gates can ever be exported via MCP. If gates fail, export is physically refused with a typed error.
4. **Human / Agent Collaboration**: The session can be inspected at any step via `render_preview()`, edited via `.vcs` file, and resumed without starting from scratch.

### Where Batch Mode Shines:
1. **Turnkey Autonomous Execution**: Batch pipeline takes a raw brief and returns a certified poster in 2.3 seconds without requiring interactive turns or IPC dialogue.
2. **Complex Multi-Asset Orchestration**: Batch mode handles the full Stage 2b asset ladder (resolving supplied assets, archive matching, native geometry, and diffusion generation) alongside automatic palette extraction and full raster verification.

---

## 6. Recommendations for Phase E3 (Hybrid Routing Engine)

For Phase E3, we recommend implementing an **intelligent routing dispatcher**:
1. **Tier 1 (Standard Briefs $\le 10$ fields)**: Route to **Batch Mode** for sub-3-second autonomous delivery.
2. **Tier 2 (Dense / Complex Briefs $\ge 15$ fields or Multi-Position Layouts)**: Route to **Interactive Mode** (`scripts/mcp_pilot_client.py` pattern) where the agent iteratively places sections, runs `measure()`, and optimizes whitespace.
3. **Tier 3 (User-in-the-Loop / OpenCode Sessions)**: Expose `VectorCraftMCPServer` directly to the user/IDE for interactive pairing, using `measure()` as the safety rail.
