#!/usr/bin/env python3
"""Render og.png (1200x630) for The Dataset Index — "archival / data-grid" card.
Bone-paper specimen sheet, vermillion accent, a cell-grid motif, heavy grotesque title.
Pillow only; graceful fallback if unavailable."""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BG = (245, 246, 248)
INK = (25, 28, 35)
MUTED = (91, 98, 112)
VERM = (79, 70, 229)
GRID = (226, 229, 235)
CELL = (203, 209, 220)


def _font(paths, size):
    from PIL import ImageFont
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def main() -> int:
    try:
        from PIL import Image, ImageDraw
    except Exception:
        print("Pillow not available — skipping og.png")
        return 0
    try:
        data = json.load(open(os.path.join(HERE, "data.json"), encoding="utf-8"))
        count, cats = data.get("count", 0), len(data.get("categories", []))
    except Exception:
        count, cats = 0, 0

    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # faint specimen grid
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=GRID, width=1)

    bold = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    mono = ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
    f_h1 = _font(bold, 92)
    f_kick = _font(mono, 24)
    f_stat = _font(mono, 27)

    # cell-grid mark (3x3, diagonal vermillion) + wordmark
    gx, gy, s, g = 70, 74, 16, 4
    diag = {(0, 0), (1, 1), (2, 2)}
    for r in range(3):
        for c in range(3):
            col = VERM if (r, c) in diag else CELL
            d.rounded_rectangle([gx + c * (s + g), gy + r * (s + g), gx + c * (s + g) + s, gy + r * (s + g) + s], radius=3, fill=col)
    d.text((gx + 3 * (s + g) + 14, gy + 14), "THE DOCUMENT INDEX", font=f_kick, fill=MUTED)

    # heavy title — "scanned." in indigo
    d.text((66, 188), "The document-AI", font=f_h1, fill=INK)
    d.text((66, 296), "stack, ", font=f_h1, fill=INK)
    try:
        w_stack = d.textlength("stack, ", font=f_h1)
    except Exception:
        w_stack = 300
    d.text((66 + w_stack, 296), "scanned.", font=f_h1, fill=VERM)

    # a row of data cells (motif) + stats
    cy = 452
    for i in range(36):
        col = VERM if i % 6 == 0 else CELL
        d.rounded_rectangle([70 + i * 30, cy, 70 + i * 30 + 20, cy + 20], radius=3, fill=col if i < 30 else GRID)
    d.text((70, 540), f"{count} tools  ·  {cats} categories  ·  ranked daily by GitHub momentum",
           font=f_stat, fill=MUTED)

    img.save(os.path.join(HERE, "og.png"))
    print(f"wrote og.png ({count} tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
