"""Call Nano Banana Pro to produce state variants of a UI element.

Design:
  - State definitions live in JSON spec files under `app/specs/<component>.json`,
    following ChatForce's structured-prompt pattern. The spec drives BOTH the
    Gemini prompt (what to generate) AND cleanup enforcement (what to enforce).
  - States marked `"passthrough": true` reuse the source image directly — no
    Gemini call. This avoids re-render drift on the canonical resting state.
  - The prompt sent to Gemini is a structured JSON block (not prose). Gemini 3
    Pro reads JSON natively and follows structured specs more reliably than
    hand-tuned English sentences.
  - Source image dimensions are included in the prompt so Gemini knows the
    exact target size. Cleanup enforces this as a hard constraint.

Contract:
    generate_variants(source_png: bytes, component_type: str)
        -> dict[str, bytes]    # PNG bytes per state
"""

from __future__ import annotations

import io
import json
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
    """Produce state variants using the JSON spec for the given component.

    Returns a dict mapping state name -> PNG bytes. The canonical resting state
    is always present. Raises if any call fails or returns no image.
    """
    from app.main import settings

    spec = load_spec(component_type)

    # Get source dimensions for the prompt.
    with Image.open(io.BytesIO(source_png)) as src:
        src_w, src_h = src.size

    client = genai.Client(api_key=settings.gemini_api_key)
    results: dict[str, bytes] = {}

    for state, state_spec in spec["states"].items():
        if state_spec.get("passthrough"):
            results[state] = source_png
            continue

        prompt = _build_prompt(spec, state, state_spec, src_w, src_h)
        results[state] = _call_nano_banana(
            client=client,
            model=settings.gemini_image_model,
            prompt=prompt,
            reference_png=source_png,
            state=state,
        )

    return results


def _build_prompt(
    spec: dict,
    state: str,
    state_spec: dict,
    src_w: int,
    src_h: int,
) -> str:
    """Build a structured JSON prompt for Gemini from the spec.

    Passes the spec fields directly as JSON — Gemini 3 Pro reads structured
    data more reliably than prose. The source dimensions are injected so the
    model knows the exact target size.
    """
    prompt_payload = {
        "task": spec["task"],
        "state_to_generate": state,
        "state_description": state_spec.get("description", ""),
        "state_modifications": state_spec.get("modifications", {}),
        "reference_image_info": {
            "dimensions_px": f"{src_w}x{src_h}",
            "width": src_w,
            "height": src_h,
            "role": spec["reference_image"]["role"],
            "use_for": spec["reference_image"]["use_for"],
            "critical_note": spec["reference_image"].get("critical_note", ""),
        },
        "output_constraints": spec["output_constraints"],
        "forbidden_content": spec["forbidden_content"],
        "priority_rules": spec["priority_rules"],
    }

    return (
        "Generate the specified UI state variant based on the JSON specification "
        "below and the reference image provided. The output image MUST be exactly "
        f"{src_w}x{src_h} pixels with a transparent background.\n\n"
        f"```json\n{json.dumps(prompt_payload, indent=2)}\n```"
    )


def _call_nano_banana(
    *,
    client: genai.Client,
    model: str,
    prompt: str,
    reference_png: bytes,
    state: str,
) -> bytes:
    """One generation call. Returns PNG bytes for this state."""
    response = client.models.generate_content(
        model=model,
        contents=[
            prompt,
            types.Part.from_bytes(data=reference_png, mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return bytes(inline.data)

    raise RuntimeError(f"Nano Banana returned no image for state={state!r}")
