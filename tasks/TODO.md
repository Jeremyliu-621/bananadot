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
- [ ] CSS for remix-section, remix-stage, remix-controls (sliders)
- [ ] HTML: launcher on results + `step-remix` with entry picker,
  preview img, hue/saturation/brightness sliders with numeric readouts,
  "save as new variant" button, "back"
- [ ] JS: openRemix() populates picker, shows most-recent entry.
  Slider handlers update preview `<img>` element's inline
  `style.filter` live. Save button: for each variant key, load source
  → draw to Canvas with filter → toDataURL. Assemble a new data
  object matching the /preview response shape, push to sessionHistory
  with a filter-readout label ("+120° · 1.2×").
- [ ] Empty state when sessionHistory is empty.
- [ ] Commit under Jeremy.
- [ ] Verify at :8009 — upload a component, click Recolor, move
  sliders, hit Save, see the new entry appear in the session strip
  back on the results page.

<!-- resume here: start with CSS for the stage + a slider control row. Inline filter on the preview image uses `style.filter = ...`. Save button creates a NEW sessionHistory entry with baked-in colors, so the user can then use the recolored version in mockup / playground / compare / poster / livedemo. -->

### Review

_Filled in when recolor commits a new variant that shows up in history._
