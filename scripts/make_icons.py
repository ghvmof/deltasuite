"""Generate the DeltaSuite app icon as ``.ico``, ``.png`` and ``.icns``.

The icon is drawn programmatically with Pillow so the wheel/installer
does not depend on any binary asset committed to git. The motif is a
white triangle (Greek Delta) over a teal-to-blue radial gradient meant
to evoke water and bathymetry.

Output files
------------
``installer/branding/icon.ico``
    Multi-resolution Windows icon (16, 24, 32, 48, 64, 128, 256 px).
``installer/branding/icon.png``
    256 px PNG used by Linux desktops and the Sphinx site.
``installer/branding/icon-1024.png``
    Hi-res PNG; convert to ``.icns`` on macOS via ``iconutil``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUTPUT_DIR = Path("installer/branding")
SIZES_ICO = (16, 24, 32, 48, 64, 128, 256)


def _radial_gradient(size: int) -> Image.Image:
    """Return a square radial-gradient background, teal centre to navy edge."""
    image = Image.new("RGB", (size, size), (12, 30, 65))
    pixels = image.load()
    assert pixels is not None
    centre = size / 2
    max_dist = (centre**2 + centre**2) ** 0.5
    for y in range(size):
        for x in range(size):
            dist = ((x - centre) ** 2 + (y - centre) ** 2) ** 0.5
            t = min(1.0, dist / max_dist)
            r = int(33 * (1 - t) + 12 * t)
            g = int(118 * (1 - t) + 30 * t)
            b = int(154 * (1 - t) + 65 * t)
            pixels[x, y] = (r, g, b)
    return image


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
    return mask


def _draw_delta(image: Image.Image, size: int) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    margin = size * 0.18
    triangle = [
        (size / 2, margin),
        (size - margin, size - margin),
        (margin, size - margin),
    ]
    # Soft outer glow.
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.polygon(triangle, fill=(255, 255, 255, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=size * 0.04))
    image.alpha_composite(glow)
    # Solid white delta on top.
    draw.polygon(triangle, fill=(255, 255, 255, 245))


def _make_square(size: int) -> Image.Image:
    base = _radial_gradient(size).convert("RGBA")
    rounded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rounded.paste(base, mask=_rounded_mask(size, radius=int(size * 0.18)))
    _draw_delta(rounded, size)
    return rounded


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    largest = _make_square(1024)
    largest.save(OUTPUT_DIR / "icon-1024.png", "PNG")

    png_256 = _make_square(256)
    png_256.save(OUTPUT_DIR / "icon.png", "PNG")

    ico_layers = [_make_square(s) for s in SIZES_ICO]
    ico_layers[0].save(
        OUTPUT_DIR / "icon.ico",
        format="ICO",
        sizes=[(im.width, im.height) for im in ico_layers],
        append_images=ico_layers[1:],
    )
    print(f"Wrote: {OUTPUT_DIR / 'icon.ico'}")
    print(f"Wrote: {OUTPUT_DIR / 'icon.png'}")
    print(f"Wrote: {OUTPUT_DIR / 'icon-1024.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
