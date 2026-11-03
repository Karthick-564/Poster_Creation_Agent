# v2 Poster Core

Additive, contract-first replacement path for the legacy `unified_pipeline.py`.
The v2 core is deliberately narrower than the old pipeline: it proves one KCT
vertical slice end-to-end before adding schools, formats or genres.

## What v2 owns

| Concern | Authority |
| --- | --- |
| Brand palette, typefaces, logo rules | `configs/brand_contracts.yaml` |
| Layout candidates and copy mapping | `poster_agent/v2/planner.py` |
| Background art | Ideogram 4.0 via `ComfyUIAssetBroker` |
| Transparent hero / cutout | Qwen-Image 2.1 via `ComfyUIAssetBroker` |
| Composition | `VectorCraftComposer` (live) or `MockRenderer` (offline) |
| Text, logo, QR, palette, alpha, OCR | `poster_agent/v2/gates.py` |
| Craft critique | `PosterReviewerV2` (optional, never overrides gates) |
| Stage routing | `Pipeline` |

The deterministic suite is the referee. Generative models propose art and
layouts; they cannot waive a gate.

## Stages and repair routes

```
ingest -> plan -> assets -> compose -> gates -> review
             ^        ^          ^                  |
             |        |          +------ compose ---+
             |        +----------------- assets ----+
             +-------------------------- plan ------+
```

* `plan` failures (bounds, overlap, logo clear-space, required copy, contrast)
  try the next layout candidate.
* `assets` failures (missing logo, opaque/void hero, palette drift) re-request
  assets for the same candidate (`max_asset_attempts`, default 2).
* `compose` failures (missing raster, wrong dimensions, OCR mismatch, renderer
  exception) re-render the same candidate (`max_compose_attempts`, default 2).
* `review` failures (VLM score below the brand threshold or a failed
  three-second test) try the next candidate. If every candidate fails review,
  the pipeline returns the best reviewed attempt with a failing audit trail
  rather than raising.

## Usage

Offline vertical slice (no GPU, no Windows binary):

```bash
python -m poster_agent.v2.cli \
  --brief-file briefs/brief_kct_v2_demo.txt \
  --mode mock \
  --out runs/v2_demo
```

Live path on Windows (ComfyUI + VectorCraft):

```bash
python -m poster_agent.v2.cli \
  --brief-file briefs/brief_kct_v2_demo.txt \
  --mode live \
  --endpoint http://127.0.0.1:8188 \
  --out runs/v2_live
```

Enable the VLM critic by adding `--vlm-review` (optionally with
`--review-endpoint http://127.0.0.1:8080/v1`), or by constructing
`Pipeline(..., reviewer=PosterReviewerV2())`. Without a reviewer the review
stage is skipped; deterministic gates still decide delivery. When the vision
endpoint is unreachable the run still passes deterministic gates, reports
`VLM review unavailable`, and records the warning instead of crashing.

## MCP frontend

The interactive frontend is a dependency-free JSON-RPC server over the same
core:

```bash
python -m poster_agent.mcp.v2_server
```

Tools:

| Tool | Purpose |
| --- | --- |
| `run_poster` | Plan, resolve assets, compose, gate and optionally review one brief |
| `plan_poster` | Return ranked layout candidates without rendering |
| `get_brand_contract` | Return the deterministic brand contract for a school |
| `list_schools` | List schools with a v2 contract |

`run_poster` accepts `brief_text` or `brief_file`, plus `school`,
`format_name`, `mode` (`mock` or `live`), `output_dir`, and optional review or
candidate budgets. The response is the same audit trail the CLI prints:
success, chosen candidate, output path, blocking issues, warnings, attempts and
review.

## Current blockers

1. **Official KCT logo is missing.** `assets/logo_kumaraguru.png` is an Apex
   Institute of Technology demo mark and must not be used. The contract points
   at `assets/brand/kct/kct_logo.png`; until that file exists, mock runs use a
   clearly marked placeholder and emit `logo_placeholder` as a warning.
2. **Helvetica Neue / Montserrat are not installed in `assets/fonts/`.** The
   live renderer falls back through the contract's `fallbacks` chain. Install
   the licensed fonts for brand-accurate output.
3. **VectorCraft is Windows-only.** `VectorCraftComposer` builds and tests the
   command batch on any host, but executing the `.exe` requires Windows.
4. **OCR engine is not installed in WSL.** The mock suite checks text from the
   render manifest. Install RapidOCR/PaddleOCR, or pass `ocr_lines`, to enable
   the pixel OCR gate.

## Deliberate non-goals for this slice

* No KCLAS/KCTBS/KIA contracts until their official logos and typefaces are
  verified. The YAML is deliberately KCT-only.
* No migration of the legacy `unified_pipeline.py` or `composer.py` yet. They
  remain in place while v2 proves parity on the KCT slice.
* No generative layout search beyond the three deterministic candidate
  templates. The scorer interface is ready for a generative proposer.
