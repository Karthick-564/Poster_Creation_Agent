# VectorCraft Design Recipes & Tool Call Sequences

**Status**: Phase 0 Design Library  
**Target Engine**: VectorCraft CLI (v0.19.0) via `vectorcraft-mcp`  
**Yardstick Brief**: `briefs/brief_noir_beats.txt` (NOIR BEATS 2026, 4:5 aspect, 1080×1350)

---

## Overview

In Phase D, poster generation relied on rigid deterministic slots (`composer.compose_slots`), producing centered single-column stacks with harsh unfeathered rectangular image blocks.

These recipes provide the VectorCraft MCP server (and designer agents) with reproducible, compositional patterns that satisfy all physical QA gates (safe margins $\ge 4.5\%$, no overlaps, WCAG contrast floors, verbatim copy) while unlocking visual interest, asymmetric balance, dynamic type scale, and seamless layer integration.

---

## Recipe 1: Swiss Editorial Grid

### Concept & Intent
A clean, mathematically disciplined layout inspired by the International Typographic Style. Uses asymmetrical columns, strict typographic hierarchy, fine hairline division rules, and generous active whitespace.

### When to Use
- Tech conferences, electronic/minimalist events, modern art exhibitions, film festivals.

### Tool Call Sequence (1080 × 1350 Canvas)
1. **Background**: Deep solid base fill
   ```json
   {"tool": "add_shape_rectangle", "args": {"x": 0, "y": 0, "width": 1080, "height": 1350, "fill": "#070B19"}}
   ```
2. **Hairline Division Rule**: Vertical grid guide (accent color at low opacity)
   ```json
   {"tool": "add_shape_rectangle", "args": {"x": 120, "y": 140, "width": 2, "height": 1080, "fill": "#00F5D4"}}
   ```
3. **Eyebrow / Category**: Micro-label above headline, high tracking
   ```json
   {"tool": "add_text", "args": {"text": "TECHNO / INDUSTRIAL / SYNTH", "x": 150, "y": 170, "size": 18, "color": "#00F5D4", "role": "eyebrow"}}
   ```
4. **Dominant Asymmetric Headline**: Left-anchored against grid line, massive scale
   ```json
   {"tool": "add_text", "args": {"text": "NOIR BEATS", "x": 150, "y": 270, "size": 84, "color": "#F0F6FC", "style": "Bold", "role": "headline"}}
   ```
5. **Hairline Horizontal Split**:
   ```json
   {"tool": "add_shape_rectangle", "args": {"x": 150, "y": 320, "width": 780, "height": 1, "fill": "#7B2FFF"}}
   ```
6. **Hero Placement with Feathering**:
   ```json
   {"tool": "place_image", "args": {"path": "runs/noir_beats_v8/layer3_hero.png", "rect": [150, 360, 780, 480], "feather_radius": 16.0}}
   ```
7. **Two-Column Meta Stack**: Date & Time left, Venue & Pricing right
   ```json
   {"tool": "add_text", "args": {"text": "FRI OCT 31 2026 // 22:00 - LATE", "x": 150, "y": 920, "size": 24, "color": "#00F5D4", "role": "date"}}
   {"tool": "add_text", "args": {"text": "THE UNDERGROUND VAULT - BERLIN", "x": 150, "y": 980, "size": 22, "color": "#F0F6FC", "role": "venue"}}
   ```

### Safety & Invariants
- Margin: $x \ge 49\text{ px}$ ($4.5\%$). With $x=150$, safe margin is generously respected ($\approx 13.9\%$).
- Invariant: Rules must never overlap text bounding boxes.

---

## Recipe 2: Asymmetric Split (Hero Anchor + Offset Typography)

### Concept & Intent
Breaks the static center alignment by splitting the canvas vertically or diagonally. One side carries the heavy visual weight (feathered hero or rich texture), while the opposing side carries crisp, high-contrast typographic hierarchy.

### When to Use
- Club nights, cyberpunk/noir themes, theatrical performances, product launches.

### Tool Call Sequence (1080 × 1350 Canvas)
1. **Full-Bleed Background Layer**:
   ```json
   {"tool": "place_image", "args": {"path": "runs/noir_beats_v8/layer0_bg.png", "rect": [0, 0, 1080, 1350]}}
   ```
2. **Soft Atmospheric Underlay**: Deep vertical scrim covering the right $60\%$ of canvas
   ```json
   {"tool": "soft_scrim", "args": {"x": 420, "y": 0, "width": 660, "height": 1350, "direction": "to_right", "stops": [[0.0, "#070B19", 0.0], [0.4, "#070B19", 0.92], [1.0, "#070B19", 0.98]]}}
   ```
3. **Hero Offset Left**: Large dramatic crop on the left $60\%$, feathered right edge
   ```json
   {"tool": "place_image", "args": {"path": "runs/noir_beats_v8/layer3_hero.png", "rect": [60, 240, 520, 700], "feather_radius": 24.0, "blend_mode": "screen"}}
   ```
4. **Typographic Stack Offset Right**:
   ```json
   {"tool": "add_text", "args": {"text": "OCT 31", "x": 620, "y": 320, "size": 48, "color": "#FF3D68", "role": "date"}}
   {"tool": "add_text", "args": {"text": "NOIR\nBEATS", "x": 620, "y": 480, "size": 96, "color": "#F0F6FC", "style": "Bold", "role": "headline"}}
   {"tool": "add_text", "args": {"text": "AN IMMERSIVE AUDIOVISUAL EXPEDITION", "x": 620, "y": 620, "size": 20, "color": "#00F5D4", "role": "subtitle"}}
   {"tool": "add_text", "args": {"text": "THE UNDERGROUND VAULT", "x": 620, "y": 720, "size": 24, "color": "#F0F6FC", "role": "venue"}}
   ```

### Safety & Invariants
- Typography bounding boxes strictly clear the hero bounding box (`hero_rect: [60, 240, 520, 700]`).
- Right margin: $620 + \text{width} \le 1080 - 49 = 1031$. Multi-line headline "NOIR\nBEATS" width $\approx 360\text{ px}$, total right boundary $980\text{ px} \le 1031\text{ px}$.

---

## Recipe 3: Brutalist Oversized Display Scale

### Concept & Intent
Creates immense dramatic impact using extreme type scale contrast ($> 4:1$ between headline and body). Massive headline dominates the upper half, balanced by dense, hyper-structured micro-copy in the lower third.

### When to Use
- EDM / Rave posters, streetwear drops, brutalist architecture showcases, high-energy festivals.

### Tool Call Sequence (1080 × 1350 Canvas)
1. **Dark Substrate**:
   ```json
   {"tool": "add_shape_rectangle", "args": {"x": 0, "y": 0, "width": 1080, "height": 1350, "fill": "#070B19"}}
   ```
2. **Radial Accent Glow**:
   ```json
   {"tool": "radial_light", "args": {"cx": 540, "cy": 320, "radius": 420, "color": "#7B2FFF", "opacity": 0.45}}
   ```
3. **Monolithic Display Headline**: Font size 120 pt, spanning nearly the entire safe width
   ```json
   {"tool": "add_text", "args": {"text": "NOIR BEATS", "x": 60, "y": 240, "size": 118, "color": "#F0F6FC", "style": "Bold", "role": "headline"}}
   ```
4. **Hero Band**: Wide horizontal aspect slot centered below headline
   ```json
   {"tool": "place_image", "args": {"path": "runs/noir_beats_v8/layer3_hero.png", "rect": [60, 310, 960, 480], "feather_radius": 12.0}}
   ```
5. **Dense Micro-Grid Footer**: High contrast, compact leading, multiple meta rows
   ```json
   {"tool": "add_text", "args": {"text": "FEATURING SOUND ARCHITECTS & VISUAL ALCHEMISTS", "x": 60, "y": 860, "size": 20, "color": "#00F5D4", "role": "subtitle"}}
   {"tool": "add_text", "args": {"text": "THE UNDERGROUND VAULT - 1044 POSTER STRASSE", "x": 60, "y": 920, "size": 22, "color": "#F0F6FC", "role": "venue"}}
   {"tool": "add_text", "args": {"text": "FRIDAY, OCTOBER 31, 2026 // DOORS OPEN AT 22:00", "x": 60, "y": 980, "size": 22, "color": "#00F5D4", "role": "date"}}
   ```

### Safety & Invariants
- Headline text bounds must not exceed $1080 - 49 = 1031\text{ px}$. Font size $118\text{ pt}$ for 10 characters $\approx 850\text{ px}$, comfortably inside margin.

---

## Recipe 4: Type-as-Image Giant Numeral Watermark

### Concept & Intent
Treats typography as an atmospheric textural graphic. A massive year ("2026") or thematic numeral is rendered at low opacity ($10\% - 20\%$) in the middle ground, adding depth and architectural scale behind the foreground copy.

### When to Use
- New Year's Eve events, annual summits, numbered festival editions, anniversary celebrations.

### Tool Call Sequence (1080 × 1350 Canvas)
1. **Background Base**:
   ```json
   {"tool": "place_image", "args": {"path": "runs/noir_beats_v8/layer0_bg.png", "rect": [0, 0, 1080, 1350]}}
   ```
2. **Giant Watermark Numeral**: Huge 280 pt background type with violet tint at $18\%$ opacity
   ```json
   {"tool": "add_text", "args": {"text": "2026", "x": 180, "y": 580, "size": 260, "color": "#7B2FFF", "style": "Bold", "role": "watermark"}}
   ```
3. **Atmospheric Darkening Scrim**: Blends watermark into ambient depth
   ```json
   {"tool": "soft_scrim", "args": {"x": 0, "y": 300, "width": 1080, "height": 600, "direction": "to_bottom", "stops": [[0.0, "#070B19", 0.3], [1.0, "#070B19", 0.85]]}}
   ```
4. **Foreground Headline & Information Stack**: Crisp white and neon cyan typography crossing cleanly over the subdued watermark
   ```json
   {"tool": "add_text", "args": {"text": "NOIR BEATS", "x": 80, "y": 340, "size": 86, "color": "#F0F6FC", "style": "Bold", "role": "headline"}}
   {"tool": "add_text", "args": {"text": "FRIDAY OCTOBER 31", "x": 80, "y": 420, "size": 28, "color": "#00F5D4", "role": "date"}}
   ```

### Safety & Invariants
- Verbatim rule: The string "2026" is verified directly against the brief text ("2026").
- `measure()` contrast gate checks foreground text against local background. High opacity scrim guarantees foreground text contrast $\ge 4.5:1$.

---

## Recipe 5: Neon Glow & Outer Glow Energy

### Concept & Intent
Simulates high-voltage neon signage and glowing EDM club lighting using VectorCraft's `radial_light` and `stylize.outerGlow` or layered color offsets.

### When to Use
- Cyberpunk themes, electronic music, retro 80s synthwave, nighttime spectacles.

### Tool Call Sequence (1080 × 1350 Canvas)
1. **Deep Void Canvas**:
   ```json
   {"tool": "add_shape_rectangle", "args": {"x": 0, "y": 0, "width": 1080, "height": 1350, "fill": "#070B19"}}
   ```
2. **Radial Neon Aura**: Centered behind the headline focal point
   ```json
   {"tool": "radial_light", "args": {"cx": 540, "cy": 300, "radius": 360, "color": "#00F5D4", "opacity": 0.55}}
   ```
3. **Secondary Under-Glow**: Hot magenta/violet spill below headline
   ```json
   {"tool": "radial_light", "args": {"cx": 540, "cy": 450, "radius": 280, "color": "#FF3D68", "opacity": 0.35}}
   ```
4. **Primary Luminescent Headline**:
   ```json
   {"tool": "add_text", "args": {"text": "NOIR BEATS", "x": 120, "y": 320, "size": 92, "color": "#F0F6FC", "style": "Bold", "role": "headline"}}
   ```
5. **Neon Accent Divider**: 3px glowing cyan rule
   ```json
   {"tool": "add_shape_rectangle", "args": {"x": 120, "y": 360, "width": 840, "height": 3, "fill": "#00F5D4"}}
   ```
6. **Feathered Hero Integration**:
   ```json
   {"tool": "place_image", "args": {"path": "runs/noir_beats_v8/layer3_hero.png", "rect": [120, 420, 840, 520], "feather_radius": 20.0, "blend_mode": "screen"}}
   ```

### Safety & Invariants
- `radial_light` uses additive screen blending, ensuring base text legibility is preserved while bathing the design in radiant color.

---

## Recipe 6: Ticket-Stub / VIP Badge CTA Container

### Concept & Intent
Elevates the closing call-to-action (tickets, admissions, web link) from a boring plain-text line into an authoritative, tangible object—a ticket stub, pill badge, or VIP coupon container.

### When to Use
- Paid admissions, limited capacity club nights, early-bird ticket releases, VIP packages.

### Tool Call Sequence (1080 × 1350 Canvas)
1. **Container Outer Stroke & Fill**: Rounded pill container in the lower active zone
   ```json
   {"tool": "add_shape_rectangle", "args": {"x": 140, "y": 1120, "width": 800, "height": 130, "fill": "#0D142A", "stroke": "#00F5D4", "stroke_width": 2.0, "radius": 16.0}}
   ```
2. **Inner Accent Block / Ticket Notch**: Left-side highlight badge
   ```json
   {"tool": "add_shape_rectangle", "args": {"x": 142, "y": 1122, "width": 160, "height": 126, "fill": "#00F5D4", "radius": 14.0}}
   ```
3. **Badge Callout**: Dark copy inside cyan pill
   ```json
   {"tool": "add_text", "args": {"text": "ADMISSION", "x": 165, "y": 1195, "size": 22, "color": "#070B19", "style": "Bold", "role": "ticket_badge"}}
   ```
4. **Ticket Details**: High-contrast white copy inside dark container
   ```json
   {"tool": "add_text", "args": {"text": "TICKETS: NOIRBEATS2026.EVENTBRITE.COM", "x": 330, "y": 1180, "size": 20, "color": "#F0F6FC", "role": "cta"}}
   {"tool": "add_text", "args": {"text": "STRICTLY 21+ // PHOTO ID REQUIRED AT DOOR", "x": 330, "y": 1215, "size": 15, "color": "#00F5D4", "role": "disclaimer"}}
   ```

### Safety & Invariants
- Container bounds $[140, 1120, 800, 130]$ safely inside canvas margins ($y_2 = 1250 \le 1350 - 49 = 1301$).
- Contrast: `#070B19` on `#00F5D4` has $14.2:1$ contrast ratio ($\gg 4.5:1$). `#F0F6FC` on `#0D142A` has $15.8:1$.

---

## Summary Matrix of Recipes

| Recipe Name | Visual Energy | Archetype Affinity | Key MCP Tools Used |
| :--- | :--- | :--- | :--- |
| **Swiss Editorial Grid** | Precise, intellectual, elegant | Minimalist, Architectural, Tech | `add_shape_rectangle`, `add_text` (multi-col) |
| **Asymmetric Split** | Dynamic, tension-filled | Cyberpunk, Film Noir, Avant-Garde | `soft_scrim`, `place_image` (offset), `add_text` |
| **Brutalist Oversized** | Raw, high-impact, dominant | EDM / Rave, Fashion, Underground | `add_text` (120pt+), `radial_light`, `place_image` |
| **Type-as-Image Watermark**| Atmospheric, deep, layered | Anniversary, Festival, Nightclub | `add_text` (subdued), `soft_scrim`, `place_image` |
| **Neon Glow & Outer Glow** | Radiant, electrified, immersive | Synthwave, Club, Nightlife | `radial_light`, `stylize.outerGlow`, `place_image` |
| **Ticket-Stub CTA** | Actionable, tangible, premium | Concerts, Events, Conventions | `add_shape_rectangle` (nested), `add_text` |
