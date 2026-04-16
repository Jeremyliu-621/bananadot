"""Emit a drop-in Godot 4 folder from a normalised variant set.

Every supported component shares the same output shape:

    <root>/bananadot_<component_type>/
        assets/<state>.png ...         # one PNG per state produced upstream
        example.tscn                   # ready-to-run scene wired to the assets
        README.md                      # install + swap-in-your-own-scene notes

What changes per component is the Godot node and which textures wire to which
properties. That mapping lives in `_SPECS` below — one entry per component
type. To add a new component:

    1. Add its state list + prompts in `generate.py` (STATE_INSTRUCTIONS).
    2. Add a `_ComponentSpec` entry here with a `render_tscn` that emits
       the right node type, and a `render_readme` that describes the prop
       mapping in prose.

Everything else (zip bundling, cleanup, the HTTP layer) is component-agnostic.

Choice of nodes (v1):
  - button        -> TextureButton (texture_normal/hover/pressed/disabled)
  - panel         -> NinePatchRect (9-slice, auto-computed patch margins)
  - checkbox      -> TextureButton with toggle_mode; normal=unchecked,
                     pressed=checked (simpler than Theme+CheckBox override)
  - progress_bar  -> TextureProgressBar (texture_under=empty, texture_progress=full)

All drop in with zero import ceremony. A Theme resource would be the "correct"
home once we want 9-slice panels behind buttons, typography, focus outlines —
not yet.
"""

from __future__ import annotations

import io
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image


# --- public entry point -------------------------------------------------------


def emit_component(
    component_type: str,
    variants: dict[str, bytes],
    root: Path,
    source_png: bytes | None = None,
) -> Path:
    """Write the Godot bundle to disk; return the folder path.

    `source_png` is optional and only used to decide whether to set
    `texture_filter = nearest` (pixel-art inputs look awful with linear
    filtering).
    """
    try:
        spec = _SPECS[component_type]
    except KeyError as e:
        raise NotImplementedError(
            f"No Godot template for component_type={component_type!r}. "
            f"Add a _ComponentSpec entry in godot.py."
        ) from e

    folder_name = f"bananadot_{component_type}"
    out_dir = Path(root) / folder_name
    assets_dir = out_dir / "assets"

    # Start clean — stale files from a previous run would ride along in the zip.
    if out_dir.exists():
        shutil.rmtree(out_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Write only the states this spec knows about, in canonical order.
    written: dict[str, Path] = {}
    for state in spec.states:
        png = variants.get(state)
        if png is None:
            continue
        path = assets_dir / f"{state}.png"
        path.write_bytes(png)
        written[state] = path

    if spec.canonical_state not in written:
        raise RuntimeError(
            f"Pipeline produced no {spec.canonical_state!r} variant for "
            f"{component_type!r} — refusing to emit bundle."
        )

    pixel_art = _looks_like_pixel_art_bytes(source_png) if source_png else False

    tscn = spec.render_tscn(
        folder_name=folder_name,
        written=written,
        variants=variants,
        pixel_art=pixel_art,
    )
    readme = spec.render_readme(folder_name=folder_name)

    (out_dir / "example.tscn").write_text(tscn, encoding="utf-8")
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    return out_dir


# --- spec --------------------------------------------------------------------


@dataclass(frozen=True)
class _ComponentSpec:
    states: tuple[str, ...]  # canonical order for .tscn + filenames
    canonical_state: str  # must be present or we refuse to emit
    render_tscn: Callable[..., str]
    render_readme: Callable[..., str]


# --- button ------------------------------------------------------------------


_BUTTON_STATE_TO_PROP = {
    "normal": "texture_normal",
    "pressed": "texture_pressed",
    "hover": "texture_hover",
    "disabled": "texture_disabled",
}


def _render_button_tscn(*, folder_name: str, written: dict[str, Path], pixel_art: bool, **_: object) -> str:
    ext_lines: list[str] = []
    prop_lines: list[str] = []
    ordered = [s for s in _BUTTON_STATE_TO_PROP if s in written]

    for i, state in enumerate(ordered, start=1):
        ext_id = f"{i}_{state}"
        ext_lines.append(
            f'[ext_resource type="Texture2D" '
            f'path="res://{folder_name}/assets/{state}.png" id="{ext_id}"]'
        )
        prop_lines.append(f'{_BUTTON_STATE_TO_PROP[state]} = ExtResource("{ext_id}")')

    load_steps = len(ordered) + 2
    filter_line = "texture_filter = 1\n" if pixel_art else ""

    return (
        f"[gd_scene load_steps={load_steps} format=3]\n\n"
        + "\n".join(ext_lines)
        + "\n\n"
        + '[node name="Demo" type="TextureButton"]\n'
        + filter_line
        + "\n".join(prop_lines)
        + "\n"
    )


def _render_button_readme(*, folder_name: str) -> str:
    return _readme_shell(
        folder_name=folder_name,
        component_type="button",
        run_hint="hover, click, and toggle the disabled checkbox to see the states react",
        use_section=f"""Option A — instance `example.tscn` as a `PackedScene`.

Option B — add a `TextureButton` node and point its texture properties at
the files in `assets/`:

- `texture_normal` → `assets/normal.png`
- `texture_pressed` → `assets/pressed.png`
- `texture_hover` → `assets/hover.png`
- `texture_disabled` → `assets/disabled.png`
""",
    )


# --- panel -------------------------------------------------------------------


# How aggressively to trust the source's aspect for 9-slice margins. 1/4 of the
# shorter dimension is a forgiving default — frames with thick borders (pixel
# art) slice cleanly; tight vector frames don't overrun the center.
_PANEL_PATCH_FRACTION = 0.25
_PANEL_PATCH_MIN = 4
_PANEL_PATCH_MAX = 64
# Preview size in the scene — picked so the 9-slice stretch is visible.
_PANEL_PREVIEW_W = 320
_PANEL_PREVIEW_H = 200


def _render_panel_tscn(*, folder_name: str, written: dict[str, Path], pixel_art: bool, **_: object) -> str:
    normal_path = written["normal"]
    with Image.open(normal_path) as img:
        w, h = img.size

    # Auto 9-slice margin — tuned conservatively so we never exceed image bounds.
    raw = int(min(w, h) * _PANEL_PATCH_FRACTION)
    margin = max(_PANEL_PATCH_MIN, min(raw, _PANEL_PATCH_MAX, min(w, h) // 2 - 1 if min(w, h) > 2 else 1))

    filter_line = "texture_filter = 1\n" if pixel_art else ""

    return (
        "[gd_scene load_steps=3 format=3]\n\n"
        f'[ext_resource type="Texture2D" '
        f'path="res://{folder_name}/assets/normal.png" id="1_normal"]\n\n'
        '[node name="Demo" type="NinePatchRect"]\n'
        f"offset_right = {float(_PANEL_PREVIEW_W)}\n"
        f"offset_bottom = {float(_PANEL_PREVIEW_H)}\n"
        + filter_line
        + 'texture = ExtResource("1_normal")\n'
        f"patch_margin_left = {margin}\n"
        f"patch_margin_top = {margin}\n"
        f"patch_margin_right = {margin}\n"
        f"patch_margin_bottom = {margin}\n"
    )


def _render_panel_readme(*, folder_name: str) -> str:
    return _readme_shell(
        folder_name=folder_name,
        component_type="panel",
        run_hint="drag the NinePatchRect's size in the editor — the frame stretches, corners stay crisp",
        use_section=f"""Option A — instance `example.tscn` as a `PackedScene`.

Option B — add a `NinePatchRect` node and point its `texture` at
`assets/normal.png`. The generated scene sets `patch_margin_*` automatically
based on the source image; tweak them in the inspector if the corners look
off.

The default preview size is a stretched rectangle so you can see the 9-slice
work. Resize freely — that's the whole point of a panel.
""",
    )


# --- checkbox ----------------------------------------------------------------


def _render_checkbox_tscn(*, folder_name: str, written: dict[str, Path], pixel_art: bool, **_: object) -> str:
    ext_lines = [
        f'[ext_resource type="Texture2D" '
        f'path="res://{folder_name}/assets/unchecked.png" id="1_unchecked"]',
        f'[ext_resource type="Texture2D" '
        f'path="res://{folder_name}/assets/checked.png" id="2_checked"]',
    ]
    filter_line = "texture_filter = 1\n" if pixel_art else ""

    return (
        "[gd_scene load_steps=4 format=3]\n\n"
        + "\n".join(ext_lines)
        + "\n\n"
        '[node name="Demo" type="TextureButton"]\n'
        + filter_line
        + "toggle_mode = true\n"
        'texture_normal = ExtResource("1_unchecked")\n'
        'texture_pressed = ExtResource("2_checked")\n'
    )


def _render_checkbox_readme(*, folder_name: str) -> str:
    return _readme_shell(
        folder_name=folder_name,
        component_type="checkbox",
        run_hint="click the button to toggle between unchecked and checked",
        use_section=f"""Option A — instance `example.tscn` as a `PackedScene` and listen to
its `toggled(pressed)` signal.

Option B — add a `TextureButton` node, set `toggle_mode = true`, then wire:

- `texture_normal` → `assets/unchecked.png`
- `texture_pressed` → `assets/checked.png`

`toggle_mode` is what makes the pressed texture stick after the click. Leave
`texture_hover` unset unless you want a separate hover look.
""",
    )


# --- progress bar ------------------------------------------------------------


def _render_progress_bar_tscn(*, folder_name: str, written: dict[str, Path], pixel_art: bool, **_: object) -> str:
    ext_lines = [
        f'[ext_resource type="Texture2D" '
        f'path="res://{folder_name}/assets/empty.png" id="1_empty"]',
        f'[ext_resource type="Texture2D" '
        f'path="res://{folder_name}/assets/full.png" id="2_full"]',
    ]
    filter_line = "texture_filter = 1\n" if pixel_art else ""

    return (
        "[gd_scene load_steps=4 format=3]\n\n"
        + "\n".join(ext_lines)
        + "\n\n"
        '[node name="Demo" type="TextureProgressBar"]\n'
        + filter_line
        + "max_value = 100.0\n"
        "value = 50.0\n"
        'texture_under = ExtResource("1_empty")\n'
        'texture_progress = ExtResource("2_full")\n'
    )


def _render_progress_bar_readme(*, folder_name: str) -> str:
    return _readme_shell(
        folder_name=folder_name,
        component_type="progress bar",
        run_hint="drag the `value` property in the inspector — the fill texture reveals left-to-right",
        use_section=f"""Option A — instance `example.tscn` as a `PackedScene` and drive its
`value` property from code (`$Demo.value = 0.75 * Demo.max_value`, etc.).

Option B — add a `TextureProgressBar` node and wire:

- `texture_under`    → `assets/empty.png`   (frame / background)
- `texture_progress` → `assets/full.png`    (filled bar, revealed by `value`)

Default fill mode is left → right. Change `fill_mode` on the node if you want
right-to-left, top-to-bottom, or radial.
""",
    )


# --- registry ----------------------------------------------------------------


_SPECS: dict[str, _ComponentSpec] = {
    "button": _ComponentSpec(
        states=("normal", "hover", "pressed", "disabled"),
        canonical_state="normal",
        render_tscn=_render_button_tscn,
        render_readme=_render_button_readme,
    ),
    "panel": _ComponentSpec(
        states=("normal",),
        canonical_state="normal",
        render_tscn=_render_panel_tscn,
        render_readme=_render_panel_readme,
    ),
    "checkbox": _ComponentSpec(
        states=("unchecked", "checked"),
        canonical_state="unchecked",
        render_tscn=_render_checkbox_tscn,
        render_readme=_render_checkbox_readme,
    ),
    "progress_bar": _ComponentSpec(
        states=("empty", "full"),
        canonical_state="empty",
        render_tscn=_render_progress_bar_tscn,
        render_readme=_render_progress_bar_readme,
    ),
}


# --- readme shell ------------------------------------------------------------


def _readme_shell(*, folder_name: str, component_type: str, run_hint: str, use_section: str) -> str:
    return f"""# bananadot {component_type}

Generated by bananadot from a single source image.

## Install

Drop this **entire folder** into your Godot 4 project's root so it lives at:

```
res://{folder_name}/
```

Open `example.tscn` and run the scene (F6) — {run_hint}.

## Use in your own scenes

{use_section}
## Renaming the folder

If you rename `{folder_name}`, search-and-replace the old path inside
`example.tscn` with the new one.
"""


# --- helpers -----------------------------------------------------------------


def _looks_like_pixel_art_bytes(png: bytes) -> bool:
    """Same heuristic cleanup.py uses — duplicated here to keep modules independent."""
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    if img.width > 128 or img.height > 128:
        return False
    colors = img.getcolors(maxcolors=65)
    return colors is not None and len(colors) <= 64
