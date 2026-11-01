# Agent Handoff — 2026-11-01

> Read this file FIRST, then in order: `AGENTS.md` (policies), `DESIGN.md` (design system),
> `context.md` (KCT brand), `configs/default.yaml`, `skills/poster-design-craft/SKILL.md` (Stage 2 doctrine),
> `skills/poster-critique/SKILL.md` (Stage 7 critique).

## 1. Active Architecture (CURRENT TRUTH ONLY)

- **The one pipeline to use**: `run_poster.py` → `poster_agent/unified_pipeline.py` (strict 8-stage gated execution).
- Components actually involved:
  - `poster_agent/ingestion/extractor.py` — Zero-drop brief parser. **Required fields: `title`, `date`, `venue`** (Stage 1 halts if missing). Optional fields auto-extracted when present: `events`, `prize`, `cta`, `blurb`, `tagline`, `subtitle`, `organizer`, `time`, `venue_tamil` — layout renders those blocks conditionally.
  - `poster_agent/gemini_client.py` — Gemini JSON planning (Stage 2) + multimodal vision critique (Stage 7). Model fallback list inside file (`gemini-flash-latest` only — `gemini-3-flash-preview` was removed from the list because the API returned HTTP 404 for that model name; do not re-add it without verifying the endpoint). Requires `GEMINI_API_KEY` in `.env`. **Downscales critique images to ≤1024px before upload** (429/503 prevention — do not remove).
  - `poster_agent/generators/comfyui_client.py` — ComfyUI at `http://127.0.0.1:8188`. Layer 0 background via `ideogram_workflow_api.json` (node `98:24` = prompt, nodes `98:27`/`98:28` = 896×1120, node `158` = output). Layer 3 hero via inline Qwen-Image 2.1 workflow (`qwen_image_2.1_int8_convrot.safetensors`, `qwen3vl_8b_fp8_scaled` CLIP, `qwen_image_2.1_vae_bf16` VAE, 768×768, steps 20, cfg 4.5). **Seed is time-derived and NOT persisted — reproducibility gap.**
  - `poster_agent/vision/art_measurer.py` — Alpha bbox, center, halo score. ⚠️ Measured geometry is currently **logged but unused** by the layout (hero placed at fixed 540×540 rect).
  - `poster_agent/renderer/vectorcraft_renderer.py` — VectorCraft CLI bridge. CLI binary path: `tools/vectorcraft_bin/vectorcraft-0.19.0-windows-x64-portable/vectorcraft-cli.exe`. Batch JSON → `vectorcraft-cli run --commands <file> --export <png> --scale 2 --export <pdf>`. 60s subprocess timeout (tight for large exports).
- Prior planner used **Groq** (`GROQ_API_KEY` still in `.env`) — now legacy. Gemini is the live planner.
- Stage 2 injects poster-design-craft (was: ideogram-prompting + poster-graphic-design).
- Canvas: 1080×1350 (4:5) rendered at scale 2.0 → gate requires exactly **2160×2700** PNG.
- Fonts used: `Bahnschrift`, `Segoe UI`, `Nirmala UI` (Windows system fonts; Tamil venue block relies on Nirmala UI complex-script shaping — unverified inside VectorCraft).

## 2. Environment Prerequisites

- Python 3.13 (Windows), deps in use: `opencv-python`, `Pillow`, `numpy`, `python-dotenv`. **No requirements.txt yet — known gap.**
- `.env` needs `GEMINI_API_KEY` (planner + critique). `GROQ_API_KEY` legacy/unused.
- Local ComfyUI server must be running with the Qwen/Ideogram model files under `ComfyUI/models/`.
- ComfyUI/ is gitignored; tools/vectorcraft is a git submodule-style checkout (`m` in status is expected).

## 3. What Works (verified, how to run it)

- **LIVE production run** (requires ComfyUI running + `GEMINI_API_KEY`):
  ```powershell
  python run_poster.py --brief-file briefs/brief_nova_ctf.txt
  ```
  Expected: dual-pass diffusion (Ideogram bg + Qwen hero), VectorCraft compiles
  `runs/{run_id}/master_print.pdf` + `master_render_2x.png` (2160×2700), Gemini Stage 7 critique,
  report `runs/{run_id}/{title_slug}_master_pipeline_report.md`. Optional
  `--artifact-dir D:\some\folder` copies deliverables there; default copies nothing outside `runs/`.

- **Unit tests**:
  ```powershell
  $env:PYTHONPATH="."; python -m pytest tests/ -v
  ```
  Last known: 52 passing (includes `tests/test_no_hardcoded_paths.py` tripwire).

## 4. Mock Mode — explicit contract (dev/test only, NEVER production)

`--mock` is **strictly opt-in**. It is never triggered automatically: live mode with ComfyUI
offline **halts at Stage 3** with `PIPELINE HALTED` (by design — do not "soften" this into a
mock fallback). What `--mock` fakes:

- Stage 2: static hardcoded plan (ignores the brief's content entirely)
- Stage 3: PIL flat-gradient background + green-ellipse "hero" (these are the flat
  `layer0_bg.png` files seen in `runs/poster_run_*` — that is how you recognize a mock run)
- Stage 7: fabricated passing critique

Mock exists to exercise renderer/CLI/gates offline and is relied on by tests. A mock run's
PDF/PNG is a **pipeline smoke test, not a poster** — treat any mock output as disposable.

## 5. Known Open Issues (priority order)

1. **[FIXED] Fill-ordering bug in `vectorcraft_renderer.py`** — Resolved by emitting `select.none` followed by `paint.setFill` / `paint.setStroke` / `stroke.set` *before* the create command. Verified via regression test `tests/test_vectorcraft_paint_order.py::test_paint_ordering_two_rectangles`.
2. **Stage 7 fallback fabricates a pass** — Gemini 429/503 → hardcoded `overall_score: 9,
   READY_FOR_PRINT` defeats the "strict gate". Should either fail hard or run deterministic
   checks instead.
3. **`checks/` not wired into the unified pipeline** — `checks/pixel_verifier.py`, OCR, contrast
   exist (generation-1 code, tested) but Stages 6–7 don't call them. Stage 6 only checks pixel
   dimensions; the report then *claims* "Safe-Zone Margins >80px verified" and "OCR 100% verbatim"
   which were never measured. **Report wording must be synced to what a gate actually verified.**
4. **Stage 2 silent fallback plan** — Gemini rate-limit → hardcoded cyberpunk plan with only a
   console note. At minimum link/record in the run log that the plan was a fallback.
5. **[FIXED — composer.py, archetype-driven] Layout hardcoded in `_assemble_vectorcraft`** — Replaced with `poster_agent/renderer/composer.py`. Dynamically builds a `TypographicPlan` with relative canvas scaling and dispatches across 4 distinct archetypes (`focal_point`, `z_pattern`, `split`, `grid_3col`). Hardcoded event subfooter string removed; all typography originates from the brief.
6. **[FIXED — Phase C Fix-Up] Composer Placement & Rendering Defects Resolved**:
   - **Bug 1 (Canvas bounds escape & detection)**: `vectorcraft_renderer.py` monitors rendered text bounds and flags escapes outside safe margins in `manifest_item["overflow"]`. Column 3 text in `grid_3col` is bounded by `col_w` via `area_text(fit="shrinkText")`.
   - **Bug 2 (z_pattern row collisions)**: Top band horizontal collisions are detected ($w_{\text{org}} + w_{\text{date}} + \text{gap} > \text{usable\_w}$) and resolved by vertically stacking organizer mark and date badge; bottom band elements receive dedicated sequential non-overlapping vertical slots.
   - **Bug 3 (focal_point headline/tagline collision)**: Multi-line headline block height is computed dynamically via `estimate_headline_height()`; tagline is placed strictly below the headline frame, and hero top is placed strictly below the tagline.
   - **Bug 4 (Horizontal seam artifacts)**: Opaque rectangle in `split` eliminated; all scrims across all 4 archetypes enforce outer edge stops strictly terminating at opacity 0.0 (`stops[-1]["opacity"] == 0.0`).
   - **Bug 5 (grid_3col vertical dead zone)**: Mid-canvas vertically balanced with enlarged hero ($35\%$ canvas) and radial light centered in Col 2, tracks/schedule in Col 1, narrative in Col 2, prizes/CTA/eligibility in Col 3, and dual-line monospace footer.
6. **[FIXED for focal_point] ArtMeasurer output unused** — Stage 4 measured hero cutout geometry and aspect ratio now dynamically drive hero scaling and centering in the `focal_point` archetype (remaining archetypes to follow in future phases).
7. **[FIXED — composer.py compact layout] Static layout vs sparse briefs** — `TypographicPlan` only instantiates rows for fields present in the brief; sparse briefs (e.g. only `title/date/venue`) render compact, balanced layouts with zero blank gap placeholders.
8. **Seed not persisted** (reproducibility) — save ComfyUI seeds per run.
9. **Title year split assumption** — `_assemble_vectorcraft` assumes a trailing 4-digit year;
   titles without years take an alternate static branch (sizes differ).

## 6. Decisions & Learnings (short list)

- Never write/copy files outside the project root (enforced by `AGENTS.md` +
  `tests/test_no_hardcoded_paths.py`). Timeline: the Antigravity session originally wrote
  deliverables into its own `.gemini/antigravity/brain/{session-id}` cache dir — removed, with
  `--artifact-dir` as the only sanctioned external copy mechanism.
- Keep deliverables in `runs/{run_id}/` by default; copy to external `--artifact-dir` only when
  explicitly specified via CLI flag.
- Skills consolidated: `skills/poster-design-craft/SKILL.md` adopted as the single master design doctrine (folding Ideogram zero-text gate and Swiss design rules); superseded skills (`poster-design-studio`, `poster-graphic-design`, `ideogram-prompting`) removed.
- No HTML container cards / rounded button pills on posters; editorial typography sits directly
  on atmospheric scrims (per `DESIGN.md` + `skills/poster-design-craft`).
- Gemini critique images must be downscaled ≤1024px before base64 upload.
- Always Ideogram background at 896×1120 (4:5, multiples of 16), then Lanczos-resize to 1080×1350
  in Stage 4 (`layer0_feathered_bg.png`).
- VectorCraft `text.create` returns `bounds`/`overflow` in its result JSON — recorded per run in `text_manifest.json` and `VectorCraftResult.text_manifest`.
- Engine facts catalogue documented in full at `docs/vc_engine_facts.md`:
  - `paint.setFill`: Accepts per-stop `opacity` in `gradient.stops`, enabling smooth alpha scrims over images.
  - `transparency.set`: Supports all 16 PDF blend modes (`screen`, `multiply`, `overlay`, etc.) and object/layer opacity.
  - `document.rasterEffectsSettings`: Live pixel effects (drop shadow, blur) render at print resolution via `resolution: 300`.
  - `text.fitHeadline`: Natively tracks area text line to fill frame width.
  - Shared fonts: Programmatically resolved at `<exe_dir>/VectorCraftData/Fonts` (portable) or platform prefs without hardcoded user paths. Available TTFs audited at runtime: Inter, JetBrainsMono, SourceSans3, SourceSerif4. Note: Outfit font is NOT installed; composer degrades gracefully to Inter/Segoe UI/Arial.

## 7. Superseded / Do Not Revive

- `poster_agent/pipeline.py` (old Playwright/HTML 8-stage harness) — DO NOT USE or resurrect without explicit user instructions.
- `poster_agent/renderer/{blended_layered_renderer,theme_renderer,renderer,print_engine}.py` — legacy Playwright/HTML/print paths superseded by native `VectorCraftRenderer`.
- `scripts/run_acceptance.py`, `scripts/run_kongu_nights_pipeline.py`, `scripts/run_kongu_pipeline_master.py`, `scripts/run_vortex_pipeline_master.py`, root `run_*_monitored_pipeline.py`, and root `test_*.png/json` clutter — one-offs superseded by `run_poster.py` (cleanup pending).
- End-of-turn repair loops (`TypedLayoutPatcher` / `repair.py`) — DO NOT loop font-size micro-tweaks on broken layouts.
- Groq planner path (`poster_agent/planner/planner.py`, verifier/templates) — superseded by Gemini; kept for reference.
