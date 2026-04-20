# Tasks

## Current initiative: "Recolor" palette remix

**Goal:** A new "Recolor" button on the results page opens a live
color-shift tool. Pick any session-history entry; three sliders
(hue / saturation / brightness) apply CSS filters to the preview in
real time. On save, the filters bake into fresh PNG data URLs for
every state variant via Canvas 2D `ctx.filter`, and the recolored
variant is pushed to session history as a new entry.

Creative iteration without another Gemini round-trip. Great for
exploring "what if this button were teal instead of green?" in 3
seconds instead of 30.

**Started:** 2026-04-20 (tick 7 of /loop 2h)
**Base branch:** `worktree-livedemo` (commit `6013e3e`)
**Author:** `Jeremyliu-621 <jeremyliu621@gmail.com>`

### Why Canvas filter works

`ctx.filter` accepts CSS filter strings in modern browsers. We load
each state image, `ctx.filter = "hue-rotate(...) saturate(...) ..."`,
`ctx.drawImage()`, `canvas.toDataURL('image/png')`. The filters bake
in — the output is a regular PNG with the shifted colors. Reliable
across Firefox, Chrome, Safari, Edge.

### Plan

- [x] Spawn worktree `remix` from livedemo tip
- [x] Boot server on :8009
- [x] CSS: remix-section, remix-stage, remix-layout grid, sliders,
  actions, state chips, empty state, launcher.
- [x] HTML: launcher + `step-remix` with header + body host (built by
  JS so empty state is easy) + state-chip row.
- [x] JS: `openRemix()` populates entry picker and sliders; live
  preview uses inline `style.filter`. State chips let user preview on
  any specific variant key. `_saveRemix()` bakes filters into all
  variant keys via Canvas 2D `ctx.filter` + `toDataURL`, pushes a new
  sessionHistory entry with a filter-readout label.
- [x] Empty-state when sessionHistory is empty.
- [x] Committed under Jeremy.
- [ ] **Blocked on user:** visual verify at :8009 — upload any
  component, click Recolor, drag the hue slider, hit Save, go back to
  results, confirm the new remix entry appears in the session strip
  and in the mockup/playground/etc views.

<!-- resume here: user smoke-test on :8009 when awake. Polish knobs if he wants more: (1) preset chip row (warm / cool / mono / inverse / pastel), (2) per-color swap (click a dominant-color swatch → picker opens → per-pixel remap via canvas pixel iteration for pixel-art entries), (3) hue/sat animated over time as a looping showcase, (4) Ctrl+Z / Ctrl+Shift+Z to step through slider changes. -->

### Review

_Filled in when recolor commits a new variant that shows up in history._
