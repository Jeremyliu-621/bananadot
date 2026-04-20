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
- [ ] CSS for the mockup stage, panel frame, menu buttons, progress
  strip, checkbox row, empty state
- [ ] HTML: new `<section id="step-mockup">` + "See in a game screen"
  button on the results page (below the kit section)
- [ ] JS: `openMockup()` pulls from sessionHistory, keys entries by
  component_type (most recent wins), injects data URLs into CSS custom
  properties. Missing types render placeholder tiles with labels.
- [ ] "Back to results" button. Exiting preserves results view.
- [ ] Visual verify at :8003 — upload a button, generate, click "See in
  a game screen", confirm the scene looks like a game menu.
- [ ] Commit each chunk under Jeremy.

<!-- resume here: add CSS for .mockup-stage and .mockup-panel, using CSS custom properties (--mockup-panel, --mockup-btn-normal, etc.) so JS just sets those props. -->

### Review

_Filled in when the button renders a coherent scene._
