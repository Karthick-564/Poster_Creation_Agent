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
# Run complete test suite
pytest tests/ -v
```
