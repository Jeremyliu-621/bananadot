# Tasks

<!-- HOW TO USE: see sibling worktrees' TODO.md. One resume marker. -->

## Current initiative: compare slider (before/after reveal)

**Goal:** A new "Compare" button on the results page opens a split
before/after view. User picks two session-history entries via
dropdowns, the stage shows entry A on the left half and entry B on the
right half, separated by a draggable vertical divider. Drag the
divider to scrub between them.

Classic before/after reveal pattern (Google Maps old/new, design-diff
tools). For bananadot: START button vs STOP variant, or pixel-art
button vs its recoloured sibling, or original vs kit-generated
checkbox in matching style.

**Started:** 2026-04-20 (tick 4 of /loop 2h)
**Base branch:** `worktree-playground` (commit `42f3ac8`)
**Author:** `Jeremyliu-621 <jeremyliu621@gmail.com>`

### Constraints (unchanged)

- Pure frontend. No backend calls.
- NEW button + NEW step. Don't touch existing code.
- Works even with 1 session entry (falls back to a polite prompt
  asking user to generate more).
- Testable on wake.

### Design

```
   [← back]          A: [chip: button · 01 ▾]     B: [chip: button · STOP ▾]

    ┌────────────────────────┐
    │ left-side img | right  │
    │               |        │
    │      (entry A)|(entry B)│
    │               ‖        │     ‖ = draggable divider
    │               ‖        │
    └────────────────────────┘
           ‖ 50%

    [use source | normal | hover | pressed | disabled]    <- which variant to show
```

- Dropdowns/chips at the top to pick entries A and B.
- Stage is `position: relative`; two layered images (one full-width
  each), the right-side image clipped via `clip-path: inset(0 0 0 X%)`
  where X is the divider position.
- Divider `<div>` positioned at X%, has a thin accent line + a
  circular drag handle in the middle.
- Drag handle listens to pointer events and updates X.
- Bottom chip row: state selector (source / normal / hover / pressed /
  disabled / checked / unchecked / etc) — controls which variant's
  image we display for both sides.

### Plan

- [x] Spawn worktree `compare` from playground tip
- [x] Boot server on :8006
- [ ] CSS for compare stage, layers, divider, state chips
- [ ] HTML: launcher button on results + new `step-compare` section
- [ ] JS: `openCompare()` populates A/B dropdowns from sessionHistory,
  defaults A=most recent, B=second-most-recent. `renderCompareStage()`
  paints current state. Pointer drag on divider updates position.
  State chips re-render with selected state.
- [ ] Empty-state: fewer than 2 history entries → message.
- [ ] Commit each chunk under Jeremy.
- [ ] Verify at :8006 — generate 2 components (or a component + a
  variant), click Compare, drag divider, switch state chip.

<!-- resume here: write CSS for .compare-stage with two layered images and the divider. Use CSS custom props so JS just sets --compare-left / --compare-right / --compare-split (a percentage). -->

### Review

_Filled in when divider drags smoothly and both entries render._
