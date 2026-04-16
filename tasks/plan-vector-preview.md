# Vector live-preview — implementation plan

**Branch:** `worktree-vector-preview` (via `.claude/worktrees/vector-preview`)
**Started:** 2026-04-16
**Status:** plan only, awaiting Jeremy review. Not yet scheduled against the active
`tasks/TODO.md` initiative (v0 end-to-end pipeline is still mid-flight on the
real-image smoke test).

## Problem

The live preview panel on `/` renders the button by swapping a PNG
`background-image` on a `<button>` element for each state
(`backend/app/static/index.html:179-187`). It is a bitmap that happens to look
crisp because we pin `image-rendering: pixelated`. Jeremy wants the preview to
be genuinely vector — composed of multiple paths/shapes, not a flat raster.

## Goal

When the user hits the results screen, the live preview panel shows each state
as an inline SVG whose DOM contains **multiple path/rect elements grouped by
color region**. Hovering / pressing / toggling disabled swaps to the
corresponding state's SVG with no flicker and no network roundtrip. At 4×
browser zoom the preview stays crisp. Devtools' element inspector shows real
vector geometry.

## Non-goals (keep scope tight)

- **Godot bundle format stays raster.** TextureButton still points at PNGs.
  Godot 4 does support SVG, but swapping the exported asset format is a
  user-visible change to the download shape and belongs in its own initiative.
- **Variant thumbnail grid stays raster.** Those thumbnails are the honest
  record of what Nano Banana produced — useful for debugging model drift.
  Vectorizing them would hide bitmap artefacts Jeremy may want to see.
- **Nano Banana prompts unchanged.** NB outputs raster; vectorization is a
  post-cleanup pipeline step.
- **No new component types.** Button only, matching current viewer scope.
- **No /generate endpoint change.** CLI consumers keep getting a raster zip.

## Architecture

```
source_png
    │
    ▼
generate_variants (pipeline/generate.py)           {state: PNG bytes}
    │
    ▼
normalize_variants (pipeline/cleanup.py)           {state: PNG bytes, aligned}
    │
    ├──────────────────────────────► emit_component (pipeline/godot.py)
    │                                  └── writes raster PNGs for Godot (unchanged)
    │
    ▼
vectorize_variants (pipeline/vectorize.py, NEW)    {state: SVG string}
    │
    ▼
/preview response                   adds `variants_svg: {state: svg_string}`
    │
    ▼
index.html live preview             inlines 4 SVGs inside <button>, CSS hides
                                    all but the active-state SVG
```

### New module: `backend/app/pipeline/vectorize.py`

```python
def vectorize_variants(
    variants: dict[str, bytes],
    is_pixel_art: bool,
) -> dict[str, str]:
    """PNG bytes per state → SVG string per state."""
```

Two internal branches, chosen by the `is_pixel_art` flag already computed
upstream in `cleanup._looks_like_pixel_art_bytes_from_source`:

- **`_svg_from_pixel_grid(png_bytes) -> str`** — pixel art. Walk the pixel
  grid; emit one `<rect width=run height=1 x=x y=y fill=#rrggbb/>` per
  horizontal run of same-color opaque pixels (run-length encoding across rows).
  Group rects by color into `<g fill="...">` blocks so the DOM is
  color-semantic ("border region", "fill region", "highlight region" fall out
  naturally from palette structure). Wrap in `<svg viewBox="0 0 W H"
  shape-rendering="crispEdges">`. Transparent pixels emit nothing.
  Faithful to source pixels — no AI-guessed path smoothing — and each color
  region is a cleanly separable group of many vectors.

- **`_svg_from_vtracer(png_bytes) -> str`** — flat vector art. Call
  `vtracer.convert_raw_image_to_svg` (Python binding, Rust-backed) in color
  mode. Output has one `<path>` per color cluster, which is exactly the
  "border + fill + corners + highlight" decomposition a vector illustrator
  would hand-author. Starting parameters:
  `color_precision=6, layer_difference=16, corner_threshold=60,
  filter_speckle=4, mode="spline"`. Tune against the first real smoke-test
  button before calling this done.

Return SVG as strings (not bytes / not files) because they're inlined into
the response JSON and injected into the DOM.

### `/preview` response (`backend/app/main.py`)

Extend `_run_pipeline` to compute and return `svg_variants`. Plumb into the
JSON response as `variants_svg: dict[str, str]`. `/generate` unchanged.
Approximate diff:

```python
# _run_pipeline
cleaned = cleanup.normalize_variants(variants, source_png=raw)
svg_variants = vectorize.vectorize_variants(cleaned, is_pixel_art=is_pixel)  # NEW
# ...
return cleaned, svg_variants, zip_bytes, is_pixel, out_dir

# /preview response body
"variants_svg": svg_variants,
```

### Frontend (`backend/app/static/index.html`)

Replace the `.live-button` that relies on CSS custom properties with four
stacked SVG children inside the same `<button>`:

```html
<button class="live-button" id="live-button">
  <span class="state state-normal"></span>
  <span class="state state-hover"></span>
  <span class="state state-pressed"></span>
  <span class="state state-disabled"></span>
</button>
```

CSS (replace the `--tex-*` machinery):

```css
.live-button { position: relative; width: 160px; height: 160px;
               background: transparent; border: 0; padding: 0; }
.live-button .state { position: absolute; inset: 0; display: none; }
.live-button .state-normal { display: block; }
.live-button .state svg { width: 100%; height: 100%; display: block; }

.live-button:hover    .state-normal { display: none; }
.live-button:hover    .state-hover  { display: block; }
.live-button:active   .state-hover  { display: none; }
.live-button:active   .state-pressed { display: block; }
.live-button:disabled .state-normal,
.live-button:disabled .state-hover,
.live-button:disabled .state-pressed { display: none; }
.live-button:disabled .state-disabled { display: block; cursor: not-allowed; }
```

JS (`renderResults` in `index.html`): after grid rendering, inject SVG
strings:

```js
const live = document.getElementById('live-button');
for (const s of ['normal', 'hover', 'pressed', 'disabled']) {
  const slot = live.querySelector(`.state-${s}`);
  slot.innerHTML = data.variants_svg[s] || data.variants_svg.normal;
}
```

Delete the four `live.style.setProperty('--tex-*', ...)` lines and the
`--tex-*` CSS selectors. Keep the `<button>` element (so `:disabled`,
keyboard focus, and the existing "disabled" checkbox handler all keep
working).

Sanitization: SVGs come from our own server, not user-pasted content. Still,
defensively strip `<script`, `on*=`, and `javascript:` via a small regex
before `innerHTML` — cheap insurance if vtracer or future pipeline steps ever
pass through anything weird.

## Step-by-step

### Dependencies
- [ ] Add `vtracer>=0.6` to `backend/pyproject.toml`. Verify it installs
      cleanly on Windows (prebuilt wheels expected). If it doesn't, fall back
      to shelling out to the `vtracer` CLI — document whichever path we take.

### Backend
- [ ] Create `backend/app/pipeline/vectorize.py` with `vectorize_variants`,
      `_svg_from_pixel_grid`, `_svg_from_vtracer`.
- [ ] Unit-test both branches offline with synthetic inputs: a 4×4 palette
      image (exercises pixel-grid RLE) and the existing
      `backend/outputs/bananadot_button/assets/normal.png` (exercises vtracer
      if the sample is pixel-art; if not, vice versa).
- [ ] Wire into `backend/app/main.py::_run_pipeline` and extend the `/preview`
      JSON response with `variants_svg`.

### Frontend
- [ ] Rewrite `.live-button` HTML + CSS per the Architecture section.
- [ ] Update `renderResults` to inject SVG strings; delete `--tex-*`
      property-setters.
- [ ] Keep the body-level `.pixel-art` class toggle — it still affects the
      variant thumbnails; the SVG preview ignores it (it's already crisp).

### Verification
- [ ] Open the existing cached pixel-art button in the new pipeline end-to-end.
      Inspect the preview in devtools — must see `<g fill="...">` wrappers
      containing many `<rect>` children, not a single traced blob.
- [ ] Zoom the browser to 400%. Preview must stay crisp; no stair-stepping
      other than the intended pixel-art lattice.
- [ ] Run a flat-vector button through end-to-end. Devtools must show
      multiple `<path>` siblings grouped by color — if it's one monolithic
      path, vtracer params need retuning.
- [ ] Interaction smoke test: hover, mousedown-hold, toggle the disabled
      checkbox. Each transitions without flicker (all four SVGs are already
      in the DOM, state changes are pure CSS).
- [ ] Measure payload. If a single state's SVG exceeds ~100KB for a typical
      input, either tighten vtracer thresholds or add a minification pass
      (strip whitespace, drop redundant attrs). Don't reach for full SVGO —
      overkill for v1.

### Docs
- [ ] One-paragraph note in `backend/README.md`: "live preview renders as
      SVG; the downloaded Godot bundle is unchanged and still ships PNGs."
      Prevents anyone assuming the Godot shape changed.

### Cleanup
- [ ] Delete `--tex-normal`, `--tex-hover`, `--tex-pressed`, `--tex-disabled`
      CSS vars and all `background-image` rules on `.live-button`. They are
      fully replaced — no need to keep fallback code paths.

## Risks & mitigations

- **vtracer Windows install.** Likely fine (prebuilt wheels), but prove it
  on Jeremy's machine before wiring anything else. Fallback: bundled CLI.
- **Pixel-art SVG DOM size.** A 128×128 busy button could emit a few
  thousand rects. RLE across rows typically collapses 5–10×. If that's still
  too heavy, add a second pass that greedily merges vertically-adjacent equal
  runs into taller rects — a simple greedy 2D rectangle cover is enough. Not
  needed for v1, flagged as follow-up.
- **State-swap flicker.** Eliminated by design: all four SVGs ship inline on
  `/preview` response, state change is CSS-only. No async injection per state.
- **`:disabled` selector scope.** Only matches native form controls. The
  `<button>` wrapper keeps this working — don't refactor the button out to a
  div during the frontend rewrite.
- **HTML-escaping in JSON.** vtracer SVGs may contain characters that JSON
  encodes fine but need to survive `innerHTML` injection. Strings not DOM
  nodes — standard path, no special handling needed, but worth eyeballing the
  first generated response body.

## Open questions for Jeremy

1. **Godot bundle.** Preview becomes SVG. Should the downloaded zip also emit
   SVG (Godot 4 imports SVG natively as Texture2D)? Bigger scope, user-visible.
   **My default:** leave raster; revisit as its own initiative.
2. **Variant thumbnails.** Stay raster (current plan, honest to NB output) or
   also vectorize for visual consistency? **My default:** stay raster.
3. **Vectorizer choice.** Going with vtracer (Rust, modern, color-layered
   out of the box) unless you have a preference. Potrace is the other common
   option but it's monochrome-first and needs per-color passes to match.
4. **Timing.** This is a Phase 3 / polish concern per the existing
   `tasks/TODO.md`. Do we land this before or after the Phase 2 Next.js
   frontend skeleton? **My default:** after. The polish only matters once
   the demo surface is settled.

## Decisions already made

- **Scope:** preview-only; Godot bundle untouched.
- **Two-mode vectorizer:** pixel-art → RLE `<rect>` grid; flat-art → vtracer
  color-layered paths. One knob (`is_pixel_art`), already in the pipeline.
- **All states inline on load:** state swap is pure CSS, never async.
- **Keep `/generate` raster-only:** CLI consumers unaffected.
- **SVG strings in JSON, not data URLs:** inlining gives us real DOM
  inspectability, which is the whole point.
