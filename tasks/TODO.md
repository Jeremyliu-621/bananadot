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
- [x] CSS for stage, chips, size slider, state readout, per-widget styling
- [x] HTML: new `step-playground` + "Open playground" launcher on results
- [x] JS: per-type widget builder (`_pgButton/_pgCheckbox/_pgPanel/_pgProgress`);
  chips switch active entry; size slider scales via CSS transform.
- [x] Live state readout tracks mouseenter/leave/down/up for buttons,
  drags for progress, toggles for checkbox.
- [x] "Back to results" button; preserves results view via `show()`.
- [x] Committed under Jeremy.
- [ ] **Blocked on user:** visual verify at :8005 — upload any component
  (or several), click "Open playground", hover/click/toggle/drag,
  confirm each interaction works and the state readout updates.

<!-- resume here: user smoke-test on :8005 when awake. If the playground feels good, cherry-pick 62e7d0e into kit-batch. Obvious polish knobs if he wants more: (1) keyboard shortcut on button widgets (press spacebar to toggle disabled), (2) pinch-to-zoom for touch devices, (3) multi-widget mode — show all four component types side-by-side at once. -->

### Review

_Filled in when the playground renders, interactions work, chips
switch, slider scales._
