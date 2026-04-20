# Tasks

<!-- HOW TO USE: see sibling worktrees' TODO.md. One resume marker. -->

## Current initiative: interaction playground

**Goal:** Add a new button on the results page: **"Open playground"**.
Opens a hands-on surface where every component in session history is
fully interactive — hover buttons for real hover-state swap, click
for pressed, toggle checkboxes, drag a slider to drive progress-bar
fill, scale components up and down with a size slider. Demo audience
stops looking at static previews and actually *uses* the kit.

**Started:** 2026-04-20 (tick 3 of /loop 2h)
**Base branch:** `worktree-mockup-layouts` (commit `157a2d3`)
**Author:** `Jeremyliu-621 <jeremyliu621@gmail.com>`

### Constraints (unchanged)

- Pure frontend. No backend calls.
- NEW button + NEW step. Don't revamp existing code.
- Fallback: empty session history renders an "upload first" prompt.
- Testable on wake: upload any component, click "Open playground",
  interact with it.

### Design — the playground screen

```
    [← Back to results]                    [size slider ────○──── 3×]

    ┌──────────────────────┐
    │ (checkerboard bg)    │    <- the active component (big)
    │   [component HERE]   │       hover / click / etc actually works
    │                      │
    └──────────────────────┘

    state: pressed                       <- live readout of current state

    [component chips ·······················]    <- click chip to switch which
                                                    session-history entry is
                                                    displayed
```

- **Size slider** (1×..5×) scales the hit area so the user can test
  how the component feels at game resolutions. CSS `transform: scale()`
  doesn't blur on pixel art because `image-rendering: pixelated` sticks.
- **Component chips** at the bottom list each session-history entry
  (label + thumbnail). Clicking a chip swaps the active component.
- **Live state readout** watches mousedown/mouseup/mouseenter/mouseleave
  and updates "state: hover" / "pressed" / etc so the user sees what's
  happening.
- **Progress bar** variant: swap the big component for a slider drag —
  a 0–100% slider whose value sets the `clip-path` inset on the fill
  texture. Feels like a real in-game progress bar.

### Plan

- [x] Spawn worktree `playground` from `worktree-mockup-layouts` tip
- [x] Boot server on :8005
- [ ] CSS for the playground stage, chips, size slider, state readout
- [ ] HTML: new `<section id="step-playground">` + "Open playground"
  button on the results page (below the mockup launcher)
- [ ] JS: `openPlayground()` renders chips per session-history entry,
  `renderPlaygroundComponent(entry)` shows one entry big, wired with
  interactive textures per-component-type. Per-type renderer:
    - button: TextureButton behavior (hover/active/disabled)
    - checkbox: click to toggle, sprite-swap
    - progress_bar: 0..100 slider driving clip-path
    - panel: border-image stretched to the resized box
- [ ] Live state readout element, wired to mouse events on the active
  widget.
- [ ] "Back to results" button; exiting preserves results view.
- [ ] Commit each chunk under Jeremy.
- [ ] Verify at :8005 — upload a button, generate, click "Open
  playground", confirm hover/click/scale all work.

<!-- resume here: write the CSS block for .playground-stage, .playground-widget, .playground-chip. Use CSS custom props for textures like other features so JS just sets --pg-* per active entry. -->

### Review

_Filled in when the playground renders, interactions work, chips
switch, slider scales._
