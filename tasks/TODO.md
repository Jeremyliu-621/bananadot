# Tasks

<!-- HOW TO USE: see sibling worktrees' TODO.md. One resume marker. -->

## Current initiative: "See in a game screen" — mockup scene

**Goal:** New button on the results page opens a stylised game pause-menu
mockup assembled from session history. User's button becomes menu items,
panel becomes the frame, progress bar becomes a loading strip, checkbox
becomes a sound toggle. One click turns their single upload into a
coherent UI screen.

**Started:** 2026-04-20
**Base branch:** `worktree-kit-batch` (commit `141e25a`)
**Author:** `Jeremyliu-621 <jeremyliu621@gmail.com>` via `-c user.*` + `--author=`

### Constraints (from /loop prompt)

- NEW button + NEW view. Do not modify existing pipeline code.
- Must be testable when Jeremy wakes up — the button opens something
  compelling even with zero generated components (placeholder fallback).
- Pure frontend. No new backend endpoints.

### Plan

- [x] Spawn worktree `mockup` from kit-batch tip
- [x] Copy .env, boot server on :8003
- [x] CSS for the mockup stage, panel frame, menu buttons, progress
  strip, checkbox row, empty state (CSS custom properties driven)
- [x] HTML: new `<section id="step-mockup">` + "See in a game screen"
  button on the results page (below the kit section)
- [x] JS: `openMockup()` pulls from sessionHistory, picks most-recent
  entries per type, three button slots can each use a different
  history entry so variants (START/STOP/OPTIONS) show up distinctly.
  Missing types fall back to placeholder styling.
- [x] "Back to results" button. `show('mockup')` / `show('results')`
  toggle cleanly via the existing state machine.
- [ ] **Blocked on user:** visual verify at :8003 — upload a button
  (optionally also a panel / checkbox / progress_bar), generate, click
  "See in a game screen", confirm the scene looks coherent.
- [x] Committed each chunk under `Jeremyliu-621`.

<!-- resume here: visually verify on :8003 when Jeremy wakes up. If he likes it, the branch is ready to merge into kit-batch (or cherry-pick 93d2ae6). If he wants polish, obvious follow-ups: (1) a "shuffle" button on the mockup that re-picks history entries so he can flip through combinations, (2) custom labels for the menu buttons (text inputs so he can write 'START' 'OPTIONS' 'QUIT' over the baked-in text), (3) multiple mockup layouts (pause menu / HUD / shop) to show off different uses of the same kit. -->

### Review

_Filled in when the button renders a coherent scene._
