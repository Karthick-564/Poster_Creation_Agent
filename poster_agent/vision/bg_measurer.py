"""Background image analyzer: 12-col x 15-row grid calm/busy/salient cell classification."""
from pathlib import Path
from typing import Any, Union
import numpy as np
from PIL import Image


def measure_background(
    image: Union[str, Path, Image.Image, np.ndarray],
    grid_cols: int = 12,
    grid_rows: int = 15,
) -> dict[str, Any]:
    """Downsample background to grid_cols x grid_rows and classify each cell.

    Returns JSON-safe structure mapping every cell to calm/busy/salient plus
    a list of contiguous calm rectangles in normalized 0-1000 [y0, x0, y1, x1] form.
    """
    if isinstance(image, (str, Path)):
        img = Image.open(image).convert("L")
        arr = np.array(img, dtype=float) / 255.0
    elif isinstance(image, Image.Image):
        img = image.convert("L")
        arr = np.array(img, dtype=float) / 255.0
    elif isinstance(image, np.ndarray):
        if image.ndim == 3:
            arr = (0.299 * image[:, :, 0] + 0.587 * image[:, :, 1] + 0.114 * image[:, :, 2])
        else:
            arr = image.astype(float)
        if arr.max() > 1.0:
            arr = arr / 255.0
    else:
        raise TypeError(f"Unsupported image type: {type(image)}")

    H, W = arr.shape
    R, C = grid_rows, grid_cols

    cells = []
    calm_mask = np.zeros((R, C), dtype=bool)

    calm_count = 0
    busy_count = 0
    salient_count = 0

    for r in range(R):
        y0 = int(r * H / R)
        y1 = int((r + 1) * H / R)
        for c in range(C):
            x0 = int(c * W / C)
            x1 = int((c + 1) * W / C)

            patch = arr[y0:y1, x0:x1]
            if patch.size == 0:
                mean_lum = 0.0
                std_lum = 0.0
            else:
                mean_lum = float(np.mean(patch))
                std_lum = float(np.std(patch))

            # Classification logic
            # calm: low local variance/edges (< 0.055)
            # salient: high mean luminance and high variance (focal bright element)
            # busy: textured/detailed background
            if std_lum <= 0.055:
                classification = "calm"
                calm_mask[r, c] = True
                calm_count += 1
            elif mean_lum >= 0.50 and std_lum >= 0.08:
                classification = "salient"
                salient_count += 1
            else:
                classification = "busy"
                busy_count += 1

            cells.append({
                "row": r,
                "col": c,
                "classification": classification,
                "mean_lum": round(mean_lum, 3),
                "std_lum": round(std_lum, 3),
            })

    total_cells = R * C
    calm_percentage = round((calm_count / total_cells) * 100.0, 1)

    # Find contiguous rectangular calm regions in [y0, x0, y1, x1] normalized 0-1000
    calm_regions = _extract_calm_regions(calm_mask, R, C)

    return {
        "grid_cols": C,
        "grid_rows": R,
        "calm_percentage": calm_percentage,
        "counts": {
            "calm": calm_count,
            "busy": busy_count,
            "salient": salient_count,
        },
        "cells": cells,
        "calm_regions": calm_regions,
    }


def _extract_calm_regions(mask: np.ndarray, R: int, C: int) -> list[list[int]]:
    """Extract up to 4 significant contiguous calm rectangles in normalized 0-1000 [y0, x0, y1, x1]."""
    regions = []

    # 1. Look for full-width or broad horizontal calm bands (typical for poster header / footer)
    visited = np.zeros_like(mask, dtype=bool)

    # Check consecutive rows where >= 80% of cells are calm
    calm_rows = [r for r in range(R) if np.mean(mask[r, :]) >= 0.80]
    if calm_rows:
        groups = []
        cur = [calm_rows[0]]
        for r in calm_rows[1:]:
            if r == cur[-1] + 1:
                cur.append(r)
            else:
                groups.append(cur)
                cur = [r]
        groups.append(cur)

        for g in groups:
            r0 = g[0]
            r1 = g[-1] + 1
            visited[r0:r1, :] = True
            regions.append([
                int(round(r0 * 1000 / R)),
                0,
                int(round(r1 * 1000 / R)),
                1000,
            ])

    # 2. Find any remaining large contiguous calm blocks (min 3 rows x 4 cols)
    for r in range(R):
        for c in range(C):
            if mask[r, c] and not visited[r, c]:
                # Expand rectangle
                r_max = r
                while r_max < R and mask[r_max, c] and not visited[r_max, c]:
                    r_max += 1
                c_max = c
                while c_max < C and np.all(mask[r:r_max, c_max]) and not np.any(visited[r:r_max, c_max]):
                    c_max += 1

                if (r_max - r) >= 2 and (c_max - c) >= 3:
                    visited[r:r_max, c:c_max] = True
                    regions.append([
                        int(round(r * 1000 / R)),
                        int(round(c * 1000 / C)),
                        int(round(r_max * 1000 / R)),
                        int(round(c_max * 1000 / C)),
                    ])

    # Sort by area descending and return top <= 4
    regions.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    return regions[:4]
