# Poster Agent (`poster-agent`)

An AI-driven promotional poster generation agent built with strict deterministic quality gates, verifiable text integrity, and layout planning.

## Features & Architecture

1. **Config (`poster_agent/config`)**: Type-safe YAML configuration with environment variable secret injection (`GROQ_API_KEY`).
2. **Context (`poster_agent/context`)**: Loads institutional brand profiles (`context.md`), club metadata, typography rules, color palettes, and logo assets with usage constraints.
3. **Spec (`poster_agent/spec`)**: Pydantic `PosterSpec` with coordinates in a normalized 0–1000 scale, strict JSON schema output matching Groq structured output specifications.
4. **Planner (`poster_agent/planner`)**: Calls Groq (`llama-3.3-70b-versatile`) with strict structured output. Enforces a **Verbatim String Guard** (text must appear verbatim in source brief or context without hallucination) and stops on missing dates/venues.
5. **Renderer (`poster_agent/renderer`)**: HTML/CSS layout renderer producing pixel-exact PNG and PDF exports via Playwright headless Chromium. Exports DOM bounding boxes for geometry validation.
6. **Checks (`poster_agent/checks`)**:
   - **OCR Check**: PaddleOCR / RapidOCR verification to detect missing text, duplicate lines, or reading order violations.
   - **Geometry**: Detects element overflow and collisions (`> 5px` overlap).
   - **Contrast**: WCAG 2.1 AA relative luminance and contrast ratio checks (`>= 4.5:1`), minimum readable font size check (`>= 14pt`).
   - **Logo**: Verifies required brand logos and enforces minimum dimension constraints.
7. **Template Library (`templates/`)**: Pre-engineered layout templates with named slots:
   - `event_portrait_hero`
   - `event_portrait_3col`
   - `event_landscape_2col`
   - `event_minimal`

## Quick Start & Running Tests

```bash
# Run complete test suite (42 tests covering all modules)
ComfyUI/venv/Scripts/python -m pytest tests/ -v

# Run Vision Reviewer Bake-Off Benchmark
ComfyUI/venv/Scripts/python scripts/bakeoff/run_bakeoff.py

# Generate a promotional poster end-to-end (Mock generator)
ComfyUI/venv/Scripts/python scripts/generate_poster.py --mock --brief " AI Hackathon 2026\nDate: November 12-14, 2026\nVenue: Auditorium Hall, Apex Institute"

# Generate a promotional poster with Ideogram 4.0 in ComfyUI (GPU)
ComfyUI/venv/Scripts/python scripts/generate_poster.py --brief-file scripts/bakeoff/briefs/brief_1_tech.txt
```

## Vision Reviewer & 3-Second Test

The reviewer module (`poster_agent/reviewer`) evaluates candidate posters using an OpenAI-compatible endpoint (targeting `LFM3-VL-2B` from Liquid AI) with a configurable reasoning/thinking mode toggle (`thinking: True/False`).
It generates a 360px downscaled thumbnail for the **3-second test** to guarantee that the event title, date, and venue are instantly recognizable at a glance.
A comprehensive bake-off script (`scripts/bakeoff/run_bakeoff.py`) runs fixed briefs across configurations and generates markdown tables reporting:
- Visual polish, hierarchy, balance, readability (1-5 scale)
- 3-Second glance test pass rate
- Consistency score across runs
- Latency (seconds)


