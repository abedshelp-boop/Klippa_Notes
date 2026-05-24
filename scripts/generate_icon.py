"""One-shot script: generate build/icon.ico and assets/icon-256.png from the
same design as assets/logo.svg (kept in sync by hand).

Run: python scripts/generate_icon.py
Requires: Pillow.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ICON_OUT = PROJECT / "build" / "icon.ico"
PNG_OUT = PROJECT / "assets" / "icon-256.png"

SIZES = [256, 128, 64, 48, 32, 24, 16]

BG_DARK = (10, 10, 14, 255)
BG_LIGHT = (28, 28, 34, 255)
FG = (255, 255, 255, 255)
RIM = (255, 255, 255, 36)
SPARKLE = (255, 255, 255, 235)


def draw_icon(size: int) -> Image.Image:
    """Render the logo at the requested square size."""
    # Oversample for crisp edges, then downscale with LANCZOS.
    scale = 4 if size >= 32 else 6
    s = size * scale

    # 1. Background: solid dark, with a soft highlight in upper-left.
    bg = Image.new("RGBA", (s, s), BG_DARK)
    highlight = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight)
    hd.ellipse(
        [-s * 0.20, -s * 0.20, s * 0.85, s * 0.85],
        fill=BG_LIGHT,
    )
    highlight = highlight.filter(ImageFilter.GaussianBlur(s * 0.18))
    bg = Image.alpha_composite(bg, highlight)

    # 2. Round-corner mask: outside corners → transparent.
    radius = int(s * 0.22)
    rect_mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(rect_mask).rounded_rectangle(
        [0, 0, s - 1, s - 1], radius=radius, fill=255,
    )

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(bg, (0, 0), rect_mask)

    # 3. Inner rim highlight along the rounded edge.
    rim_w = max(1, scale)
    ImageDraw.Draw(img).rounded_rectangle(
        [rim_w / 2, rim_w / 2, s - rim_w / 2 - 1, s - rim_w / 2 - 1],
        radius=radius - rim_w / 2,
        outline=RIM,
        width=rim_w,
    )

    # 4. D mask. Stem rectangle + right-half ellipse for bowl (via pieslice
    # so the flat diameter lines up cleanly with the stem's right edge).
    def vb(v: float) -> float:
        return v * s / 64.0

    d_mask = Image.new("L", (s, s), 0)
    dmd = ImageDraw.Draw(d_mask)
    cx, cy = vb(22), vb(32)
    # Stem.
    dmd.rectangle([vb(16), vb(14), vb(22), vb(50)], fill=255)
    # Bowl outer (right half).
    rx_out, ry_out = vb(20), vb(18)
    dmd.pieslice(
        [cx - rx_out, cy - ry_out, cx + rx_out, cy + ry_out],
        start=-90, end=90, fill=255,
    )
    # Bowl inner cutout (right half) — fill=0 erases the inner area.
    rx_in, ry_in = vb(11), vb(11)
    dmd.pieslice(
        [cx - rx_in, cy - ry_in, cx + rx_in, cy + ry_in],
        start=-90, end=90, fill=0,
    )

    # 5. Paint white through the D mask. Pixels outside the mask are
    # untouched, so the dark background under the D is preserved (this was
    # the bug in v1: pasting an RGBA bowl image with a binary crop mask
    # punched holes in the background where the bowl had alpha=0).
    white_layer = Image.new("RGBA", (s, s), FG)
    img.paste(white_layer, (0, 0), d_mask)

    # 6. Sparkle accent in upper-right.
    sx, sy = vb(50), vb(14)
    arm = vb(3.0)
    waist = vb(1.2)
    ImageDraw.Draw(img).polygon(
        [
            (sx, sy - arm),
            (sx + waist, sy - waist),
            (sx + arm, sy),
            (sx + waist, sy + waist),
            (sx, sy + arm),
            (sx - waist, sy + waist),
            (sx - arm, sy),
            (sx - waist, sy - waist),
        ],
        fill=SPARKLE,
    )

    if scale != 1:
        img = img.resize((size, size), Image.LANCZOS)
    return img


def main() -> None:
    ICON_OUT.parent.mkdir(parents=True, exist_ok=True)
    PNG_OUT.parent.mkdir(parents=True, exist_ok=True)

    images = {s: draw_icon(s) for s in SIZES}
    images[256].save(PNG_OUT, format="PNG")
    images[256].save(
        ICON_OUT,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
    )
    print(f"Wrote {ICON_OUT} ({ICON_OUT.stat().st_size} bytes) "
          f"and {PNG_OUT} ({PNG_OUT.stat().st_size} bytes).")


if __name__ == "__main__":
    main()
