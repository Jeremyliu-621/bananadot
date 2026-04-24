"""Call OpenAI's image model (gpt-image-2) to produce state variants of a UI element.

Design:
  - State definitions live in JSON spec files under `app/specs/<component>.json`,
    following ChatForce's structured-prompt pattern (task, reference_image roles,
    output_constraints, forbidden_content, priority_rules).
  - The spec drives BOTH the prompt AND cleanup enforcement downstream.
  - EVERY state goes through the model, including "normal". A previous iteration
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
           A different component in the visual style we want — the model copies
           its rendering language (art, palette, detail) but NOT its shape.

Runtime context:
  Per-run JSON built by `_analyze_source` carries concrete numbers (dimensions,
  color palette, pixel-art flag) that get included in every prompt. The
  consistency-anchor block is added to this context after the first state.

gpt-image-2 output dimensions:
  The model accepts arbitrary sizes within these constraints — any multiples
  of 16, long:short edge ratio ≤3:1, total pixels 655k–8.3M. We pick from a
  small set of buckets closest to the source's aspect so cleanup's
  force-resize back to source dims stays mild. Extreme aspects (e.g. a 10:1
  progress bar) clamp to 3:1 (1536x512) — still far closer to source than
  the near-square buckets gpt-image-1 was limited to.

Contract:
    generate_variants(
        source_png, component_type,
        kit_mode=False, shape_guidance=True,
    ) -> dict[str, bytes]
"""

from __future__ import annotations

import base64
import io
import json
from collections import Counter
from pathlib import Path

from PIL import Image
from openai import OpenAI

SPECS_DIR = Path(__file__).parent.parent / "specs"

# gpt-image-2 output size buckets — used everywhere we call images.edit.
# All obey the model's constraints: multiples of 16, long:short ≤3:1, total
# pixels in 655,360–8,294,400. 3:1 is the tightest-aspect bucket the model
# allows; anything more elongated than 3:1 (e.g. a 10:1 progress bar) gets
# clamped to this and cleanup does the rest.
_SIZE_SQUARE = "1024x1024"       # 1:1
_SIZE_LANDSCAPE = "1536x1024"    # 1.5:1
_SIZE_PORTRAIT = "1024x1536"     # 1:1.5
_SIZE_WIDE = "1536x512"          # 3:1
_SIZE_TALL = "512x1536"          # 1:3

# Per-component-type aspect hint used when we're inventing a fresh target in
# kit mode / invent flow (we don't have concrete dims yet, so lean on the
# spec's typical aspect via this table).
_KIT_TARGET_SIZE: dict[str, str] = {
    "button":       _SIZE_WIDE,       # shape_profile 2.5:1–5:1 → clamp at 3:1
    "panel":        _SIZE_SQUARE,     # shape_profile 1:1–4:3
    "checkbox":     _SIZE_SQUARE,     # 1:1
    "progress_bar": _SIZE_WIDE,       # shape_profile 4:1–10:1 → clamp at 3:1
}


def _size_bucket_for_dims(w: int, h: int) -> str:
    """Pick the gpt-image-2 output size closest to a requested aspect ratio."""
    aspect = w / h if h else 1.0
    if aspect >= 2.2:
        return _SIZE_WIDE
    if aspect >= 1.35:
        return _SIZE_LANDSCAPE
    if aspect <= 0.45:
        return _SIZE_TALL
    if aspect <= 0.74:
        return _SIZE_PORTRAIT
    return _SIZE_SQUARE


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


_INVENT_STATE_HINT: dict[str, str] = {
    "checkbox": (
        "State: CHECKED. Produce the checkbox with a clearly visible "
        "checkmark or fill indicator inside the box. Invent the "
        "checkmark's style to match image 1's art style (stroke weight, "
        "edge treatment, anti-aliasing). A checked reference gives "
        "phase 2 more visual signal than an empty box."
    ),
    "progress_bar": (
        "State: HALF-FILLED. Produce the progress bar with approximately "
        "50% of its track filled, showing BOTH the filled portion on the "
        "left and the empty portion on the right. The boundary between "
        "filled and empty must be clearly visible. A half-filled "
        "reference carries both states' visual vocabulary in one image."
    ),
    # button, panel: no hint — the model produces the resting/default state.
}


def invent_source(
    source_png: bytes,
    source_component_type: str,
    target_component_type: str,
) -> bytes:
    """Ask the model to invent a fresh {target_component_type} in the source's style.

    Used as phase 1 of the show-and-proceed kit flow. The returned PNG is a
    standalone component meant to be fed into the normal /preview pipeline
    as the new source for state generation.

    One image in (the user's upload), one image out. No primitives, no
    style-JSON bottleneck. The target's `shape_profile` block from its
    spec is injected as prose so the model has "what does a progress bar
    look like" text to anchor on without a shape reference image that
    could constrain its freedom.

    For component types whose default state is visually bare (empty
    checkbox, empty progress bar), an `_INVENT_STATE_HINT` bumps the
    output to a richer state — checked / half-filled — so phase 2 has
    more visual signal to anchor on.
    """
    from app.main import settings

    target_spec = load_spec(target_component_type)
    sp = target_spec.get("shape_profile", {})

    shape_guidance_lines: list[str] = []
    if sp.get("description"):
        shape_guidance_lines.append(f"Description: {sp['description']}")
    if sp.get("typical_aspect_ratio"):
        shape_guidance_lines.append(f"Typical aspect ratio: {sp['typical_aspect_ratio']}")
    if sp.get("required_visual_features"):
        shape_guidance_lines.append(
            "Required features: " + "; ".join(sp["required_visual_features"])
        )
    if sp.get("must_not_look_like"):
        shape_guidance_lines.append(
            "Must NOT look like: " + "; ".join(sp["must_not_look_like"])
        )
    shape_guidance = "\n".join(f"  - {line}" for line in shape_guidance_lines)

    state_hint = _INVENT_STATE_HINT.get(target_component_type, "")
    state_hint_block = f"\n\n{state_hint}" if state_hint else ""

    prompt = (
        f"Image 1 is a {source_component_type}. Produce a NEW "
        f"{target_component_type} in the same art style.\n\n"
        "MATCH image 1's: colour palette, line weight, rendering technique, "
        "edge treatment, level of detail, texture, and overall visual "
        "identity.\n\n"
        f"DO NOT copy image 1's silhouette, subject, dimensions, or shape. "
        f"The output is a {target_component_type} — a different component "
        f"type from image 1. It must read as a {target_component_type} at "
        "a glance, not as image 1 wearing a different label.\n\n"
        f"Shape guidance for {target_component_type}:\n"
        f"{shape_guidance}"
        f"{state_hint_block}\n\n"
        f"Output: a single standalone {target_component_type} rendered in "
        "image 1's art style, against a transparent background unless "
        "image 1 has an opaque plate (in which case match it). Do not "
        "include any other UI element, text, caption, or framing."
    )

    client = OpenAI(api_key=settings.openai_api_key)
    return _call_image_model(
        client=client,
        model=settings.openai_image_model,
        prompt=prompt,
        image_pngs=[source_png],
        size=_KIT_TARGET_SIZE.get(target_component_type, _SIZE_SQUARE),
        label=f"invented {target_component_type}",
    )


def generate_variants(
    source_png: bytes,
    component_type: str,
    kit_mode: bool = False,
    shape_guidance: bool = True,
) -> dict[str, bytes]:
    """Produce state variants using the JSON spec + consistency chaining.

    Two modes:

    * Normal (`kit_mode=False`, default): the uploaded image IS the element
      we're generating states for. Source is passed to the model as the
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
    the prompt so the model produces a proper button shape / panel frame /
    etc. Toggle off for pure style transfer — the family will copy the
    reference's silhouette more faithfully but may not read as the right
    component type.
    """
    from app.main import settings

    spec = load_spec(component_type)
    runtime_ctx = _analyze_source(source_png)

    client = OpenAI(api_key=settings.openai_api_key)
    results: dict[str, bytes] = {}

    # In kit mode the source is a DIFFERENT component type, so its dims don't
    # describe what we're generating — fall back to the target's typical aspect.
    if kit_mode:
        size = _KIT_TARGET_SIZE.get(component_type, _SIZE_SQUARE)
    else:
        src = runtime_ctx["source_analysis"]
        size = _size_bucket_for_dims(src["width"], src["height"])

    anchor_png: bytes | None = None
    anchor_state: str | None = None

    for state, state_spec in spec["states"].items():
        # Every state goes through the model (no passthrough branch). See module docstring.
        if kit_mode:
            # Kit mode passes the user's source as STYLE_FAMILY_REFERENCE only.
            # Shape semantics come from the target's `shape_profile` block
            # injected into the prompt via _build_prompt, not from a primitive
            # image — letting the model pick the silhouette preserves freedom.
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

        img_bytes = _call_image_model(
            client=client,
            model=settings.openai_image_model,
            prompt=prompt,
            image_pngs=[png for png, _ in image_refs],
            size=size,
            label=f"state={state!r}",
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
    the model can't drift back into 'just copy the reference'. This is the block
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

    `image_refs` is the same list passed to _call_image_model; the prompt keys
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
        # the model has concrete geometric constraints (aspect ratio, required
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
    # With shape_guidance we have up to 3 images with distinct roles; without
    # it we have 1 (style) or 2 (style + anchor).
    if kit_mode and component_type:
        # Describe each attached image by its role, in attach order.
        role_lines: list[str] = []
        for i, (_, meta) in enumerate(image_refs, start=1):
            role = meta.get("role", "REFERENCE")
            if role == "SHAPE_REFERENCE":
                role_lines.append(
                    f"- Image {i} — SHAPE reference: a neutral grayscale "
                    f"geometric primitive showing the canonical shape, aspect "
                    f"ratio, and structural layout of a {component_type}. "
                    f"Use this for SILHOUETTE, PROPORTIONS, and STRUCTURE only. "
                    f"Ignore its colours and lack of texture."
                )
            elif role == "STYLE_FAMILY_REFERENCE":
                role_lines.append(
                    f"- Image {i} — STYLE reference: a different component "
                    f"type in the visual style you must match. Use this for "
                    f"ART STYLE, COLOUR PALETTE, LINE WEIGHT, EDGE TREATMENT, "
                    f"and LEVEL OF DETAIL only. Do NOT copy its silhouette "
                    f"or subject."
                )
            elif role == "CONSISTENCY_REFERENCE":
                role_lines.append(
                    f"- Image {i} — CONSISTENCY reference: a previously "
                    f"generated '{meta.get('state_name', '?')}' state of the "
                    f"{component_type} you're building. Match its EXACT "
                    f"dimensions, silhouette, and rendering style."
                )

        has_shape_ref = any(m.get("role") == "SHAPE_REFERENCE" for _, m in image_refs)

        lines = [
            f"Generate a NEW {component_type} for the '{state}' state.",
            "",
            f"You are given {len(image_refs)} reference image"
            f"{'s' if len(image_refs) != 1 else ''} with distinct roles:",
            "",
            *role_lines,
            "",
        ]
        if has_shape_ref:
            lines.append(
                f"Combine them: take the STYLE from the STYLE reference and "
                f"apply it to the SHAPE from the SHAPE reference. The output "
                f"must clearly read as a {component_type}, not as a copy of "
                f"any single reference."
            )
        else:
            lines.append(
                f"You MUST invent an appropriate {component_type} silhouette "
                f"from scratch. The output must clearly read as a "
                f"{component_type}, not as a copy of the reference image."
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


# --- openai call --------------------------------------------------------------


def _call_image_model(
    *,
    client: OpenAI,
    model: str,
    prompt: str,
    image_pngs: list[bytes],
    size: str = "auto",
    label: str = "image",
) -> bytes:
    """One image-edit call. Images are attached in the order given.

    `size` is one of the aspect buckets defined above. gpt-image-2 honours
    the requested size (multiples of 16, long:short ≤3:1) — the spec
    template still asks for source-exact pixel dims in the prompt text,
    but cleanup's force-resize corrects any remaining mismatch downstream.

    `label` is a short human-readable tag ("state='hover'",
    "invented button", "modification") that shows up in error messages.
    """
    if not image_pngs:
        raise ValueError("image_pngs must be non-empty")

    image_files: list[io.BytesIO] = []
    for i, png in enumerate(image_pngs):
        bio = io.BytesIO(png)
        # The SDK inspects `.name` to infer the MIME type. Without it,
        # multi-image requests fail with "image must be a PNG/WEBP/JPEG".
        bio.name = f"ref_{i}.png"
        image_files.append(bio)

    # images.edit accepts a single file-like OR a list. Pass the right shape
    # so n=1 calls with one reference image don't trigger a multi-image path.
    image_arg = image_files[0] if len(image_files) == 1 else image_files

    response = client.images.edit(
        model=model,
        image=image_arg,
        prompt=prompt,
        n=1,
        size=size,
    )

    for item in response.data or []:
        if getattr(item, "b64_json", None):
            return base64.b64decode(item.b64_json)

    raise RuntimeError(f"OpenAI returned no image for {label}")


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

    client = OpenAI(api_key=settings.openai_api_key)
    return _call_image_model(
        client=client,
        model=settings.openai_image_model,
        prompt=prompt,
        image_pngs=[source_png],
        size=_size_bucket_for_dims(src_w, src_h),
        label=f"modification={modification.strip()[:40]!r}",
    )
