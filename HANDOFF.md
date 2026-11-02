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
- Canvas: Default 1080×1920 (9:16 story) or format-driven (4:5, 1:1, A3, A4) rendered at scale 2.0 → gate dynamically requires exact 2x canvas dimensions (e.g. 2160×3840 for story).
- Fonts used: Display typography standardized on school voice (**Montserrat Bold** for KCT/KCLAS/KI/KIA, **Barlow Bold** for KCTBS, **Noto Sans Tamil Bold** for Tamil, **Inter Black 900** / `Bahnschrift` fallback). Structural/body fonts: `Inter`, `Source Sans 3`, `Segoe UI`, `JetBrains Mono`. Note: Offline TTFs (`Montserrat-Bold.ttf`, `Barlow-Bold.ttf`, `NotoSansTamil-Bold.ttf`) were obtained offline and installed into `tools/vectorcraft_bin/vectorcraft-0.19.0-windows-x64-portable/VectorCraftData/Fonts` (with copies in `assets/fonts/`); only Bold weights exist offline (display roles; body text remains Inter / Source Sans 3).

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
   - **Bug 4 (Horizontal seam artifacts & geometry overshoot)**: Prior fix of 0.0 terminal stop values was necessary but insufficient due to VectorCraft's raster effects flattening leaving a 1-pixel quantization edge when shape boundaries lie within the visible canvas (luminance delta >= 23.0). Resolved by extending scrim shape geometry past canvas edges by `fade_overshoot = 0.03 * canvas_shorter_side` (`-fade_overshoot` to `dim + fade_overshoot` on all 4 sides), ensuring only the gradient fade is visible on canvas and eliminating all rectangle boundary artifacts (luminance delta dropped to <= 1.00 across all archetypes, well below the 6.0 gate).
   - **Bug 5 (grid_3col vertical dead zone & microcopy boundary)**: Mid-canvas vertically balanced with enlarged hero ($35\%$ canvas) and radial light centered in Col 2, tracks/schedule in Col 1, narrative in Col 2, prizes/CTA in Col 3, and dual-line monospace footer. Fabricated copy (`CIRCUIT ELIGIBILITY:` / `ALL COLLEGES & UNIVERSITIES`) completely removed; module-level `MICROCOPY_ALLOWLIST` introduced for structural microcopy, ensuring 100% of rendered text derives strictly from `{MICROCOPY_ALLOWLIST ∪ brief}`.
   - **Bug 6 (z_pattern diagonal headline restoration)**: Restored two-line diagonal stagger (line 1 flush left, line 2 offset right by `width * 0.16` and down by `headline_size * 0.55`) with balanced word-boundary splitting, width clamping, and guaranteed collision clearance against top band elements and the mid-canvas hero rect.
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
  - Shared fonts: Programmatically resolved at `<exe_dir>/VectorCraftData/Fonts` (portable) or platform prefs without hardcoded user paths. Available TTFs audited at runtime: Inter, JetBrainsMono, SourceSans3, SourceSerif4. Note: Outfit font is NOT installed offline; display weight standardized on Inter Black 900 (or Bahnschrift fallback).

## 6. Task Status & Today's Progress (2026-11-01)

### Completed
- **Phase A & B**: Paint-ordering foundation bug fixed (`select.none` + pre-create paint emit) & Rich VectorCraft DSL (`soft_scrim`, `radial_light`, `orbital_text`, `add_effect`, `fit_headline`).
- **Phase C**: Archetype-native composer (`poster_agent/renderer/composer.py`) dispatching 4 archetypes (`focal_point`, `z_pattern`, `split`, `grid_3col`).
- **Phase C Fix-Up**: Canvas bounds protection, row collision prevention, headline height tracking, vertical rebalancing.
- **Phase C Repair**:
  - P1: Microcopy allowlist boundary (`MICROCOPY_ALLOWLIST`) and complete elimination of fabricated copy.
  - P2: Seam overshoot geometry past canvas edges (`fade_overshoot = 0.03 * canvas_shorter_side`), dropping max luminance jump from $23.36\text{--}30.11 \rightarrow 1.00$.
  - P3: Restored `z_pattern` two-line diagonal headline stagger with word-boundary splitting and hero collision clamping.
  - Verification: 2x PNG + vector PDF renders for all 4 archetypes in `runs/archetype_check_v3/` with max seam delta 1.00 and zero fabricated strings.
- **Phase C2 (Two-Call Planner & Slot Execution)**:
  - Two-call planner architecture: Stage 2a Concept Planning (`CONCEPT_SCHEMA`) -> Stage 3 Hero-First Generation -> Stage 3.5 Hero Measurement & Color Extraction -> Stage 4a Background Generation (conditioned on hero color + light plan) -> Stage 4b Background Measurement (12x15 calm/busy/salient grid) -> Stage 4.5 Layout Planning (`LAYOUT_SCHEMA` placing text into calm regions).
  - Schema enforcement via Gemini REST `responseSchema` + Python validators with exactly 1 bounded retry.
  - Honest failure policy: deleted silent canned-fallback block. Live mode halts cleanly (`PLANNING_HALT`), mock mode logs loud banner (`PLANNING_FALLBACK`) and provenance.
  - Provenance: `runs/{run_id}/plan.json` written before Stage 5 with full concept, layout, art metrics, allowlists, and repair attempt records.
  - Slot execution in `composer.py`: slots converted to pt, clamped to doctrine floors (headline >= canvas_h/11 (~122.7pt), body >= 1.8%, micro >= 1.4%, margin safe-box clamp), font & treatment validated, degenerate zones fall back to archetype default, all text content strictly brief-sourced.
  - **[AUDIT FIX 2026-11-02]** Headline floor corrected: the slot clamp actually used a hardcoded 72pt while `headline_floor = canvas_h/11` existed as dead code; clamp now uses the doctrine floor and floors are RE-APPLIED after fit-shrink (shrink floor was 13-14pt, which could silently undercut doctrine). Floor unit test now asserts the clamped VALUE (queued text size >= canvas_h/11), replacing log-string assertions. Mock pipeline confirmed to never consult Gemini (canned plan unconditional) — old "fallback in mock" test was vacuous and was replaced with `test_mock_pipeline_never_consults_planner_and_writes_plan` + new live halt tests `test_live_pipeline_halt_on_failed_concept_call` / `test_live_pipeline_halt_on_layout_failure_after_valid_concept` (generators stubbed; layout-halt path mirrors concept-halt path, code-audited). CLI-render-dependent mock tests skip honestly with reason on WSL path-interop. WSL audit: 80 passed / 12 CLI-gated failed (Windows renders), full suite green on Windows host.
  - Verification: 93 passing unit tests (`tests/test_planner_c2.py`), 4 forced archetype renders in `runs/archetype_check_v4/` (2160x2700 PNG + vector PDF), and live mode ComfyUI halt verified.
- **Housekeeping**: Root litter verified clean; offline font search completed; display weight standardized on Inter Black 900 in `HANDOFF.md` and `DESIGN.md`.
- **Phase C4 Commit 1 (Asset Strategy Resolver)**:
  - Resolver ladder implemented in `poster_agent/assets/resolver.py`: `supplied -> archive -> native -> generated`. Generation is now the last resort rather than mandatory pipeline spine.
  - Brief asset references parsed via `poster_agent/ingestion/extractor.py` without leaking into verbatim poster copy.
  - Stage 2b asset resolution gate integrated into `poster_agent/unified_pipeline.py`. Stages 3 & 4a conditionally run only if corresponding slots resolve to `generated`. Live run without ComfyUI completes when assets are supplied/archive/native.
  - Native background raster preview generated and measured in Stage 4b. Provenance logged per-slot in `plan.json`.
  - Full test suite: 102/102 tests passed (`tests/test_assets.py`). Committed as `78f0c6c`.
- **Phase C4 Commit 2 (House Style System)**:
  - Brand data per school (KCT, KCLAS, KCTBS, KI, KIA), format mappings (`story -> 1080x1920 (DEFAULT)`, `square -> 1080x1080`, `fourfive -> 1080x1350`, `A3 -> 842x1191pt`, `A4 -> 595x842pt`), genre taxonomy, and structural policies defined in `configs/house_style.yaml`.
  - House style resolver implemented in `poster_agent/house_style.py` (`load_house_style`, `resolve_canvas_dimensions`, `resolve_school`, `resolve_genre`). Default canvas when absent: 1080x1920 (9:16 story).
  - Fonts installed offline into VectorCraft Data directory: `Montserrat-Bold.ttf`, `Barlow-Bold.ttf`, `NotoSansTamil-Bold.ttf`. Runtime font auditing (`audit_fonts`) selects school display voice (Barlow for KCTBS, Montserrat for KCT/KCLAS/KI/KIA, Noto Sans Tamil for Tamil).
  - Dynamic canvas sizing end-to-end: Stage 2 concept contract, Stage 3.5 measurer, Stage 4a background generation, Stage 4b measurement, Stage 4.5 layout, Stage 5 VectorCraft render, and Stage 6 exact size gate dynamically derived from canvas (`target_2x = (canvas_w * 2, canvas_h * 2)`).
  - Structural rows implemented in `poster_agent/renderer/composer.py`: `emit_logo_row`, `emit_banner_tab_row`, `emit_pill_row`, `emit_footer_bar_row`, `emit_qr_row` (with deterministic QR code generation). Manifest records all structural items with `_structure_*` prefix. Genre policy enforces institutional allowance of pills/banners while preserving clean line on cultural editorial.
  - Full test suite: 111/111 tests passed (`tests/test_house_style.py`, `tests/test_composer.py`). Committed as `feat(house): house style...`.

- **Phase C4 Commit 3 (Doctrine Rebuild & Corpus Exemplar Injection)**:
  - Addendum Item 1 applied: `poster_agent/assets/resolver.py` resolves to `native` if `declared_source is None or declared_source != "generated"`, legacy comment removed, verified by unit test `test_concept_without_asset_plan_resolves_native_for_hero_and_bg`.
  - Addendum Item 2 applied: WSL skip guards added to all VectorCraft execution tests in `tests/test_house_style.py` and `tests/test_doctrine_c4.py`.
  - Addendum Item 3 applied: Normalized trailing newlines in `configs/house_style.yaml` and `poster_agent/house_style.py`.
  - Addendum Item 4 applied: Recorded offline font discovery / Bold-weight limitation in Section 1 and Section 6.
  - Section 1.5 added to `skills/poster-design-craft/SKILL.md` with verified corpus ground truth citations (`corpus: 172/205` for 9:16 story per the audit-adjusted rule, `corpus: 129/205` for white/light base, `corpus: 48/205` for QR code, `corpus: 44/205` for weak-point discipline). Updated Section 1 (genre-aware structural policy), Section 12 (9:16 story default), and Section 13 (quality rubric).
  - Exemplar picker `select_house_exemplars` and prompt formatter `format_exemplars_for_prompt` implemented in `poster_agent/house_style.py`.
  - Concept prompt builder `build_concept_prompt` implemented in `poster_agent/gemini_client.py` injecting up to 3 exemplars under strict ~500 token budget (~2000 chars).
  - Pipeline logs `HOUSE_EXEMPLARS: N` at Stage 1.5. Verified `HOUSE_EXEMPLARS: 3` on GDG recruitment brief and `HOUSE_EXEMPLARS: 0` on unknown genre brief.
  - Full test suite: 116/116 tests passing (`tests/test_doctrine_c4.py`, `tests/test_assets.py`, `tests/test_house_style.py`).
  - **[AUDIT ALIGN 2026-11-02]** Citation arithmetic corrected against the CSV recompute: with the rule
    `"1080x1920" in format` the story count is **172/205 (84%)** — the earlier 173 came from an OR-rule
    that also counted one mislabeled `~1080x2070` row; "166" matched no rule on the CSV. Secondary tiers
    recompute to **32/205 (16%)** (rule: 4:5/square/A3/A4 and non-1080x1920) — the earlier `39/205` was
    unverifiable. `SKILL.md` and `tests/test_doctrine_c4.py` now agree on both rules and counts.
  - **[AUDIT ALIGN]** An uncommitted worktree edit had silently rolled `house_style.py` back to
    Commit 2's first-match genre logic; the Commit 3 weighted-scoring version was restored from
    `20bfc15` after its own tests passed. Whether a deliberate revert is preferred must be argued
    with failing-test evidence, not silent file replacement.
  - **[AUDIT ALIGN — font provenance]** Montserrat-Barlow-NotoSansTamil Bold TTFs were copied from the
    VectorCraft portable bundle (`tools/vectorcraft_bin/.../VectorCraftData/Fonts/`) — sizes byte-identical
    to `assets/fonts/`. No network downloads. All three are OFL families; ship OFL attribution files with
    the bundle before any public distribution.
  - **[AUDIT ALIGN — test hygiene]** `tests/test_no_hardcoded_paths.py` reworked to `os.walk` with directory
    pruning (same invariants): 186s → ~1s under WSL. Minimal test policy added: `scripts/test.sh` /
    `scripts/test.ps1` — CORE suite (7 invariant files, ~10s) by default; FULL suite only when
    composer / pipeline / gates / render code changes.

- **Phase D Commit 1 (Composer Remediation & Six Defects Addressed)**:
  - **Defect D1 (Headline Clipped)**: `wrap_and_fit_row` wraps long headlines to $\le 2$ lines before shrinking toward doctrine floors. If still exceeding usable width at floor, scales down with a loud banner (`>>> [composer] LOUD BANNER: row 'title' ...`) to guarantee zero canvas clipping.
  - **Defect D2 (Subtitle/Venue/Date Clipped & QR Collision)**: QR reserve space calculated (`max_log_w = qr_px - margin_x - 30.0`). All bottom logistics rows constrained to `max_log_w`, preventing collision with the bottom-right QR code module.
  - **Defect D3 (Hero Occlusion)**: Physical hero bounding box reserved in Band 1 ($y = 660 \dots 980$). Header items bounded to finish above hero crown ($y \le 640$). `check_rect_intersection` audit reports `HERO_OCCLUSION: none`.
  - **Defect D4 (Closing Line Dedupe)**: Closing line rendered strictly once in the structural footer bar when allowed by genre; removed from body row emission.
  - **Defect D5 (~25% Dead Vertical Band)**: 5-band vertical rhythm system implemented (`compute_vband_coverage`). Content distributed across full 9:16 portrait canvas; audited at `V-BAND COVERAGE: 100%`.
  - **Defect D6 (Contrast Floors)**: WCAG 2.1 relative luminance checking implemented (`get_contrast_ratio`, `ensure_contrast_color`). Structural rows (footer bar, banner tabs, pills, barcodes) guarantee $\ge 4.5:1$ contrast against their fills; eyebrow text on light backgrounds uses deep navy `#0B2A5B` ($> 12:1$ contrast).
  - New test suite `tests/test_render_polish.py` created with 8 comprehensive unit & end-to-end render tests (100% passing).
  - Full pytest suite passing: 124 passed on Windows.
  - Yardstick proof render generated to `runs/render_polish_demo/` (2160x3840 2x PNG, vector PDF, `report.md`, and `plan.json` with 0 overflows).

- **Phase D Commit 2 (Deterministic QA Gates Wired + Honest Stage 7 Review)**:
  - **Stage 6 QA Gate Suite**: Deterministic gate runner `run_stage6_gates` wired directly into Stage 6 of `UnifiedPosterPipeline`. Evaluates all 6 gates in strict sequence:
    1. `text_bounds`: Guarantees no queued text row exceeds canvas safe margins (left, top, right, bottom with $\ge 4.5\%$ margin).
    2. `hero_overlap`: Resolves hero bounding box and asserts zero text/hero rect intersections.
    3. `structure_contrast`: Samples WCAG 2.1 relative luminance on raster image, enforcing $\ge 4.5:1$ contrast floor.
    4. `required_content`: Confirms all brief-supplied logistics (date, venue, CTA, QR) appear in the render manifest.
    5. `dedupe`: Flags any duplicate closing line or text across structural and body roles.
    6. `v_band_coverage`: Audits vertical rhythm across 5 bands, enforcing $\ge 70\%$ vertical band coverage.
  - **Audit Provenance in `plan.json`**: Every gate verdict, measured metrics, and failure targets recorded in `plan.json` under `gates: [...]` and `gate_failures: [...]`.
  - **Honest Stage 7 VLM Verdict**: Completely removed synthetic `overall_score = 9` fallback. When Gemini VLM critique is unavailable or errors (e.g. 429 rate limit), verdict reads `REVIEW_UNAVAILABLE` with score `N/A`. When VLM responds, score pass threshold is strictly restored to **8/10** (reverting `149cb3e` 7→8). Overclaiming "10/10" language eliminated from reports.
  - **Report Table**: `report.md` now features a dedicated `Stage 6 Deterministic Quality Gates Enforcement` markdown table showing gate names, verdicts (`PASS`/`FAIL`), measured metrics, and enforcement details.
  - **Tests**: `tests/test_gates_integrated.py` created with 9 passing tests covering planted failures (oversized row, hero-overlapping row, low-contrast pair, missing required content, duplicate closing, clustered rhythm), clean spec verification, honest `REVIEW_UNAVAILABLE` handling, and score 8 threshold enforcement.
  - **Corpus Protection**: `skills/poster-design-craft/SKILL.md` citations verified untouched.
  - Full test suite: **133 passed**, 3 warnings in 63.56s on Windows.

- **Phase D Commit 3 (Repair Executor + Editable VCS Sessions + Payload v2 & Refusal Gate)**:
  - **Ideogram Payload v2**: Canonical builder `poster_agent/generators/ideogram_v2.py` replaces all ad-hoc dictionary construction and double word-purge logic. Guarantees 1–2 concrete bounding-box elements, flat `style_description` string with inline hexes, plain descriptive prose without negative incantations ("NO TEXT", "NO WORDS"), and aspect ratio synchronization matching ComfyUI `ResolutionSelector` node 37 (`9:16 (Portrait Widescreen)` for 1080×1920).
  - **Refusal-Free Gate (`check_refusal_free`)**: Scans generated raster layers (Layer 0 background, Layer 3 hero) via OCR (if pytesseract available) and deterministic variance/edge heuristics to detect safety-filter blocked banners. Automatic 1-attempt sanitized retry before honest halt. Refusal artifacts never enter layout measurement or print packaging.
  - **Critique Prompt De-bias & Mock Branding**: Replaced hardcoded example score `"overall_score": 9` in Gemini Stage 7 prompt with neutral `<integer 1-10>` and strict rubric instructions. Mock Stage 7 reports are explicitly branded as `MOCK (canned fixture), score 9` across console logs and report deliverables.
  - **Archetype Diversity Check**: Enforced structural distinction between `focal_point` (centered optical radiance) and `z_pattern` (left-aligned diagonal flow with offset hero at $x=0.52$). Verified with $\ge 4$ divergent row coordinates in `tests/test_archetype_diversity.py`.
  - **Footer Baseline Margin Clearance**: Closing-line text baseline in `emit_footer_bar_row` strictly respects bottom safe margin ($y + h \le \text{canvas\_h} - \text{margin\_px}$).
  - **Repair Executor (`poster_agent/repair/executor.py`)**: Consumes Stage-6 deterministic QA gate failures and applies typed repair operations (`shrink_text`, `wrap_text`, `move_row`, `swap_contrast`, `drop_duplicate`) across $\le 2$ cycles. Every attempt logged to `plan.json` under `repairs: [{gate, op, applied, outcome}]`. If unrepairable in live mode, triggers honest `PIPELINE_HALT`.
  - **Editable VCS Session Files (`session_poster.vcs`)**: Full VectorCraft command streams serialized per run as `runs/{run_id}/session_poster.vcs`. Re-loadable via `VectorCraftRenderer.load_session(...)` with 100% manifest and raster output parity, providing a human-editable and re-renderable design artifact.
  - **Broken-Scenario Harness (`briefs/brief_broken_dense.txt`)**: Stress-test brief featuring a 44-character single-word headline and 9 dense positions, verified end-to-end in `tests/test_repair_broken_scenario.py`.
  - Full test suite: **144 passed**, 3 warnings on Windows.

- **Phase E (VectorCraft MCP Server + Interactive Designer Mode + Bakeoff)**:
  - **Halt-Receipt Contract Fix**: Updated `log_gate` in `poster_agent/unified_pipeline.py` to persist early checkpointed `plan.json` with `halt: True`, `halt_reason`, `halted_at`, and `halt_stage` before re-raising. Updated `test_planner_c2.py` contract.
  - **VectorCraft MCP Server (`poster_agent/mcp/vectorcraft_server.py`)**: Dependency-free JSON-RPC 2.0 stdio server providing 12 authoring tools: `create_doc`, `load_brief`, `add_shape_rectangle` (background/card vector shapes), `add_text` (with strict whole-token and line-boundary verbatim copy validation against loaded brief), `place_image` (with platform-neutral project-root path security enforcement), `soft_scrim`, `radial_light`, `measure` (instant `<1ms` pure-math evaluation of 7 QA gates including composition-time contrast floor), `render_preview` (fast CLI raster preview), `save_session` / `load_session` (.vcs session round-trips), and `export` (honest blocked export refusing to render if any QA gates fail).
  - **Composition-Time Contrast Floor**: `measure()` tracks each text row's local background (last rect/gradient fill covering its bounds from the command buffer) and verifies WCAG 2.1 relative luminance contrast ($\ge 4.5:1$ for body, $\ge 3.0:1$ for display) via pure math. White-on-white text rows are strictly flagged and export remains blocked until resolved.
  - **OpenCode & README Documentation**: Created `docs/mcp_opencode.json.example` ready for OpenCode integration; added "Interactive Designer Session" and "Anti-Thrash Interaction Policy" to `README.md`.
  - **Test Suite (`tests/test_mcp_server.py`)**: 11 comprehensive tests verifying tool schemas, whole-token verbatim copy validation, platform-neutral security checks, white-on-white contrast floor rejection and export blocking, coordinate-math measurement, and JSON-RPC protocol framing.
  - **Pilot Bakeoff (`docs/interactive_bakeoff.md`)**: Executed automated bakeoff (`scripts/mcp_pilot_client.py`) on `briefs/brief_c4_demo.txt`. Batch mode delivered in 2.31s (0 gate failures); Interactive MCP designer completed 30 tool calls in 3.39s, painting a full-canvas `#070B19` background fill, aligning atmospheric scrims without slicing text, measuring pure-math gates in 0.4ms, iteratively wrapping headlines to resolve margin escapes, and achieving 0 gate failures with 100% vertical band coverage. Master renders, session files, and telemetry logged in `runs/mcp_bakeoff_20261103/`.
  - Full test suite: **155 passed**, 3 warnings on Windows.

### Pending / Next Up
- **Phase E3 (Hybrid Routing Engine)**: Connect planner to route standard briefs ($\le 10$ fields) to Batch Pipeline and dense/complex briefs ($\ge 15$ fields) to Interactive MCP loop.
- **Live Acceptance Run**: Run live production pipeline with real Gemini API on `briefs/brief_c4_demo.txt` and `briefs/brief_robotics_demoday.txt`.

## 7. Superseded / Do Not Revive

- `poster_agent/pipeline.py` (old Playwright/HTML 8-stage harness) — DO NOT USE or resurrect without explicit user instructions.
- `poster_agent/renderer/{blended_layered_renderer,theme_renderer,renderer,print_engine}.py` — legacy Playwright/HTML/print paths superseded by native `VectorCraftRenderer`.
- `scripts/run_acceptance.py`, `scripts/run_kongu_nights_pipeline.py`, `scripts/run_kongu_pipeline_master.py`, `scripts/run_vortex_pipeline_master.py`, root `run_*_monitored_pipeline.py`, and root `test_*.png/json` clutter — one-offs superseded by `run_poster.py` (cleanup pending).
- End-of-turn repair loops (`TypedLayoutPatcher` / `repair.py`) — DO NOT loop font-size micro-tweaks on broken layouts.
- Groq planner path (`poster_agent/planner/planner.py`, verifier/templates) — superseded by Gemini; kept for reference.
