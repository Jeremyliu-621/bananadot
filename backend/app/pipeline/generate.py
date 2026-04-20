"""Call Nano Banana Pro to produce state variants of a UI element.

Design:
  - State definitions live in JSON spec files under `app/specs/<component>.json`,
    following ChatForce's structured-prompt pattern (task, reference_image roles,
    output_constraints, forbidden_content, priority_rules).
  - The spec drives BOTH the Gemini prompt AND cleanup enforcement downstream.
  - EVERY state goes through Gemini, including "normal". A previous iteration
    treated "normal" as a source-passthrough, but that made it the odd one
    out — normal kept the source's original canvas/padding while the other
    states came back tightly trimmed, so they visibly differed in size.
    Regenerating normal through the same path as everything else keeps the
    whole set coherent.

Reference images (1, 2, or 3 per call, in this order):
  image_1 — SOURCE: always present. STYLE_AND_SUBJECT_REFERENCE — what the
           element looks like (its shape, content, intended style).
  image_2 — CONSISTENCY_ANCHOR: present after the first state is generated.
           ChatForce's pattern for reducing cross-state drift — subsequent
           states must match its exact dimensions, rendering style, and
           level of detail.
  image_3 — STYLE_FAMILY_REFERENCE: present only during kit generation.
           A different component in the visual style we want — Gemini copies
           its rendering language (art, palette, detail) but NOT its shape.

Runtime context:
  Per-run JSON built by `_analyze_source` carries concrete numbers (dimensions,
  color palette, pixel-art flag) that get included in every prompt. The
  consistency-anchor block is added to this context after the first state.

Contract:
    generate_variants(
        source_png, component_type,
        style_reference_png=None,   # enables kit-generation mode
    ) -> dict[str, bytes]
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


# --- spec loading --------------------------------------------------------------


def load_spec(component_type: str) -> dict:
    """Load the JSON spec for a component type."""
    path = SPECS_DIR / f"{component_type}.json"
    if not path.is_file():
        raise ValueError(
            f"No spec file for component_type={component_type!r}. "
            f"Expected: {path}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


# --- main entry ----------------------------------------------------------------


def generate_variants(
    source_png: bytes,
    component_type: str,
    kit_mode: bool = False,
    shape_guidance: bool = True,
) -> dict[str, bytes]:
    """Produce state variants using the JSON spec + consistency chaining.

    Two modes:

    * Normal (`kit_mode=False`, default): the uploaded image IS the element
      we're generating states for. Source is passed to Gemini as the
      STYLE_AND_SUBJECT reference — "make the hover/pressed/disabled states
      of THIS thing."

    * Kit mode (`kit_mode=True`): we're generating a DIFFERENT component
      type that should match the uploaded image's visual style. Source is
      passed as STYLE_FAMILY_REFERENCE only — "invent a new <component_type>
      that renders in the same art style as this image, don't copy its
      shape." This prevents the "upload a checkbox, get a button that's
      secretly just the checkbox again" failure mode.

    `shape_guidance` only matters in kit mode. When True (default), the
    target's `shape_profile` block from its spec (typical aspect ratio,
    required visual features, what it must not look like) is injected into
    the prompt so Gemini produces a proper button shape / panel frame /
    etc. Toggle off for pure style transfer — the family will copy the
    reference's silhouette more faithfully but may not read as the right
    component type.
    """
    from app.main import settings

    spec = load_spec(component_type)
    runtime_ctx = _analyze_source(source_png)

    client = genai.Client(api_key=settings.gemini_api_key)
    results: dict[str, bytes] = {}

    anchor_png: bytes | None = None
    anchor_state: str | None = None

    for state, state_spec in spec["states"].items():
        # Every state goes through Gemini (no passthrough branch). See module docstring.
        if kit_mode:
            # Single reference image: the source, but relabelled as style-only.
            # No separate STYLE_AND_SUBJECT image — that was the bug: showing
            # the source twice with contradictory roles made Gemini copy it
            # literally instead of inventing a new silhouette.
            image_refs: list[tuple[bytes, dict]] = [
                (source_png, _style_family_meta_for_kit(component_type)),
            ]
            if anchor_png is not None and runtime_ctx.get("consistency_anchor"):
                image_refs.append((anchor_png, runtime_ctx["consistency_anchor"]))
        else:
            image_refs = _collect_image_refs(
                source_png=source_png,
                source_meta=_source_meta(spec, runtime_ctx),
                anchor_png=anchor_png,
                anchor_meta=runtime_ctx.get("consistency_anchor"),
                style_reference_png=None,
                style_reference_meta=None,
            )

        prompt = _build_prompt(
            spec=spec,
            state=state,
            state_spec=state_spec,
            runtime_ctx=runtime_ctx,
            image_refs=image_refs,
            kit_mode=kit_mode,
            component_type=component_type,
            shape_guidance=shape_guidance,
        )

        img_bytes = _call_nano_banana(
            client=client,
            model=settings.gemini_image_model,
            prompt=prompt,
            image_pngs=[png for png, _ in image_refs],
            state=state,
        )
        results[state] = img_bytes

        # First generated state becomes the consistency anchor for all others.
        if anchor_png is None:
            anchor_png = img_bytes
            anchor_state = state
            runtime_ctx["consistency_anchor"] = _anchor_meta(state)

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


# --- image-ref collection ------------------------------------------------------


def _source_meta(spec: dict, runtime_ctx: dict) -> dict:
    """Metadata block for image_1 (the source)."""
    return {
        "role": spec["reference_image"]["role"],
        "use_for": spec["reference_image"]["use_for"],
        "critical_note": spec["reference_image"].get("critical_note", ""),
        "dimensions_px": runtime_ctx["source_analysis"]["dimensions_px"],
    }


def _anchor_meta(state_name: str) -> dict:
    """Metadata block for image_2 (the consistency anchor). Added after first gen."""
    return {
        "state_name": state_name,
        "role": "CONSISTENCY_REFERENCE",
        "use_for": [
            "exact_dimensions",
            "rendering_style",
            "edge_treatment",
            "color_temperature",
            "level_of_detail",
        ],
        "critical_note": (
            "This image is a previously generated state variant. ALL subsequent "
            "states MUST match its exact dimensions, rendering approach, edge "
            "treatment, and level of detail. It is the ground truth for how "
            "this model interpreted the source."
        ),
    }


def _style_family_meta() -> dict:
    """Generic style-family metadata (used when kit mode is not explicit)."""
    return {
        "role": "STYLE_FAMILY_REFERENCE",
        "use_for": [
            "art_style",
            "color_palette",
            "rendering_technique",
            "level_of_detail",
            "line_weight_and_edge_treatment",
        ],
        "must_not_extract": [
            "silhouette",
            "subject_content",
            "specific_shape",
            "dimensions",
        ],
        "critical_note": (
            "This image is a DIFFERENT component type in the visual style you "
            "must match. Copy its rendering language (art style, colors, "
            "detail) but NOT its shape or subject — the current generation is "
            "for a different component entirely and must have its own correct "
            "silhouette, not this reference's."
        ),
    }


def _style_family_meta_for_kit(target_component_type: str) -> dict:
    """Kit-mode metadata — the source image is ONLY a style guide.

    Emphatic `must_not_extract` and a per-component-type critical note so
    Gemini can't drift back into 'just copy the reference'. This is the block
    that fixes the 'upload a checkbox, get a button that IS the checkbox' bug.
    """
    return {
        "role": "STYLE_FAMILY_REFERENCE",
        "use_for": [
            "art_style",
            "color_palette",
            "rendering_technique",
            "level_of_detail",
            "line_weight_and_edge_treatment",
            "texture_and_material",
        ],
        "must_not_extract": [
            "silhouette",
            "subject_content",
            "specific_shape",
            "component_type",
            "dimensions",
            "aspect_ratio",
        ],
        "critical_note": (
            f"This image is a DIFFERENT UI component type from what you are "
            f"generating. You are generating a {target_component_type!r} and "
            f"MUST invent a new {target_component_type} silhouette from "
            f"scratch. Do NOT copy this image's shape, outline, or subject. "
            f"Use it ONLY for art style, colour palette, line weight, edge "
            f"treatment, and overall rendering feel. The output must clearly "
            f"read as a {target_component_type}, not as whatever this image is."
        ),
    }


def _collect_image_refs(
    *,
    source_png: bytes,
    source_meta: dict,
    anchor_png: bytes | None,
    anchor_meta: dict | None,
    style_reference_png: bytes | None,
    style_reference_meta: dict | None,
) -> list[tuple[bytes, dict]]:
    """Collect the ordered (png, meta) pairs for this generation call.

    Order: source -> anchor (if any) -> style_family_ref (if any).
    """
    refs: list[tuple[bytes, dict]] = [(source_png, source_meta)]
    if anchor_png is not None and anchor_meta is not None:
        refs.append((anchor_png, anchor_meta))
    if style_reference_png is not None and style_reference_meta is not None:
        refs.append((style_reference_png, style_reference_meta))
    return refs


# --- prompt building ----------------------------------------------------------


def _build_prompt(
    *,
    spec: dict,
    state: str,
    state_spec: dict,
    runtime_ctx: dict,
    image_refs: list[tuple[bytes, dict]],
    kit_mode: bool = False,
    component_type: str | None = None,
    shape_guidance: bool = True,
) -> str:
    """Build the structured JSON prompt + human-readable preamble.

    `image_refs` is the same list passed to _call_nano_banana; the prompt keys
    each metadata block as image_1, image_2, ... in the same order.
    """
    src = runtime_ctx["source_analysis"]

    reference_images = {
        f"image_{i + 1}": meta for i, (_, meta) in enumerate(image_refs)
    }

    prompt_payload: dict = {
        "task": spec["task"],
        "state_to_generate": state,
        "state_description": state_spec.get("description", ""),
        "state_modifications": state_spec.get("modifications", {}),
        "reference_images": reference_images,
        "source_analysis": src,
        "output_constraints": spec["output_constraints"],
        "forbidden_content": spec["forbidden_content"],
        "priority_rules": spec["priority_rules"],
    }

    if kit_mode and component_type:
        # Extra kit-specific framing in the structured payload so it's
        # impossible to miss — belt AND suspenders for the preamble text.
        prompt_payload["kit_mode_notice"] = {
            "target_component_type": component_type,
            "instruction": (
                f"You are generating a NEW {component_type} in the visual "
                "style of the reference image. The reference image is a "
                "DIFFERENT component type — do NOT copy its silhouette, "
                "shape, or subject. Invent an appropriate "
                f"{component_type} silhouette from scratch."
            ),
        }
        # When shape guidance is on, inject the target's shape_profile so
        # Gemini has concrete geometric constraints (aspect ratio, required
        # features, shapes to avoid). Purely shape/role info — no style
        # guidance — so it doesn't blunt the reference-driven art direction.
        if shape_guidance and "shape_profile" in spec:
            prompt_payload["target_shape_profile"] = spec["shape_profile"]

    preamble = _build_preamble(
        state=state,
        w=src["width"],
        h=src["height"],
        image_refs=image_refs,
        kit_mode=kit_mode,
        component_type=component_type,
    )
    return f"{preamble}\n\n```json\n{json.dumps(prompt_payload, indent=2)}\n```"


def _build_preamble(
    *,
    state: str,
    w: int,
    h: int,
    image_refs: list[tuple[bytes, dict]],
    kit_mode: bool = False,
    component_type: str | None = None,
) -> str:
    """Human-readable preamble describing what each attached image is for."""

    # Kit mode gets its own preamble because the framing is fundamentally
    # different: "invent a new X" rather than "generate states of THIS thing".
    if kit_mode and component_type:
        lines = [
            f"Generate a NEW {component_type} for the '{state}' state.",
            "",
            f"The reference image is a DIFFERENT UI component type (e.g. a "
            f"checkbox when you're generating a {component_type}). It is "
            "provided ONLY as a style guide — copy its colour palette, line "
            "weight, edge treatment, level of detail, and overall rendering "
            "feel. Do NOT copy its silhouette, shape, or subject.",
            "",
            f"You MUST invent an appropriate {component_type} silhouette "
            f"from scratch. The output must clearly read as a "
            f"{component_type}, not as a copy of the reference image.",
        ]
        if len(image_refs) > 1:
            for i, (_, meta) in enumerate(image_refs[1:], start=2):
                if meta.get("role") == "CONSISTENCY_REFERENCE":
                    lines.append("")
                    lines.append(
                        f"Image {i}: a previously generated "
                        f"'{meta.get('state_name', '?')}' state of the "
                        f"{component_type} you are building — match its "
                        "exact dimensions, silhouette, and rendering style."
                    )
        lines.append("")
        lines.append(f"The output MUST be exactly {w}x{h} pixels.")
        return "\n".join(lines)

    # Normal mode: what we had before.
    n = len(image_refs)
    if n == 1:
        return (
            "Generate the specified UI state variant based on the reference "
            f"image provided. The output MUST be exactly {w}x{h} pixels."
        )

    lines = [f"Generate the specified UI state variant. You are given {n} reference images:"]
    for i, (_, meta) in enumerate(image_refs, start=1):
        role = meta.get("role", "REFERENCE")
        if role == "CONSISTENCY_REFERENCE":
            lines.append(
                f"- Image {i}: a previously generated '{meta.get('state_name', '?')}' "
                "state (CONSISTENCY REFERENCE — match its exact dimensions, rendering "
                "style, and level of detail)"
            )
        elif role == "STYLE_FAMILY_REFERENCE":
            lines.append(
                f"- Image {i}: a DIFFERENT component in the visual style you must match "
                "(STYLE FAMILY REFERENCE — copy its rendering language, NOT its shape "
                "or subject)"
            )
        else:
            lines.append(
                f"- Image {i}: the ORIGINAL source element (style and subject reference)"
            )
    lines.append("")
    lines.append(f"The output MUST be exactly {w}x{h} pixels.")
    return "\n".join(lines)


# --- gemini call --------------------------------------------------------------


def _call_nano_banana(
    *,
    client: genai.Client,
    model: str,
    prompt: str,
    image_pngs: list[bytes],
    state: str,
) -> bytes:
    """One generation call. Images are attached in the order given."""
    contents: list = [prompt]
    for png in image_pngs:
        contents.append(types.Part.from_bytes(data=png, mime_type="image/png"))

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


# --- variant feature ----------------------------------------------------------


def apply_modification(
    source_png: bytes,
    modification: str,
    component_type: str,
    *,
    variation_label: str | None = None,
) -> bytes:
    """Apply a single text-described modification to the source image.

    Returns a new PNG that is 'like the source but with [modification] applied.'
    Used as the pre-step for the /variant flow, and as the per-option worker
    for /variant/options (batch). `variation_label`, when set, gets appended
    to the prompt so parallel calls produce subtly different candidates.

    Same dimensions, same style, same everything else — only the requested
    change is applied.
    """
    from app.main import settings

    with Image.open(io.BytesIO(source_png)) as src:
        src_w, src_h = src.size

    base_prompt = (
        "Reproduce the reference image EXACTLY — same art style, same colors, "
        "same frames/borders, same dimensions, same level of detail — but "
        f"apply this single modification: {modification.strip()}\n\n"
        f"The output MUST be exactly {src_w}x{src_h} pixels. "
        "Do not change anything else about the image besides the requested "
        f"modification. This is a {component_type}; preserve its overall "
        "shape and function."
    )
    prompt = (
        f"{base_prompt}\n\nVariation tag: {variation_label}. Introduce a small, "
        "unique creative interpretation so this candidate differs subtly from "
        "sibling candidates (slightly different color temperature, line weight, "
        "or detail emphasis) while still obeying all constraints above."
    ) if variation_label else base_prompt

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_image_model,
        contents=[
            prompt,
            types.Part.from_bytes(data=source_png, mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return bytes(inline.data)

    raise RuntimeError("Nano Banana returned no image for the modification step")
