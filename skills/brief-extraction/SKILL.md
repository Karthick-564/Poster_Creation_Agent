---
name: brief-extraction
description: Use when ingesting user brief text and institutional context. Extracts verbatim key-value fields with zero-drop guarantee, tags provenance, and identifies missing required fields.
---
# Brief Extraction
## Rules
1. Every string must be tagged with provenance: `brief`, `context`, or `decorative`.
2. Never invent dummy emails, hashtags, dates, times, venues, or pricing.
3. If a key fact is missing from the brief, add it to `missing_fields` and halt execution.
4. Tolerate all standard formatting styles: bullet dashes (`-`), asterisks (`*`), numbers (`1.`), and raw key-value lines (`Key: Value`).
