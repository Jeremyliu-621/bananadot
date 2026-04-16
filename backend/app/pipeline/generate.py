"""Call Nano Banana Pro to produce state variants of a UI element.

Design:
  - Every variant — including "normal" — goes through Nano Banana with the
    user's source image as the reference. All variants come from the same
    generation family, so stylistic drift between states is uniform rather
    than showing a jarring seam between the raw source (if used as "normal")
    and the generated others.
  - One prompt template per state, no art-style branching. The source IS
    the style anchor — Nano Banana Pro matches it from the reference image.
  - Pixel-art-specific fixes live downstream in cleanup.py as post-processing.

Contract:
    generate_variants(source_png: bytes, component_type: str)
        -> dict[str, bytes]    # PNG bytes per state

Component type → states lookup lives in STATE_INSTRUCTIONS below. Add new
component types there; the rest of the pipeline is state-agnostic.
"""

from __future__ import annotations

from google import genai
from google.genai import types


STATE_INSTRUCTIONS: dict[str, dict[str, str]] = {
    "button": {
        "normal": (
            "Render this exact button in the same art style, same palette, same silhouette. "
            "Clean edges, transparent background. This is the canonical 'normal' resting state."
        ),
        "hover": (
            "Same button, hover state. Slightly brighter overall, a subtle raised-highlight feel. "
            "Silhouette and palette must stay identical to the source so it overlays cleanly."
        ),
        "pressed": (
            "Same button, pressed state. Shift the top highlight to a bottom shadow, move the "
            "inner face 1-2 pixels down to read as 'pushed in'. Outer silhouette must not change."
        ),
        "disabled": (
            "Same button, disabled state. Desaturated, slightly faded, lower contrast. "
            "Same silhouette, palette family derived from the source."
        ),
    },
    "panel": {
        "normal": (
            "Render this exact panel in the same art style, same palette, same edge treatment. "
            "Clean edges, transparent background. Must tile cleanly as a 9-slice background."
        ),
    },
    "checkbox": {
        "unchecked": (
            "Render this exact checkbox in the same art style, unchecked (empty) state. "
            "Transparent background, clean edges."
        ),
        "checked": (
            "Same checkbox, checked state — same box, now with a check-mark or filled indicator "
            "in a style matching the source art. Outer box silhouette must not change."
        ),
    },
    "progress_bar": {
        "empty": (
            "Render this exact progress bar, empty (0%% filled). Same style, same palette, "
            "transparent background."
        ),
        "full": (
            "Same progress bar, fully filled (100%%). Same outer frame, fill style matching "
            "the source art."
        ),
    },
}


def generate_variants(source_png: bytes, component_type: str) -> dict[str, bytes]:
    """Produce state variants for the given component.

    Returns a dict mapping state name -> PNG bytes. `normal` (or the component's
    canonical resting state) is always present. Raises if any call fails or
    returns no image — we'd rather surface the error than ship a partial set.
    """
    # Import settings lazily so the module is testable without env vars loaded.
    from app.main import settings

    try:
        states = STATE_INSTRUCTIONS[component_type]
    except KeyError as e:
        raise ValueError(f"Unknown component_type: {component_type!r}") from e

    client = genai.Client(api_key=settings.gemini_api_key)
    results: dict[str, bytes] = {}

    for state, prompt in states.items():
        results[state] = _call_nano_banana(
            client=client,
            model=settings.gemini_image_model,
            prompt=prompt,
            reference_png=source_png,
            state=state,
        )

    return results


def _call_nano_banana(
    *,
    client: genai.Client,
    model: str,
    prompt: str,
    reference_png: bytes,
    state: str,
) -> bytes:
    """One generation call. Returns PNG bytes for this state.

    We pass the source image as a reference part alongside the text prompt;
    Nano Banana Pro uses it as the style and silhouette anchor.
    """
    response = client.models.generate_content(
        model=model,
        contents=[
            prompt,
            types.Part.from_bytes(data=reference_png, mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    # Walk the response for inline image data. Nano Banana can return multiple
    # parts (text narration + image); we want the first image part.
    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return bytes(inline.data)

    raise RuntimeError(f"Nano Banana returned no image for state={state!r}")
