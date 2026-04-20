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

- [x] Extended `generate.apply_modification` with optional
  `variation_label` keyword — a short nudge appended to the prompt so
  parallel candidates diverge subtly.
- [x] New `/variant/options` endpoint. Streams SSE events:
  `batch_started` / `option_started` / `option_completed` /
  `option_failed` / `batch_done`. Count clamped to 1..4. Runs via
  `asyncio.to_thread` + `asyncio.as_completed` so first-to-finish
  shows up immediately.

### Phase 4.5 — bring kit-batch in line with :8001 (user asked mid-session)

- [x] `git revert 79ac3fe` on kit-batch so normal is regenerated by
  Gemini rather than being a source passthrough. Verified the
  generate.py / specs state is byte-identical to worktree-normal-regenerate.

### Phase 5 — multi-variant batch frontend

- [x] "Generate variant" now calls `/variant/options` first with
  `count=3` (const `VARIANT_OPTION_COUNT` in index.html).
- [x] Picker UI: 3 option-slots in a grid. Each has a spinner, then a
  thumbnail + "Use this one" button once `option_completed` arrives.
- [x] On pick: `pickVariantOption(dataUrl, modification)` turns the
  chosen data URL into a File, POSTs to `/preview`, and feeds the
  result through renderResults + session history.
- [x] Per-option pending/done/failed states via CSS classes on the
  slot. `batch_done` and `option_failed` handled.

### Phase 6 — verification + polish

- [ ] **Blocked on user:** real-image smoke test of `/kit` with a
  button source → verify panel/checkbox/progress_bar all come out
  in the same visual style. Inspect by eye.
- [ ] **Blocked on user:** same with a checkbox source.
- [ ] **Blocked on user:** variant batch smoke test — type a
  modification, see three options, pick one, confirm the state
  pipeline runs on the picked image.
- [x] Error-handling review (code): `_kit_event_stream` and
  `_variant_options_stream` both wrap each Gemini call in try/except
  and emit `*_failed` events instead of killing the whole stream.
  `_read_upload` rejects empty uploads + missing API key.
- [x] Lessons captured: SSE pattern, 3-image role separation,
  revert-the-revert strategy, uvicorn --reload caveats on Windows.
- [x] Commit messages authored as `Jeremyliu-621
  <jeremyliu621@gmail.com>` via `-c user.name/user.email` +
  `--author=` on every commit. Git config itself untouched.

### Handoff for when Jeremy wakes up

Live servers:
- `:8000` — worktree-demo-both (safe, normal = passthrough)
- `:8001` — worktree-normal-regenerate (preferred, normal = regen)
- `:8002` — worktree-kit-batch (this initiative — all of :8001 plus
  /kit, /variant/options, kit UI, batch picker UI)

To smoke test on :8002:
1. Hard-refresh the page
2. Upload any button/panel/checkbox/progress_bar
3. Click "Generate variant" — should see 3 option slots filling in
   one at a time (SSE working)
4. Click "Use this one" on any — should run /preview on that pick,
   land back in a normal results view, session history updated
5. Click "Generate matching kit" — should see 3 progress rows, one
   per target component type, filling sequentially
6. Each kit member gets its own download button when it completes

What's NOT built:
- `/kit/bundle` single-zip download. Per-member zip downloads are in
  place — assemble-as-one is still nice-to-have.
- Automated smoke test (mocked Gemini). Would catch event-sequence
  regressions without burning real API credits. Low priority.

<!-- resume here: Phase 6 — real-image smoke tests. :8002 is serving kit-batch. Three human-tested flows to confirm: (a) upload a pixel-art button, click 'Generate matching kit', verify 3 SSE progress rows fill and 3 kit-member cards render with coherent style. (b) type 'change label to STOP' in the variant box, verify 3 options appear + picking one runs the state pipeline + banner + history. (c) error path: intentionally break the Gemini key, confirm a component_failed / option_failed row renders red with the error tooltip. After eyeballing all three, mark initiative complete and archive this TODO. -->

### Review

_Filled in when the initiative closes: what shipped, what surprised us,
what belongs in lessons.md or MEMORY.md._
