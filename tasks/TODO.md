# Tasks

## Current initiative: "Banana Clicker" — playable live demo

**Goal:** A new "Play live demo" button on the results page opens a
tiny playable microgame built from whatever the user has in session
history. Score panel, health bar, clickable button, pause checkbox —
all wearing real generated textures. The demo moment where the
components stop being gallery pieces and start playing a role in a
game loop.

**Started:** 2026-04-20 (tick 6 of /loop 2h)
**Base branch:** `worktree-poster` (commit `cb6b00b`)
**Author:** `Jeremyliu-621 <jeremyliu621@gmail.com>`

### Game design (intentionally simple)

- **Banana Clicker:** click the button to score points. Each click
  drains a small amount of health. Health also drains slowly over
  time. When health hits 0 → game over.
- Display:
  - **Score counter** at top, backed by the user's panel texture
  - **Health bar** below, using their progress_bar textures (fill
    clip-path from 100% down to 0%)
  - **Big button** centered, using their button textures (real
    hover/pressed states)
  - **Pause checkbox** in a corner — uses their checkbox texture
  - Game over state: overlay with final score + "Play again" button
- **State machine:** `idle → playing → paused → gameover → idle`
- **No high-score persistence** (would require localStorage; out of
  scope for this tick).

### Plan

- [x] Spawn worktree `livedemo` from poster tip
- [x] Boot server on :8008
- [ ] CSS for live-demo scene (background, score/health panels,
  clickable button, pause toggle, game-over overlay)
- [ ] HTML: launcher button on results + new `step-livedemo` section
- [ ] JS: game state machine + requestAnimationFrame loop for health
  drain; click increments score and dings health; pause freezes the
  loop; game-over blocks clicks.
- [ ] Uses `sessionHistory` to grab a button (required), panel
  (optional), checkbox (optional), progress_bar (optional). Falls back
  to CSS-placeholder UI when a type is missing.
- [ ] Commit under Jeremy.
- [ ] Verify at :8008 — upload a button, optionally generate the
  matching kit, click "Play live demo", click button repeatedly,
  confirm health drains, game over fires, play-again resets.

<!-- resume here: add CSS for .livedemo-stage, .livedemo-score, .livedemo-health, .livedemo-button, .livedemo-pause. Use CSS custom props (--ld-*) for the session textures so JS sets them once per entry. -->

### Review

_Filled in when you can actually lose at Banana Clicker._
