"""Normalise the variant set so downstream Godot code can trust the shapes.

Three stages, in order:
  1. Alpha-bbox trim — drop transparent padding Nano Banana likes to add.
  2. Align to max bbox — pad every variant to the largest trimmed size,
     centered, so they overlay cleanly (pressed vs normal differ in content,
     not in position).
  3. Pixel-art path (only when the SOURCE looks like pixel art):
       - nearest-neighbour downsample variants to the source's canvas size,
       - snap pixels to a palette derived from the source.

The source-image-drives-pixel-art-detection rule is deliberate: Nano Banana
outputs at high res regardless of input, so you can't detect pixel art from
the generated output alone — you have to remember what you asked for.

Contract:
    normalize_variants(variants, source_png=None) -> dict[str, bytes]
        # input and output keys match; values are re-encoded PNGs.
"""

from __future__ import annotations

import io

from PIL import Image


# Heuristic thresholds for "looks like pixel art". Tuned by feel, not data yet;
# revisit once we have a handful of real inputs that hit edge cases.
PIXEL_ART_MAX_COLORS = 64
PIXEL_ART_MAX_DIMENSION = 128


def normalize_variants(
    variants: dict[str, bytes],
    source_png: bytes | None = None,
) -> dict[str, bytes]:
    """Return trimmed, aligned, optionally pixel-snapped PNG bytes per state."""
    if not variants:
        return {}

    # 1. Decode everything to RGBA PIL images.
    images: dict[str, Image.Image] = {
        state: Image.open(io.BytesIO(png)).convert("RGBA") for state, png in variants.items()
    }

    # 2. Trim each by alpha bbox. If a variant is fully transparent we keep
    #    it as-is rather than crashing — surfacing the bug is better than
    #    silently dropping it.
    trimmed = {state: _alpha_trim(img) for state, img in images.items()}

    # 3. Pad all to the max trimmed size, centered.
    max_w = max(img.width for img in trimmed.values())
    max_h = max(img.height for img in trimmed.values())
    aligned = {state: _center_pad(img, max_w, max_h) for state, img in trimmed.items()}

    # 4. Pixel-art branch.
    if source_png is not None:
        source_img = Image.open(io.BytesIO(source_png)).convert("RGBA")
        if _looks_like_pixel_art(source_img):
            aligned = _apply_pixel_art_treatment(aligned, source_img)

    # 5. Encode back to PNG bytes.
    return {state: _to_png_bytes(img) for state, img in aligned.items()}


# --- helpers ------------------------------------------------------------------


def _alpha_trim(img: Image.Image) -> Image.Image:
    """Crop to the alpha bounding box. Returns the image unchanged if fully opaque or fully blank."""
    alpha = img.split()[-1]
    bbox = alpha.getbbox()
    return img.crop(bbox) if bbox else img


def _center_pad(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Return a new RGBA image of target_w × target_h with img centered on transparent."""
    if img.size == (target_w, target_h):
        return img
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    offset = ((target_w - img.width) // 2, (target_h - img.height) // 2)
    canvas.paste(img, offset, img)
    return canvas


def _looks_like_pixel_art(img: Image.Image) -> bool:
    """Cheap heuristic: few unique colors AND small canvas."""
    small_canvas = img.width <= PIXEL_ART_MAX_DIMENSION and img.height <= PIXEL_ART_MAX_DIMENSION
    if not small_canvas:
        return False
    colors = img.getcolors(maxcolors=PIXEL_ART_MAX_COLORS + 1)
    return colors is not None and len(colors) <= PIXEL_ART_MAX_COLORS


def _looks_like_pixel_art_bytes_from_source(png: bytes) -> bool:
    """Public-ish helper: same heuristic, but from raw PNG bytes.

    Used by the HTTP layer to surface an `is_pixel_art` flag to the web UI
    (for choosing CSS `image-rendering` mode on preview) without re-reading
    the file downstream.
    """
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    return _looks_like_pixel_art(img)


def _apply_pixel_art_treatment(
    aligned: dict[str, Image.Image],
    source_img: Image.Image,
) -> dict[str, Image.Image]:
    """Downsample every variant to source dimensions (nearest-neighbour) and quantise to source palette."""
    target_size = source_img.size
    # PIL's quantize needs a P-mode image as the palette source.
    palette_img = source_img.convert("RGB").quantize(colors=PIXEL_ART_MAX_COLORS)

    snapped: dict[str, Image.Image] = {}
    for state, img in aligned.items():
        # Nearest-neighbour downsample to preserve the crunchy look.
        small = img.resize(target_size, Image.Resampling.NEAREST)
        # Quantise RGB channels against the source palette, then re-attach alpha
        # (quantize drops the alpha channel).
        alpha = small.split()[-1]
        snapped_rgb = small.convert("RGB").quantize(palette=palette_img).convert("RGB")
        result = Image.merge("RGBA", (*snapped_rgb.split(), alpha))
        snapped[state] = result
    return snapped


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
