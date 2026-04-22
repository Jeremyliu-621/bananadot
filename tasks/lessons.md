# Project Memory

<!--
HOW TO USE THIS FILE
====================
Persistent facts about THIS project that should survive across sessions.
Three things this file is NOT:
  - Rules for how Claude should behave        → that's CLAUDE.md
  - In-flight work, plans, or checklists      → that's TODO.md
  - Anything derivable from code or git log   → don't duplicate the repo

This file is for the stuff future-you wouldn't figure out by reading the
code: decisions that were made, constraints that were discovered, the
"why" behind non-obvious choices.

WHEN TO WRITE HERE
- User corrects an approach → capture the correction + why.
- A design decision gets made (stack, API shape, pipeline order, file layout).
- A real-world constraint surfaces (rate limit, model quirk, Godot gotcha,
  perf ceiling).
- "How it's wired" knowledge that would take 20 min to rediscover from code.

WHEN NOT TO WRITE HERE
- It's already in the code or commit messages.
- It's about the current task (→ TODO.md).
- It's a global preference about Jeremy or Claude's style (→ ~/.claude memory).

FORMAT FOR EACH ENTRY
- One decision/fact per entry.
- Dated: `(YYYY-MM-DD)` next to the title.
- Lead with the rule/fact, then:
    **Why:** the reason (incident, constraint, user preference)
    **How it applies:** when this should shape future work
- Newest entries at the top of each section.

WHEN TO PRUNE
- An entry contradicts current reality → update it, don't stack a new one.
- A decision gets reversed → move the old entry to "Superseded" with
  the date it was replaced. Don't silently delete — the history matters.
-->

## Decisions

_Newest first. Format: `### Title (YYYY-MM-DD)` then the rule + Why + How it applies._

### Godot 4 web HTTPRequest silently drops callbacks — use postMessage + data URLs (2026-04-21)

In the Godot 4.6 web export, `HTTPRequest.request()` fires (returns
`RESULT_SUCCESS`) but the `request_completed` signal never emits for
same-origin URLs the browser itself can `fetch()` fine. The texture is
fetched somewhere in Emscripten-land but the Godot-side callback
doesn't run. Hit this while building the Godot embed iframe for
bananadot results.

**Why:** We verified via `fetch()` in the parent page that the URL
returned 200 with the correct MIME, and the textures were served from
the SAME origin as the iframe. No CORS, no preflight, no redirect. The
`err` from `http.request()` was 0. So it's a known/unfixed quirk of
Godot's web `HTTPRequest` — not a configuration issue.

**How to apply:** For the bananadot viewer and any future Godot 4 web
iframe use-case, ship textures/bytes via `postMessage` from the parent
frame as `data:image/png;base64,...` URLs and decode inline with
`Marshalls.base64_to_raw` + `Image.load_png_from_buffer`. Avoid
`HTTPRequest` entirely in web builds unless you're OK with debugging
Godot internals. Bonus: this path also lets client-only features
(recolor, canvas filters) show up in the Godot preview without a
backend round-trip.

### GDScript type inference breaks on `Dictionary.keys()` iteration (2026-04-21)

`for key in my_dict.keys(): var x := base_str + key + ".png"` fails
at parse time with "Cannot infer the type of 'x' variable because the
value doesn't have a set type." The fix: cast inside the loop —
`for key in my_dict.keys(): var s := String(key); var x := base_str + s + ".png"`.

**Why:** `Dictionary.keys()` returns `Array[Variant]`. String + Variant
has no statically-known type, so `:=` inference fails. Caught this
shipping the bananadot Godot viewer — parse error broke the WASM load
on browser.

**How to apply:** Any time a GDScript for-loop binds a key/value from
a Dictionary and you want typed locals downstream, cast the loop var
to its concrete type on the first line of the loop. Or use untyped
`var x = ...` if you really don't care.

### SSE for long Gemini operations, not polling or fake progress (2026-04-20)

`/kit` and `/variant/options` return `StreamingResponse` with media type
`text/event-stream`, yielding newline-terminated `data: {json}\n\n`
frames. The async generator does the actual Gemini calls via
`asyncio.to_thread(blocking_fn, ...)` so the event loop stays free to
flush events out to the browser between component/option completions.
Frontend reads via `fetch()` + a generic `parseSSE(res, cb)` helper that
walks the `ReadableStream` — NOT `EventSource`, because that only does
GET requests and we need multipart POST.

**Why:** Kit generation is 3 components × ~4 states each = up to 12
Gemini calls, wall time ~60–90 s. Without real progress the UI feels
broken. Polling would need a task_id/session mechanism. SSE is one
long-lived response, dead simple. `asyncio.to_thread` is the seam
between FastAPI's async world and the sync google-genai SDK.

**How it applies:** Any future long-running endpoint (multi-step Gemini
work, batch jobs) should follow the same shape — `AsyncIterator[bytes]`
generator, `_sse(event, data)` helper, `asyncio.to_thread` for sync
libraries. Keep events small and idempotent on the UI side.

### Three reference images with role separation (2026-04-20)

`generate._call_nano_banana` now takes 1, 2, or 3 reference images,
always in the same positional order:
  1. SOURCE (always) — STYLE_AND_SUBJECT_REFERENCE
  2. CONSISTENCY_ANCHOR (after the first state of a run) — match
     dimensions/rendering exactly
  3. STYLE_FAMILY_REFERENCE (kit generation only) — match art style
     but NOT shape/subject

Each image's role gets an explicit `use_for` / `must_not_extract` list
in the JSON prompt payload so Gemini doesn't leak one role into
another.

**Why:** The critical split for kit generation is "copy the look, not
the shape." Without explicit `must_not_extract: [silhouette,
subject_content, dimensions]` on image_3, Gemini will copy the
reference button's shape into the generated checkbox.

**How it applies:** When adding a fourth reference image (unlikely but
possible), extend `_collect_image_refs` rather than adding ad-hoc
slots. The positional contract (1=source, 2=anchor, 3=family) is what
the prompt preamble relies on.

### Revert-the-revert preferred over rebase/restart for short-lived branch divergence (2026-04-20)

When kit-batch (forked from demo-both, which had the "normal is
special" revert) needed the :8001 behavior (no passthrough), we used
`git revert 79ac3fe` on kit-batch rather than rebasing or restarting.

**Why:** Option 1 produces one clear undo-of-the-undo commit in 10
seconds. Options 2–4 (rebase, restart, merge) give cleaner history
only at the cost of minutes of re-setup — not worth it when the
branch has almost no committed work yet. Also: squash-merge at final
integration time erases the "revert of revert" noise anyway.

**How it applies:** When a feature branch needs the inverse of a revert
that already happened on its base, reach for `git revert <revert-sha>`
first. Reserve rebase/restart for long-lived branches where the
history will be consumed by humans browsing it.

### uvicorn --reload on Windows is unreliable; hard-kill on mismatch (2026-04-20)

When routes or imports behave unexpectedly after an edit, the running
uvicorn is probably stale. WatchFiles occasionally misses rapid
successive saves on Windows and leaves a worker on old bytecode.

**Symptom:** `curl /openapi.json | jq '.paths'` omits a newly-added
route; `python -c "from app.main import app; print(app.routes)"` shows
it fine. The direct import uses the current file; the server is running
an older one.

**Fix:** hard-kill the port owner and restart:
```
powershell "Get-NetTCPConnection -LocalPort 8002 -State Listen | Select -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }"
```
Then `uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload` again.

**How it applies:** Trust `--reload` for style-only edits. For route
additions or signature changes, always verify via `/openapi.json`
before assuming the live server is current. If suspicious, hard-kill.

### Component metadata is duplicated in two places on purpose (2026-04-16)

`generate.STATE_INSTRUCTIONS` (prompt per state per component) and
`godot._SPECS` (states list, canonical state, `.tscn`/README renderers) are
parallel dicts keyed by `component_type`. The web UI has a matching
`COMPONENTS` registry in `index.html`.

**Why:** Each dict lives in its own layer (model prompts / Godot emission /
browser rendering). Pulling them into a single source of truth would couple
the three files across two languages for no real payoff. Instead, `app.main`
boot-time asserts that the backend two agree, and the frontend's registry is
checked-in alongside the template so drift is reviewable in one PR.

**How it applies:** When adding a new component type, touch all three places
in one commit: add STATE_INSTRUCTIONS entry, add `_ComponentSpec` with
tscn/readme renderers, add a `COMPONENTS` entry in index.html. Also add the
radio option and live-preview widget HTML.

### Checkbox = TextureButton with toggle_mode, not CheckBox+Theme (2026-04-16)

The generated Godot scene for a checkbox is a `TextureButton` with
`toggle_mode = true`, `texture_normal = unchecked.png`,
`texture_pressed = checked.png`. No `CheckBox` node, no Theme resource.

**Why:** Matches the v1 rule we already used for buttons — zero import
ceremony, drops in and runs. `CheckBox` requires a Theme with icon overrides
to swap sprites, which is more setup than the whole pipeline is worth at v1.
`TextureButton` with toggle_mode covers the full behavior (toggle state
persists, emits `toggled(pressed)` signal) for ~4 lines of scene text.

**How it applies:** When/if we add full Theme resource emission (for proper
radio buttons, tabs, etc.) we'll revisit — until then, keep all toggleable
sprite-swap widgets on the TextureButton path.

### Panel 9-slice preview in the browser uses CSS border-image (2026-04-16)

The live panel preview is a `div` with `border-image-source: url(normal.png)`,
`border-image-slice: 25% fill`, stretching content across a resizable width.
The Godot output uses `NinePatchRect` with `patch_margin_*` auto-computed
from the image as `clamp(4, min(w,h) * 0.25, 64)`.

**Why:** Real 9-slice in the browser requires `border-image` — there's no
simpler primitive. A 25% slice matches the same visual behaviour as the
Godot-side auto-margin, so the web preview and the downloaded scene agree.

**How it applies:** If frames with unusual thick borders start slicing badly,
tune `_PANEL_PATCH_FRACTION` in `godot.py` AND `border-image-slice` in
`index.html` in lockstep — they're the same design decision expressed twice.

## Constraints & gotchas

_Things the model, Godot, or external services will do that bit us once and
shouldn't bite us twice._

## Superseded

_Old decisions that got reversed. Keep them — "why we don't do X anymore"
is as valuable as "why we do Y"._
