# Design Bakeoff: Batch Deterministic Baseline vs. MCP Designer Loop

**Date**: 2026-11-03  
**Status**: Acceptance Verification & Architectural Comparison  
**Brief**: `briefs/brief_noir_beats.txt` (NOIR BEATS 2026, 1080×1350, Neon-Noir EDM Night)  

---

## 1. Executive Summary

In Phase D, automated poster composition converged on a 100% deterministic template engine (`composer.compose_slots`). While this guaranteed physical compliance (margins, non-overlap, contrast), the resulting designs suffered from **"Word-Document Syndrome"**: a centered, monochrome, single-column text stack with an unfeathered harsh rectangular photo box.

In this phase, we rebalanced the architecture:
- **Hard invariants remain inviolable**: safe margins ($\ge 4.5\%$), zero collisions, WCAG contrast floors ($\ge 4.5:1$), and 100% whole-token verbatim copy.
- **Compositional authority is transferred to the VectorCraft MCP Server**: asymmetric editorial grids, dynamic type scales, color-coded hierarchy, non-destructive gradient lighting, edge feathering, and tangible ticket CTA containers are executed through MCP authoring tools under live `measure()` gate feedback.

---

## 2. Quantitative & Qualitative Comparison Matrix

| Evaluation Dimension | Incumbent Baseline (`runs/noir_beats_v8`) | MCP Designer Champion (`runs/noir_beats_designed_v3`) | Delta / Improvement |
| :--- | :--- | :--- | :--- |
| **Generation Engine** | Deterministic `compose_slots` batch script | Interactive VectorCraft MCP Server Loop | Agentic authoring under live gate feedback |
| **Physical QA Gates (`measure`)** | **PASS** (6/6 gates, 0 failures) | **PASS** (6/6 gates, 0 failures) | Parity on hard physics invariants |
| **Pre-Composition OCR Gate** | None (Risk of baked diffusion gibberish) | **PASS** (`check_background_ocr`, 0 unmapped tokens) | Guaranteed clean background & hero |
| **Composite Design Score** | **7.8 / 10.0** | **9.2 / 10.0** | **+1.4 pts (+17.9%)** |
| **Typographic Hierarchy Ratio** | 6.49:1 ($122.7\text{pt} / 18.9\text{pt}$) | 5.38:1 ($86.0\text{pt} / 16.0\text{pt}$) | Authoritative display scale with clean margins |
| **Asymmetric Balance Index** | **0.000** (COM X: 540.0px, fully centered) | **0.277** (COM X: 390.5px, dynamic offset) | **Overcomes centered Word-doc syndrome** |
| **Palette Representation** | **40.0%** (2/5 colors; essentially white on black) | **60.0%** (3/5 colors + radial lighting) | Integrated Electric Cyan, Hot Magenta & Navy |
| **Hero Layer Integration** | Harsh rectangular cut out, no edge feathering | Screen blend + 22px alpha edge feathering | Photo dissolves naturally into stage lighting |
| **CTA Presentation** | Bare text line (`Passes at kct-...`) | Styled ticket stub card with notch badge | Tactile, actionable container |
| **VCS Session Editable?** | Rigid slot batch commands | Clean human-editable `.vcs` command stream | Full designer re-usability |

---

## 3. Visual Review & Analysis

### A. The Baseline Incumbent (`runs/noir_beats_v8/master_render_2x.png`)
- **Visual Stance**: Monotone, rigid, static.
- **Flaws**:
  1. Every single element is centered along the $x = 540\text{px}$ axis.
  2. Complete palette starvation: despite a rich neon brief (`#00F5D4`, `#7B2FFF`, `#FF3D68`), all text is rendered in monotone white/off-white.
  3. The hero crowd asset is placed as a rigid, unfeathered black box in the middle of the poster.

### B. The MCP Designer Output (`runs/noir_beats_designed_v3/master_render_2x.png`)
- **Visual Stance**: Dynamic, atmospheric, high-voltage neon-noir.
- **Strengths**:
  1. **Asymmetric Editorial Stance**: Left-anchored typography with dynamic horizontal counter-balance.
  2. **Vibrant Color Coding**: Eyebrow, rules, and events in electric cyan (`#00F5D4`); date and prize pool in punchy hot magenta (`#FF3D68`); headline in clean display white (`#F0F6FC`).
  3. **Atmospheric Lighting**: Non-destructive radial lighting (`#7B2FFF` violet and `#00F5D4` cyan glows) adds stage depth behind the headline.
  4. **Seamless Hero Transition**: Alpha feathering softens the concert crowd boundary, dissolving the photo into ambient volumetric light.
  5. **Ticket Container**: The admission call-to-action is enclosed in a rounded ticket pass container with an electric cyan `PASSES` badge notch.

---

## 4. Architectural Verification

1. **Safety & Confinement**: The MCP designer strictly confined all reads and writes within the project root. Zero files created outside `runs/{run_id}/`.
2. **Deterministic Physics Guarantee**: The MCP `export()` tool remains strictly blocked (`ExportBlockedError`) unless `measure()` reports 0 failures. The champion poster achieved a genuine $10/10$ physics verdict.
3. **Whole-Token Verbatim Integrity**: All 10 text elements were validated against `briefs/brief_noir_beats.txt` with zero mutations or hallucinated copy.

---

## 5. Artifact References
- Challenger Master 2x Render: `runs/noir_beats_designed_v3/master_render_2x.png`
- Challenger Master Print PDF: `runs/noir_beats_designed_v3/master_print.pdf`
- Challenger Telemetry Log: `runs/noir_beats_designed_v3/designer_log.jsonl`
- Challenger Design Review: `runs/noir_beats_designed_v3/design_review.md`
- Incumbent Baseline Render: `runs/noir_beats_v8/master_render_2x.png`
