"""Call Nano Banana Pro to produce state variants of a UI element.

Design:
  - State definitions live in JSON spec files under `app/specs/<component>.json`,
    following ChatForce's structured-prompt pattern (task, reference_image roles,
    output_constraints, forbidden_content, priority_rules).
  - The spec drives BOTH the Gemini prompt AND cleanup enforcement downstream.
  - States marked `"passthrough": true` reuse the source image directly.
  - **Consistency chaining:** the FIRST generated (non-passthrough) state becomes
    the "consistency anchor". All subsequent calls receive TWO reference images:
      image 1 = source (STYLE_AND_SUBJECT_REFERENCE — what the element looks like)
      image 2 = anchor (CONSISTENCY_REFERENCE — what Gemini's interpretation
                actually looks like; match THIS, not a fresh interpretation)
    This is ChatForce's CONSISTENCY_REFERENCE pattern. It dramatically reduces
    cross-state drift in dimensions, rendering style, and color temperature.
  - A runtime context JSON is built per-run by analyzing the source image. It
    carries concrete numbers (dimensions, color palette, pixel-art flag) that
    get included in every prompt, then updated after the anchor is generated.

Contract:
    generate_variants(source_png: bytes, component_type: str)
        -> dict[str, bytes]
"""

from __future__ import annotations

import io
import json
from collections import Counter
from pathlib import Path

from PIL import Image
from google import genai
from google.genai import types

SPECS_DIR = Path(__file__).parent.parent / "specs"


def load_spec(component_type: str) -> dict:
    """Load the JSON spec for a component type."""
    path = SPECS_DIR / f"{component_type}.json"
    if not path.is_file():
        raise ValueError(
            f"No spec file for component_type={component_type!r}. "
            f"Expected: {path}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def generate_variants(source_png: bytes, component_type: str) -> dict[str, bytes]:
    """Produce state variants using the JSON spec + consistency chaining."""
    from app.main import settings

    spec = load_spec(component_type)
    runtime_ctx = _analyze_source(source_png)

    client = genai.Client(api_key=settings.gemini_api_key)
    results: dict[str, bytes] = {}

    anchor_png: bytes | None = None
    anchor_state: str | None = None

    for state, state_spec in spec["states"].items():
        if state_spec.get("passthrough"):
            results[state] = source_png
            continue

        # Build prompt with runtime context (includes anchor info if we have one).
        prompt = _build_prompt(
            spec=spec,
            state=state,
            state_spec=state_spec,
            runtime_ctx=runtime_ctx,
            anchor_state=anchor_state,
        )

        img_bytes = _call_nano_banana(
            client=client,
            model=settings.gemini_image_model,
            prompt=prompt,
            reference_png=source_png,
            anchor_png=anchor_png,
            state=state,
        )
        results[state] = img_bytes

        # First generated state becomes the consistency anchor for all others.
        if anchor_png is None:
            anchor_png = img_bytes
            anchor_state = state
            runtime_ctx["consistency_anchor"] = {
                "state_name": state,
                "role": "CONSISTENCY_REFERENCE",
                "use_for": [
                    "exact_dimensions",
                    "rendering_style",
                    "edge_treatment",
                    "color_temperature",
                    "level_of_detail",
                ],
                "critical_note": (
                    "Image 2 is a previously generated state variant. ALL subsequent "
                    "states MUST match its exact dimensions, rendering approach, edge "
                    "treatment, and level of detail. It is the ground truth for how "
                    "this model interpreted the source."
                ),
            }

    return results


# --- source analysis ----------------------------------------------------------


def _analyze_source(source_png: bytes) -> dict:
    """Extract concrete properties from the source image for the runtime context."""
    img = Image.open(io.BytesIO(source_png)).convert("RGBA")
    w, h = img.size

    # Dominant colors (top 8, ignoring fully transparent pixels).
    pixels = [
        (r, g, b)
        for r, g, b, a in img.getdata()
        if a > 20
    ]
    color_counts = Counter(pixels).most_common(8)
    dominant = [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in color_counts]

    # Pixel-art heuristic (mirrors cleanup.py).
    unique_colors = img.getcolors(maxcolors=65)
    is_pixel = (
        w <= 128
        and h <= 128
        and unique_colors is not None
        and len(unique_colors) <= 64
    )

    # Transparency check.
    alpha = img.split()[-1]
    has_alpha = alpha.getextrema()[0] < 255

    return {
        "source_analysis": {
            "dimensions_px": f"{w}x{h}",
            "width": w,
            "height": h,
            "aspect_ratio": f"{w}:{h}",
            "color_count": len(set(pixels)) if len(pixels) < 10000 else "many",
            "is_pixel_art": is_pixel,
            "has_alpha_transparency": has_alpha,
            "dominant_colors": dominant,
        }
    }


# --- prompt building ----------------------------------------------------------


def _build_prompt(
    *,
    spec: dict,
    state: str,
    state_spec: dict,
    runtime_ctx: dict,
    anchor_state: str | None,
) -> str:
    """Build a structured JSON prompt including runtime context.

    When an anchor exists, the prompt tells Gemini that image 2 is a
    CONSISTENCY_REFERENCE and must be matched exactly.
    """
    src = runtime_ctx["source_analysis"]

    prompt_payload = {
        "task": spec["task"],
        "state_to_generate": state,
        "state_description": state_spec.get("description", ""),
        "state_modifications": state_spec.get("modifications", {}),
        "reference_images": {
            "image_1": {
                "role": spec["reference_image"]["role"],
                "use_for": spec["reference_image"]["use_for"],
                "critical_note": spec["reference_image"].get("critical_note", ""),
                "dimensions_px": src["dimensions_px"],
            },
        },
        "source_analysis": src,
        "output_constraints": spec["output_constraints"],
        "forbidden_content": spec["forbidden_content"],
        "priority_rules": spec["priority_rules"],
    }

    # Add consistency anchor info when we have one.
    if anchor_state and "consistency_anchor" in runtime_ctx:
        prompt_payload["reference_images"]["image_2"] = runtime_ctx["consistency_anchor"]

    # Build the text preamble.
    w, h = src["width"], src["height"]

    if anchor_state:
        preamble = (
            "Generate the specified UI state variant. You are given TWO reference "
            "images:\n"
            "- Image 1: the ORIGINAL source element (style and subject reference)\n"
            f"- Image 2: a previously generated '{anchor_state}' state "
            "(CONSISTENCY REFERENCE — match its exact dimensions, rendering style, "
            "and level of detail)\n\n"
            f"The output MUST be exactly {w}x{h} pixels."
        )
    else:
        preamble = (
            "Generate the specified UI state variant based on the reference image "
            f"provided. The output MUST be exactly {w}x{h} pixels."
        )

    return f"{preamble}\n\n```json\n{json.dumps(prompt_payload, indent=2)}\n```"


# --- gemini call --------------------------------------------------------------


def _call_nano_banana(
    *,
    client: genai.Client,
    model: str,
    prompt: str,
    reference_png: bytes,
    anchor_png: bytes | None,
    state: str,
) -> bytes:
    """One generation call. Passes source + optional anchor as reference images."""
    contents: list = [
        prompt,
        types.Part.from_bytes(data=reference_png, mime_type="image/png"),
    ]
    if anchor_png is not None:
        contents.append(types.Part.from_bytes(data=anchor_png, mime_type="image/png"))

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return bytes(inline.data)

    raise RuntimeError(f"Nano Banana returned no image for state={state!r}")
