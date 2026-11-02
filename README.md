# Poster Agent (`poster-agent`)

An autonomous, multi-layered promotional poster generation agent designed for high-impact editorial poster design. Combines generative diffusion models, intelligent LLM spatial planning, a house style design system, native VectorCraft vector rendering, deterministic quality gates, and iterative repair loops.

---

## 1. System Architecture

`poster-agent` replaces static templates and blind bounding boxes with an **"Art-First, Layout-Second"** architecture that dynamically composes posters around real assets and measured image geometry.

```
                              USER BRIEF
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │ 1. Brief Ingestion (`BriefExtractor`)                       │
    │    • Zero-Drop parser extracts verbatim text fields         │
    │    • Mandatory gates: title, date, venue                    │
    └─────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │ 2. Spatial & Concept Planning (Gemini Planner)              │
    │    • Injects corpus exemplars from 205-poster catalog       │
    │    • Derives archetype, palette, typography & asset plan    │
    └─────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │ 2b. Asset Resolution Layer (`AssetResolver`)                │
    │    • Deterministic source ladder:                           │
    │      supplied ──► archive ──► native ──► generated          │
    │    • Diffusion models only invoked when necessary           │
    └─────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │ 3 & 4. Visual Asset Acquisition                             │
    │    • Hero: supplied asset, native vector, or Qwen-Image     │
    │    • Background: clean brand field, archive, or Ideogram    │
    │    • ArtMeasurer: measures alpha bounds, centroid, calm zone│
    └─────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │ 5. Native VectorCraft Composition (`composer.py`)           │
    │    • Multi-Archetype: Focal Point, Z-Pattern, Split, 3-Col  │
    │    • School brand voices (Montserrat, Barlow, Noto Tamil)   │
    │    • 5-band vertical rhythm across full 9:16 canvas         │
    │    • Width-fit wrapping (<=2 lines) & doctrine floor clamps │
    │    • Hero reserve & QR clearance (zero collisions)          │
    │    • WCAG 2.1 contrast enforcement (>=4.5:1 ratio)          │
    │    • Structural rows: logo, banner tab, pill, footer bar    │
    └─────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │ 6 & 7. Deterministic QA Gates & Multimodal Review           │
    │    • Exact canvas scale check (2.0x master export)          │
    │    • Zero margin escapes & text collision verification      │
    │    • Visual critique & glance readability                   │
    └─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Design Doctrine & House Style

Calibrated against the ground-truth 205-poster catalog (`Examples/extracted/Posters/poster_catalog.csv`):

* **9:16 Story Default (1080×1920)**: Dominates 84% of the verified corpus (`corpus: 172/205`). Secondary tiers include 4:5 portrait (1080×1350), 1:1 square, and A3/A4 print dimensions.
* **White / Light Base Dominance**: 63% of catalog posters (`corpus: 129/205`) employ clean white or light tinted backgrounds.
* **Typographic Hierarchy & Floors**:
  * **Headline**: $\ge \text{canvas\_h} / 11$ (e.g. $174.5\text{pt}$ for 9:16 story), wrapped to $\le 2$ lines.
  * **Body / Logistics**: $\ge 1.8\%$ of canvas height ($\ge 34.6\text{pt}$).
  * **Microcopy**: $\ge 1.4\%$ of canvas height ($\ge 26.9\text{pt}$, minimum $14\text{pt}$).
  * **Safe Margins**: $4.5\% - 5\%$ of canvas dimensions ($48.6\text{pt}$ on 1080w).
* **Contrast Floors**: WCAG 2.1 relative luminance checking enforces $\ge 4.5:1$ contrast on all structural and body elements against underlying fills or textures.
* **School Brand Voices**:
  * **KCT / KCLAS / KI / KIA**: Montserrat Bold display voice, Inter body.
  * **KCTBS**: Barlow Bold display voice.
  * **Tamil Typography**: Noto Sans Tamil Bold.

---

## 3. Directory Layout

```
project/
├── briefs/                       # User brief files (.txt)
├── configs/                      # Configuration YAMLs
│   ├── asset_sources.yaml        # Archive roots, tag-to-keyword maps, extensions
│   ├── default.yaml              # Pipeline runtime defaults
│   ├── house_style.yaml          # School palettes, typography & genre policies
│   └── palette_policy.yaml       # Palette extraction rules
├── docs/                         # Engine facts & architecture audits
│   └── vc_engine_facts.md        # VectorCraft CLI engine specs & gotchas
├── poster_agent/                 # Core Python package
│   ├── assets/                   # Conditional asset resolution (Stage 2b)
│   │   └── resolver.py           # Source ladder resolution (supplied/archive/native/gen)
│   ├── generators/               # ComfyUI client & model workflow adapters
│   ├── house_style.py            # School lookup, genre policies & exemplar injection
│   ├── ingestion/                # Zero-drop brief extractor
│   ├── qa/                       # Deterministic QA gates (bounds, overlaps, contrast)
│   ├── renderer/                 # Native VectorCraft composer
│   │   ├── composer.py           # Master archetype composer, width-fit & rhythm
│   │   └── vectorcraft_renderer.py # VectorCraft CLI bridge & text manifest parser
│   ├── unified_pipeline.py       # Strict 8-stage unified pipeline coordinator
│   └── vision/                   # ArtMeasurer: alpha bbox, centroid & calm regions
├── runs/                         # Output run directories (gitignored)
│   └── poster_run_<id>/          # Per-run master PNG, PDF, plan.json & report.md
├── tests/                        # Comprehensive pytest test suite
├── tools/                        # Portable vendor binaries (VectorCraft CLI)
├── run_poster.py                 # Primary CLI entry point
└── HANDOFF.md                    # Operational handoff log & current engineering state
```

---

## 4. Usage & Commands

### 1. Live Production Run
Requires `GEMINI_API_KEY` in `.env` and local ComfyUI server if generation is needed:
```powershell
python run_poster.py --brief-file briefs/brief_c4_demo.txt
```
Generates master deliverables into `runs/{run_id}/`:
* `master_render_2x.png`: High-resolution 2x raster render (2160×3840 for story).
* `master_print.pdf`: Print-ready native vector PDF.
* `plan.json`: Complete spatial typography plan with slot zones.
* `{slug}_master_pipeline_report.md`: Detailed stage-by-stage audit and QA gate report.

Optional: `--artifact-dir D:\deliverables` copies deliverables to an external folder (default writes strictly within `runs/`).

### 2. Fast Offline Mock Run
Exercises the full planning, asset resolution, layout compilation, VectorCraft rendering, and QA gates offline without network calls or external APIs:
```powershell
python run_poster.py --mock --brief-file briefs/brief_c4_demo.txt
```

### 3. Running the Test Suite
Run the full test suite across all subsystems:
```powershell
python -m pytest tests/ -q
```
Or run individual targeted test suites:
```powershell
python -m pytest tests/test_render_polish.py -v
python -m pytest tests/test_composer.py -v
python -m pytest tests/test_house_style.py -v
```

---

## 5. Artifact & Operating Policy

Per project rules (`AGENTS.md`):
1. **Never write outside the project root**: All pipeline outputs belong strictly in `runs/{run_id}/`.
2. **No hardcoded absolute paths**: All paths are relative or configuration-driven.
3. **Honest Gate Semantics**: Mock mode is deterministic and opt-in; live mode halts explicitly on gate failures (`PLANNING_HALT`).
