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
- [x] CSS for the stage, score panel, health bar, pause checkbox,
  button, click-FX float-up, game-over overlay, empty state, launcher.
- [x] HTML: launcher on results + `step-livedemo` section with a
  host div that JS builds into the game stage (so resets are easy).
- [x] JS: state machine (`_ld.running`/paused/score/health), rAF
  loop with dt-capped-at-100ms, click handler (+1 score, −1.5 HP,
  float-up "+1" fx), pause toggle, game-over overlay, play-again.
- [x] sessionHistory wiring — button required; panel, checkbox,
  progress_bar optional; graceful placeholders for missing types.
- [x] Exit handler cancels the rAF when user clicks "Back".
- [x] Committed under Jeremy.
- [ ] **Blocked on user:** visual verify at :8008 — upload any button,
  optionally generate the kit, click "Play live demo", click the big
  button repeatedly, confirm score ticks, HP drains, game-over
  overlay fires, "Play again" resets.

<!-- resume here: user smoke-test on :8008 when awake. If it feels good, cherry-pick 17d631b into kit-batch. Polish knobs: (1) combo counter + multiplier, (2) keyboard space to click, (3) high-score banner that persists via localStorage, (4) a tiny particle shower on click, (5) shorten drain in pixel-art games and lengthen for vector so games-by-style get their own pacing. -->

### Review

_Filled in when you can actually lose at Banana Clicker._
