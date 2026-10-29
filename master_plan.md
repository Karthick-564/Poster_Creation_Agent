# Poster Agent — Master Build Plan

## One Question Before Step 5

> **Ideogram transport**: The spec says the backend (ComfyUI API, diffusers, or HTTP)
> is on another machine on the local network. Which one are you using?
> Until you answer, Step 5 is stubbed behind the adapter interface — everything else builds normally.

---

## Repo Layout

```
d:\karthick3\Projects\Image_Generation\
├── poster_agent/
│   ├── config/         settings.py         — YAML loader, env secrets
│   ├── context/        loader.py           — context.md + assets/ reader
│   ├── spec/           models.py           — PosterSpec Pydantic model + JSON Schema
│   ├── planner/        planner.py          — Groq LLM call → PosterSpec
│   │                   verifier.py         — verbatim string check
│   ├── generators/     base.py             — abstract GeneratorAdapter
│   │                   ideogram.py         — Ideogram 4.0 adapter (stubbed transport)
│   │                   mock.py             — returns plain background, used in Steps 1-4
│   ├── renderer/       renderer.py         — PosterSpec → HTML/CSS → Playwright → PNG/PDF
│   ├── checks/         ocr.py              — PaddleOCR text checks
│   │                   geometry.py         — DOM overflow/overlap/margin checks
│   │                   contrast.py         — WCAG contrast + min font size
│   │                   logo.py             — logo presence + size checks
│   │                   runner.py           — aggregates all checks → CheckReport
│   ├── reviewer/       reviewer.py         — LFM3-VL-2B vision critic (local endpoint)
│   ├── loop/           repair.py           — repair loop, candidate selection
│   └── logging/        run_log.py          — per-run folder, all artifacts saved
├── templates/
│   ├── event_portrait_3col.json
│   ├── event_portrait_hero.json
│   ├── event_landscape_2col.json
│   └── event_minimal.json
├── assets/                                 — logos (SVG/PNG) go here
├── context.md                              — college/club/brand details
├── configs/
│   └── default.yaml
├── tests/
│   ├── fixtures/
│   │   ├── duplicated_headline.png         — MUST fail OCR (duplication)
│   │   ├── wrong_order.png                 — MUST fail OCR (order)
│   │   └── clean_poster.png               — MUST pass all checks
│   ├── test_spec.py
│   ├── test_checks.py
│   ├── test_planner.py
│   ├── test_renderer.py
│   └── test_loop.py
├── scripts/
│   └── bakeoff/
│       └── run_bakeoff.py
└── README.md
```

---

## Component Interfaces (mini contracts)

```python
# generator base
class GeneratorAdapter(ABC):
    def generate(self, spec: PosterSpec) -> list[Image]: ...

# check result
class CheckResult(BaseModel):
    check_name: str
    severity: Literal["blocking", "warning", "pass"]
    detail: str
    fix_hint: str | None

# repair action enum
class RepairAction(str, Enum):
    REFLOW_TEXT   = "reflow_text"     # re-render only
    EDIT_SPEC     = "edit_spec"       # change spec, re-render
    NEW_SEED      = "new_seed"        # regenerate art
    SWITCH_STRAT  = "switch_strategy" # A↔B strategy switch
```

---

## Build Steps

### Step 1 — Spec + Config + Context (foundation, no external calls)

**Files created:**
- `configs/default.yaml`
- `poster_agent/config/settings.py`
- `poster_agent/context/loader.py`
- `poster_agent/spec/models.py`
- `tests/test_spec.py`

**What `default.yaml` covers:**
```yaml
groq:
  model: openai/gpt-oss-120b
  alt_model: qwen/qwen3-8b-27b
  temperature: 0.2
  max_tokens: 4096

ideogram:
  strategy: B          # A = model renders text, B = renderer places text
  transport: stub      # http | comfyui | diffusers — fill after your answer
  endpoint: http://192.168.x.x:PORT
  candidates_per_round: 2

repair:
  max_iterations: 4
  candidates: 2

renderer:
  dpi: 300

reviewer:
  endpoint: http://localhost:PORT/v1
  model: LFM3-VL-2B
  thinking_mode: true

checks:
  ocr_engine: paddleocr
  min_contrast_ratio: 4.5
  min_font_pt: 14
```

**PosterSpec key fields:**
```python
class TextElement(BaseModel):
    id: str
    role: Literal["headline","subheadline","date","venue","body","label","footer"]
    text: str
    source: Literal["brief","context"]      # verifier uses this
    font: str
    size: int                               # in pt
    weight: int
    color: str                              # #RRGGBB
    box: BBox                              # 0-1000 coords

class ArtSlot(BaseModel):
    id: str
    prompt: str
    box: BBox
    transparent: bool

class PosterSpec(BaseModel):
    canvas_width_px: int
    canvas_height_px: int
    dpi: int
    template_id: str
    palette: list[str]                      # max 8 #RRGGBB
    text_safe_zones: list[BBox]
    elements: list[TextElement]
    logos: list[LogoPlacement]
    art_slots: list[ArtSlot]
    assumptions: list[str]
    missing_fields: list[str]

    model_config = ConfigDict(extra="forbid")  # Groq strict compat
```

**Tests cover:**
- Schema validates correctly formed specs
- Schema rejects extra fields (Groq strict)
- BBox validates: min < max, 0 ≤ values ≤ 1000
- `missing_fields` non-empty → pipeline must stop
- JSON Schema export matches Pydantic model
- Context loader reads `context.md` and `assets/` correctly

**Assumption:** Groq strict JSON mode requires `additionalProperties: false` at every
nested level — Pydantic's `ConfigDict(extra="forbid")` maps to this correctly.

**Deliverable:** `pytest tests/test_spec.py` — all green. No external calls.

---

### Step 2 — Renderer + Checks + Fixture Tests (no LLM, no image gen)

**Files created:**
- `poster_agent/renderer/renderer.py`
- `poster_agent/checks/ocr.py`
- `poster_agent/checks/geometry.py`
- `poster_agent/checks/contrast.py`
- `poster_agent/checks/logo.py`
- `poster_agent/checks/runner.py`
- `tests/test_checks.py`
- `tests/fixtures/` (you supply the 3 images)

**Renderer contract:**
- Takes a PosterSpec + optional art image paths
- Builds an HTML file with CSS absolute positioning (0-1000 grid scaled to canvas)
- Exports PNG + PDF via Playwright
- Returns `{png_path, pdf_path, dom_boxes: dict[element_id, PixelBox]}`
- Strategy B: text elements rendered as `<div>` in HTML
- Strategy A: text elements omitted from HTML (art carries them)

**Checks contract:**

```
OCR check (deterministic):
  1. Run PaddleOCR on the poster PNG
  2. Extract all text lines, in top-to-bottom order
  3. For each expected string in spec:
     - BLOCKING if not found (missing text)
     - BLOCKING if found more than once (duplication)
  4. Check ordering: the rank of text lines in OCR output
     must respect role hierarchy (headline before subheadline, etc.)
     - BLOCKING if order violated

Geometry check (from DOM boxes):
  - BLOCKING: any element outside canvas bounds
  - BLOCKING: any two elements overlap by > 5px
  - WARNING: margin < configured minimum

Contrast check:
  - BLOCKING: text element contrast ratio < 4.5 (WCAG AA)
  - BLOCKING: font size < 14pt equivalent at intended viewing size

Logo check:
  - BLOCKING: required logo not detected in image
  - BLOCKING: logo rendered smaller than minimum size from asset rules
```

**Fixture tests (the acceptance criteria):**

| Fixture | Expected result |
|---|---|
| `duplicated_headline.png` | OCR check BLOCKING (duplication) |
| `wrong_order.png` | OCR check BLOCKING (order violation) |
| `clean_poster.png` | All checks PASS |

**Deliverable:** `pytest tests/test_checks.py` — all fixture tests pass.

---

### Step 3 — Planner + Verbatim Verifier

**Files created:**
- `poster_agent/planner/planner.py`
- `poster_agent/planner/verifier.py`
- `poster_agent/planner/templates.py`   (template library)
- `tests/test_planner.py`

**Planner contract:**
```
Input:  requirements text (str) + context (ContextBundle)
Output: PosterSpec

Flow:
  1. Build system prompt: role + template library + context.md content + rules
  2. Build user prompt: requirements text
  3. Call Groq with json_schema mode (PosterSpec schema)
  4. Parse response → PosterSpec
  5. Run verifier
  6. If missing_fields non-empty → raise MissingFieldsError (caller logs and stops)
  7. Return PosterSpec
```

**Verbatim verifier rules:**
```
For every text element where source == "brief":
  → the exact string must appear verbatim in requirements text
For every text element where source == "context":
  → the exact string must appear verbatim in context.md
If any string fails → raise VerbatimViolationError with the offending strings
```

**Template library (4 templates for V1):**
```
event_portrait_hero:      full-bleed art hero top, text block bottom
event_portrait_3col:      3 equal columns, art header strip
event_landscape_2col:     2 columns, left art right text
event_minimal:            large typography, minimal art, geometric shapes
```
Each template defines named slots with:
- Normalized box coordinates
- Semantic role (headline_slot, body_slot, art_slot, logo_slot)
- Character budget (warns planner if text will overflow)
- Visual prominence ranking

**Planner prompt rules (system prompt includes these):**
- Copy strings VERBATIM. Never paraphrase or rewrite.
- If a date, venue, or name is not in the brief or context.md, add to `missing_fields`.
- Pick the template whose slot layout best fits the content density.
- Palette: derive from context.md brand palette or infer from style/domain.
- Put all style decisions in `assumptions`.

**Tests cover:**
- Verifier catches invented strings not in source texts
- Verifier passes when strings are verbatim copies
- Missing dates/venues surface in `missing_fields`
- BBox values from planner stay in 0-1000 range
- Schema round-trips correctly through Groq's strict mode

**Assumption:** Groq model `openai/gpt-oss-120b` is available on your account.
If not, the config's `alt_model: qwen/qwen3-8b-27b` is the fallback — set `groq.model`
in your local config override.

**Deliverable:** `pytest tests/test_planner.py` — all green (uses real Groq call + fixture briefs).

---

### Step 4 — Repair Loop + Logging (mock generator)

**Files created:**
- `poster_agent/generators/mock.py`   (returns solid-color background)
- `poster_agent/loop/repair.py`
- `poster_agent/logging/run_log.py`
- `tests/test_loop.py`

**Mock generator:** returns a 2480×3508 plain background image (color from palette).
Used until Step 5. Allows the full pipeline to run end-to-end.

**Repair loop contract:**
```
run(spec, brief, context) -> RunResult

For each iteration (max N from config):
  1. Generate K candidates (mock or real generator)
  2. For each candidate: render → check → score
  3. Keep best candidate (lowest blocking count, then lowest warning count)
  4. If best has 0 blocking checks → done, return SUCCESS
  5. Map blocking failures to cheapest repair action:
       missing text       → EDIT_SPEC (fix text element)
       text duplication   → NEW_SEED (model artifact)
       overflow           → REFLOW_TEXT (shrink font in spec)
       contrast fail      → EDIT_SPEC (adjust color)
       order violation    → EDIT_SPEC (reorder elements)
       all else fails     → SWITCH_STRATEGY (A↔B)
  6. Apply action, loop
If budget exhausted → return FAILED (best attempt + all reasons)
```

**Run log structure:**
```
runs/
└── {timestamp}_{brief_slug}/
    ├── requirements.txt
    ├── context_snapshot.md
    ├── spec_v1.json ... spec_vN.json
    ├── iteration_1/
    │   ├── generator_payload.json
    │   ├── seed.txt
    │   ├── candidate_1.png
    │   ├── candidate_2.png
    │   ├── check_results.json
    │   └── decision.txt
    ├── ...
    ├── final.png
    ├── final.pdf
    ├── run_summary.json   {status, iterations, cost_usd, duration_s}
    └── reviewer_output.json
```

**Tests cover:**
- Mock generator + renderer + checks + loop runs end-to-end
- FAILED result returned when mock is set to always produce a broken poster
- Run log folder created with all expected files
- Repair action mapping fires correct action for each failure type

**Deliverable:** `pytest tests/test_loop.py` + one full end-to-end run in the log.

---

### Step 5 — Ideogram Adapter (BLOCKED on transport question)

**Waiting for:** which backend are you using?
- `http`: plain HTTP POST to Ideogram's REST API (or a local proxy)
- `comfyui`: ComfyUI workflow JSON via the ComfyUI API
- `diffusers`: local Python diffusers pipeline

**Once answered, this step implements:**
- `poster_agent/generators/ideogram.py`
- Ideogram JSON prompt builder from PosterSpec
- Strategy A / Strategy B switching
- Seed management (saved in run log for reproducibility)
- Transport class (one of the three above)

**Ideogram JSON format the adapter produces:**
```json
{
  "high_level_description": "...(≤50 words)...",
  "style_description": {
    "aesthetics": "...",
    "lighting": "...",
    "medium": "...",
    "art_style": "...",
    "color_palette": ["#1A1A2E", "#16213E", "#00D4FF"]
  },
  "compositional_deconstruction": {
    "background": "...",
    "elements": [
      {
        "type": "text",
        "bbox": [y_min, x_min, y_max, x_max],
        "text": "exact string",
        "desc": "...",
        "color_palette": ["#FFFFFF"]
      }
    ]
  }
}
```

---

### Step 6 — Reviewer + Bake-off Scripts

**Files created:**
- `poster_agent/reviewer/reviewer.py`
- `scripts/bakeoff/run_bakeoff.py`
- `scripts/bakeoff/briefs/` (fixed test briefs)

**Reviewer contract:**
```
Input:  poster PNG + PosterSpec
Output: ReviewResult {
  hierarchy: 1-5,
  balance: 1-5,
  readability: 1-5,
  brand_fit: 1-5,
  polish: 1-5,
  three_second_test: {event: str, date: str, venue: str, pass: bool},
  fixes: list[str]   (specific, actionable)
}
```

**Reviewer prompt includes:**
- The PosterSpec (so it knows what was intended)
- A downscaled copy (for 3-second test)
- Fixed rubric (same every time, for consistency)
- Thinking mode: toggled via config

**Bake-off script compares:**
- LFM3-VL-2B with thinking ON vs OFF
- GPT-4o (if key available) as reference
- Per brief: known flaws found, false alarms, consistency across 3 runs, latency

---

## Dependency Graph

```
Step 1 (spec/config/context)
    ↓
Step 2 (renderer + checks) ← you supply 3 fixture images here
    ↓
Step 3 (planner) ← needs GROQ_API_KEY
    ↓
Step 4 (loop + logging, mock generator) ← full pipeline test
    ↓
Step 5 (Ideogram adapter) ← BLOCKED on transport answer
    ↓
Step 6 (reviewer + bakeoff) ← needs local LFM3-VL-2B endpoint
```

---

## Open Questions (answer when relevant)

| # | Question | Needed for |
|---|---|---|
| 1 | **Ideogram transport**: `http`, `comfyui`, or `diffusers`? | Step 5 |
| 2 | Do you have `context.md` content ready, or should I create a template? | Step 1 |
| 3 | Can you supply the 3 fixture poster images? | Step 2 |
| 4 | Is LFM3-VL-2B already running locally on an OpenAI-compat endpoint? | Step 6 |
| 5 | Confirm `openai/gpt-oss-120b` is available on your Groq account, else which model? | Step 3 |

---

## What Each Step Delivers

| Step | What you can run | External calls |
|---|---|---|
| 1 | `pytest tests/test_spec.py` | None |
| 2 | `pytest tests/test_checks.py` + fixture tests | None |
| 3 | `pytest tests/test_planner.py` | Groq API |
| 4 | `pytest tests/test_loop.py` + full run | Groq API |
| 5 | Real poster generation | Groq + Ideogram |
| 6 | Bake-off report | Groq + Ideogram + local VLM |
