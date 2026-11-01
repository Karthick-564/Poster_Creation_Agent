# Agent Handoff — 2026-11-01

## 1. Active Architecture (CURRENT TRUTH ONLY)
- The one pipeline to use: `run_poster.py` → `poster_agent/unified_pipeline.py` (strict 8-stage gated execution)
- Components actually involved:
  - `poster_agent/ingestion/extractor.py`: Zero-drop regex and line provenance parser
  - `poster_agent/gemini_client.py`: Gemini client for JSON planning & multimodal vision critique
  - `poster_agent/generators/comfyui_client.py`: Client for local ComfyUI diffusion generation
  - `poster_agent/vision/art_measurer.py`: Computer vision alpha bounding box, halo detection, calm space analysis
  - `poster_agent/renderer/vectorcraft_renderer.py`: Native VectorCraft CLI bridge generating vector PDF and 2x PNG
- ComfyUI: endpoint `http://127.0.0.1:8188`, models used:
  - Layer 0: Ideogram 4.0 workflow (`ideogram_workflow_api.json`)
  - Layer 3: Qwen-Image 2.1 int8 native alpha cutout
- VectorCraft CLI: `tools/vectorcraft_bin/vectorcraft-0.19.0-windows-x64-portable/vectorcraft-cli.exe`

## 2. What Works (verified, how to run it)
- **Production CLI (Mock Mode - Offline / Fast Verification)**:
  ```powershell
  python run_poster.py --mock --brief "AI Summit 2026`nDate: Dec 5-7, 2026`nVenue: Apex Hall"
  ```
  Expected output:
  - Generates full 8-stage run under `runs/poster_run_{timestamp}/`
  - Outputs: `master_print.pdf`, `master_render_2x.png` (2160x2700 px), `layer0_bg.png`, `layer3_hero.png`, and markdown audit report
  - Score: 9/10 `READY_FOR_PRINT`
  - Zero external directories created; strictly adheres to `AGENTS.md` path policy

- **Production CLI (Live RTX 4090 Diffusion Pass)**:
  ```powershell
  python run_poster.py --brief-file briefs/brief_nova_ctf.txt
  ```
  Expected output:
  - Connects to ComfyUI at `http://127.0.0.1:8188`
  - Dual-pass diffusion: Ideogram 4.0 background + Qwen-Image 2.1 hero
  - Compiles vector PDF & 2x print raster via VectorCraft in `runs/poster_run_{timestamp}/`

- **Unit Test Suite**:
  ```powershell
  $env:PYTHONPATH="."; python -m pytest tests/ -v
  ```
  Expected output: 52 tests passing (including `tests/test_no_hardcoded_paths.py`).

## 3. Known Open Issues
- **Fill-ordering bug in `vectorcraft_renderer.py`**: When `add_shape_rectangle` is called with a fill, `paint.setFill` is currently emitted after `shape.create`, causing VectorCraft to ignore the paint operation on certain shape types unless reordered.
- **Deterministic `checks/` not wired into unified pipeline**: `unified_pipeline.py` currently relies on VectorCraft export status and Gemini VLM for quality gating, rather than calling the modular `checks/pixel_verifier.py` rules.
- **Stage 7 Gemini fallback fabricates a pass**: If the Gemini API returns 429/503 during Stage 7 visual critique, the pipeline falls back to a hardcoded passing dictionary (`score: 9`, `READY_FOR_PRINT`) instead of failing the gate or running deterministic OCR checks.
- **Layout hardcoded in `_assemble_vectorcraft`**: Text coordinates, fonts (Bahnschrift, Segoe UI), and layout structure are statically hardcoded in `unified_pipeline.py:_assemble_vectorcraft` rather than dynamically driven by Stage 2 Gemini spatial planning.
- **Title year split assumption**: `_assemble_vectorcraft` assumes a 4-digit year at the end of the title for lockup formatting; titles without years take an alternate static branch.

## 4. Decisions & Learnings (short list)
- Never write or copy files outside project root (enforced by `AGENTS.md` and `tests/test_no_hardcoded_paths.py`).
- Keep deliverables in `runs/{run_id}/` by default; copy to external `--artifact-dir` only when explicitly specified via CLI flag.
- Do not use HTML container cards (`.hud-panel`) or rounded button pills (`.cta-pill`) on posters; editorial posters require open typography sitting directly on atmospheric background scrims.
- In `gemini_client.py`, always downscale images to max 1024px before base64 encoding to prevent 429/503 API rate limits and connection timeouts.
- In `palette_policy.py`, always validate role color contrast against canvas luminance using WCAG $\ge 4.5:1$ calculation.

## 5. Superseded / Do Not Revive
- `poster_agent/pipeline.py` (old 8-stage Playwright harness) — DO NOT USE or resurrect without explicit user instructions.
- `poster_agent/renderer/blended_layered_renderer.py` and `theme_renderer.py` — legacy Playwright/HTML rendering paths superseded by native `VectorCraftRenderer`.
- `scripts/run_acceptance.py`, `scripts/run_kongu_nights_pipeline.py`, `scripts/run_kongu_pipeline_master.py`, `scripts/run_vortex_pipeline_master.py` — legacy one-off scripts superseded by `run_poster.py`.
- End-of-turn repair loops (`TypedLayoutPatcher` / `repair.py`) — DO NOT loop font size micro-tweaks on broken layouts.
