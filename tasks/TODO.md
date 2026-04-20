# Tasks

<!--
HOW TO USE THIS FILE
====================
Active plan for the current initiative. One TODO.md at a time. Move to
tasks/archive/YYYY-MM-DD-<name>.md when the initiative wraps up.

STATUS MARKERS
- [ ]  todo
- [~]  in progress (one at a time)
- [x]  done
- [?]  blocked (next line explains why)

THE `<!-- resume here -->` MARKER
- Exactly one in the file. First thing to read when a new session starts.
- Move it every time a step finishes.
-->

## Current initiative: kit generation + multi-variant batch + real progress

**Goal:** Two big features layered on top of the demo-both surface
(variant + session history + Godot-free UI):

1. **Kit generation** — one source component → matching set of all four
   component types (button + panel + checkbox + progress_bar) sharing the
   source's visual style.
2. **Multi-variant batch** — when a user types a text modification, return
   3 options in parallel and let them pick the best one to continue with.

Both features need **real progress bars** driven by server-sent events
(SSE), not fake timed messages.

**Started:** 2026-04-20
**Base branch:** `worktree-demo-both` (commit `f4325c7`)
**Author for commits:** `Jeremyliu-621 <jeremyliu621@gmail.com>` (via
`--author` flag; do not modify `git config`).

### Architecture notes

#### Kit generation

- New optional param on `generate.generate_variants`:
  `style_reference_png: bytes | None`. When set, every Gemini call receives
  a third image part with role `STYLE_FAMILY_REFERENCE` + a prompt block
  explaining it ("match the art style of image 3 but not its shape or
  subject").
- New endpoint `POST /kit` — takes the source image and its
  `source_component_type`. For each of the OTHER three component types
  it runs the full pipeline (generate_variants with style_reference →
  cleanup → emit). Returns a JSON bundle with all four components' state
  sets + zip bundles.
- Emits SSE events during the run:
  `{"type": "component_started", "component": "checkbox"}` and
  `{"type": "component_completed", "component": "checkbox",
    "variants": {...}}` for each target.

#### Multi-variant batch

- Extend `generate.apply_modification` to accept `count: int = 1`. When
  count > 1, run `count` parallel Gemini calls with light prompt-seed
  variation to encourage different outputs.
- New endpoint `POST /variant/options` — source + modification + count,
  returns N candidate images (NO state pipeline yet — just the modified
  source). Frontend shows them side by side.
- User picks one → frontend POSTs it as the source to the existing
  `/preview` flow (the picked option becomes the new baseline).

#### Progress bars (SSE)

- FastAPI `StreamingResponse` with `text/event-stream` media type, yielding
  `data: {json}\n\n` framed events.
- Frontend `EventSource` consumes the stream; a small progress-bar
  component fills per event. One bar per component (kit) or per option
  (batch).
- Events are fire-and-forget; the final event carries the completed
  payload the UI needs to render.

### Phase 1 — scaffolding (non-code prep)

- [x] Create worktree `kit-batch` from `worktree-demo-both` tip
- [x] Archive old TODO; write this one
- [x] Boot the existing demo-both server pattern on port 8002 for this
  branch; verify baseline (pre-feature) works

### Phase 2 — kit generation backend

- [x] Add `style_reference_png` param to `generate.generate_variants`.
  Refactored reference-collection so each call can carry 1/2/3 images
  in a consistent order (source / anchor / style-family).
- [x] Offline-test: verified preamble shape with 1/2/3 images + all
  combinations. No regression path when `style_reference=None`.
- [x] New `/kit` endpoint in `main.py`. Accepts `image` +
  `source_component_type`. Computes the three targets, runs the pipeline
  for each with the source as style reference. Uses `asyncio.to_thread`
  so blocking Gemini calls don't stall the SSE event loop.
- [x] SSE event stream: `kit_started`, `component_started`,
  `component_completed`, `component_failed`, `kit_done`. Targets run
  sequentially so a single Gemini failure doesn't cascade.
- [x] Verified `/kit` is registered on live server (/openapi.json shows
  it). Full end-to-end smoke test with a real image still pending —
  Phase 6 will cover this.

### Phase 3 — kit generation frontend

- [x] "Generate matching kit" button on the results step, under the
  variant section (below the existing 'create a variant' block).
- [x] Progress UI: one row per target component. Pulsing bar while
  active, solid fill on done, red fill on failure.
- [x] On `component_completed`, appends a kit-member card with the
  state grid + per-member download button.
- [x] Generic SSE parser using fetch's ReadableStream (EventSource
  doesn't support POST with multipart body).
- [ ] 'Download all' super-zip: punted. A per-member download per
  card is enough for v1; if the demo needs a single zip, add
  `/kit/bundle` or assemble client-side later.

### Phase 4 — multi-variant batch backend

- [ ] Extend `generate.apply_modification` to accept `count`. Run
  `asyncio.gather`-style parallel calls (Gemini client supports sync;
  use `asyncio.to_thread`).
- [ ] Optional prompt nudge per call: append "(variation N of M, vary
  subtly from other candidates)" to a small per-call seed so the three
  aren't identical.
- [ ] New `/variant/options` endpoint. Accepts image + modification +
  count. Returns a JSON list of N data-URL images.
- [ ] SSE variant: emit per-option progress events so each option's
  progress bar can fill independently.

### Phase 5 — multi-variant batch frontend

- [ ] When user hits "Generate variant", instead of going straight to
  the full-pipeline variant, call `/variant/options` first with
  `count=3`.
- [ ] Picker UI: grid of 3 thumbnails, each hoverable, with a
  "Use this one" button below.
- [ ] On pick: feed the chosen image into the existing `/preview` flow
  (treat it as a new source, pushes to session history normally).
- [ ] Progress bars during option generation (3 bars, one per option).

### Phase 6 — verification + polish

- [ ] Real-image smoke test: upload a button, click "Generate kit",
  verify all four components generate with coherent style. Inspect by eye.
- [ ] Repeat with a checkbox as the source — kit should still produce
  the other three types in a matching style.
- [ ] Variant batch smoke test: type a modification, see three options,
  pick one, confirm the state pipeline runs on the picked image.
- [ ] Error handling: if a kit component fails, the UI should show the
  failure on that row without killing the rest.
- [ ] Update `tasks/lessons.md` with any patterns learned (especially
  around SSE + FastAPI, Gemini batch calling, style transfer prompt
  shape).
- [ ] Commit messages use `--author="Jeremyliu-621 <jeremyliu621@gmail.com>"`
  on every commit (do NOT touch `git config`).

<!-- resume here: Phase 4 — multi-variant batch backend. Extend generate.apply_modification to accept `count`, run N parallel Gemini calls via asyncio.to_thread + gather, return a list of PNG bytes. Add /variant/options SSE endpoint (batch_started / option_started / option_completed / batch_done events). Per-call prompt nudge ('(variation N of M, vary subtly)') so the three candidates aren't identical. -->

### Review

_Filled in when the initiative closes: what shipped, what surprised us,
what belongs in lessons.md or MEMORY.md._
