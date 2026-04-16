"""Normalise the variant set so downstream Godot code can trust the shapes.

Approach:
  1. Alpha-bbox trim every variant — drop transparent padding NB adds.
  2. Pick the target canvas size:
       - source_png provided → use source's own alpha-trimmed bbox.
         This is the canonical "logical size" the user cropped to, and it's
         the only size that's invariant across Nano Banana's call-to-call
         output resolution jitter.
       - no source_png → fall back to the max trimmed size across variants.
  3. Fit each trimmed variant into the target canvas preserving aspect ratio
     (downscale or upscale as needed, centre on transparent). Per-variant
     resampling: nearest for pixel art, Lanczos otherwise.
  4. Pixel-art branch (only when source looks like pixel art):
     quantise each variant's RGB against a palette derived from the source,
     re-attach the alpha channel. Locks the colour set and hides any
     subtle drift NB introduced.

Why align to source bbox instead of max-across-variants:
  Previously one bad variant (e.g. NB returning an opaque white plate for
  "normal") blew up its alpha bbox to the full 1024×1024 output, which
  pulled the max up, which made every other variant's effective content
  region proportionally tiny after the pixel-art downsample. Grounding
  alignment in the source dimensions makes the whole pipeline robust to
  one-off NB weirdness — a bloated variant just gets cropped, rather than
  distorting the entire set.

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
    """Return trimmed, fitted, optionally palette-snapped PNG bytes per state."""
    if not variants:
        return {}

    images = {s: Image.open(io.BytesIO(p)).convert("RGBA") for s, p in variants.items()}
    trimmed = {s: _alpha_trim(img) for s, img in images.items()}

    # Decide target canvas + resampling mode.
    source_img: Image.Image | None = None
    is_pixel = False
    if source_png is not None:
        source_img = Image.open(io.BytesIO(source_png)).convert("RGBA")
        is_pixel = _looks_like_pixel_art(source_img)
        source_trimmed = _alpha_trim(source_img)
        target_w, target_h = source_trimmed.size
    else:
        target_w = max(img.width for img in trimmed.values())
        target_h = max(img.height for img in trimmed.values())

    resample = Image.Resampling.NEAREST if is_pixel else Image.Resampling.LANCZOS

    # Fit each variant to the canonical target, preserving aspect ratio.
    fitted = {
        state: _fit_to_canvas(img, target_w, target_h, resample=resample)
        for state, img in trimmed.items()
    }

    if is_pixel and source_img is not None:
        fitted = _apply_palette_snap(fitted, source_img)

    return {state: _to_png_bytes(img) for state, img in fitted.items()}


# --- helpers ------------------------------------------------------------------


def _alpha_trim(img: Image.Image) -> Image.Image:
    """Crop to the alpha bounding box. Returns the image unchanged if fully opaque or fully blank."""
    alpha = img.split()[-1]
    bbox = alpha.getbbox()
    return img.crop(bbox) if bbox else img


def _fit_to_canvas(
    img: Image.Image,
    target_w: int,
    target_h: int,
    resample: Image.Resampling,
) -> Image.Image:
    """Scale img to fit within target_w × target_h preserving aspect ratio, centre on transparent."""
    if img.size == (target_w, target_h):
        return img
    src_w, src_h = img.size
    if src_w <= 0 or src_h <= 0:
        return Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    resized = img.resize((new_w, new_h), resample)
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    offset = ((target_w - new_w) // 2, (target_h - new_h) // 2)
    canvas.paste(resized, offset, resized)
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


def _apply_palette_snap(
    fitted: dict[str, Image.Image],
    source_img: Image.Image,
) -> dict[str, Image.Image]:
    """Quantise every variant's RGB channels against a palette derived from the source."""
    palette_img = source_img.convert("RGB").quantize(colors=PIXEL_ART_MAX_COLORS)

    snapped: dict[str, Image.Image] = {}
    for state, img in fitted.items():
        alpha = img.split()[-1]
        snapped_rgb = img.convert("RGB").quantize(palette=palette_img).convert("RGB")
        snapped[state] = Image.merge("RGBA", (*snapped_rgb.split(), alpha))
    return snapped


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
