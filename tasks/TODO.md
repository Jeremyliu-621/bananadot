# Tasks

<!-- HOW TO USE: see sibling worktrees' TODO.md. One resume marker. -->

## Current initiative: multi-layout mockup scene (tabs)

**Goal:** Elevate the mockup from a single pause-menu scene into a
tabbed showcase. Three tabs: **Pause Menu** (existing) / **HUD** /
**Title Screen**. Each re-arranges the same session history components
into a different UI context. Shows ChatForce "upload one component →
see your whole kit across the entire game UI", not just "one fake
menu."

**Started:** 2026-04-20 (tick 2 of /loop every 2h)
**Base branch:** `worktree-mockup` (commit `ab6a035`)
**Author:** `Jeremyliu-621 <jeremyliu621@gmail.com>`

### Constraints (unchanged from tick 1)

- Pure frontend. No new backend endpoints.
- Don't rewrite the pause-menu code — add layouts alongside.
- Must be testable on wake: upload a button, click "See in a game
  screen", then click between tabs, each shows a different scene.

### Plan

- [x] Spawn worktree `mockup-layouts` from `worktree-mockup` tip
- [x] Boot server on :8004
- [x] Refactor `openMockup()` → `renderMockupTab(key)` dispatcher +
  `MOCKUP_LAYOUTS` registry. Pause menu renamed as `_layoutPauseMenu`.
- [x] Tab bar above stage host. Click handler sets `state.mockupLayout`
  (sticky across back/forth) and re-renders.
- [x] HUD layout: health bar (top-left), score panel (top-right),
  centre crosshair, ability buttons row (bottom-left with Q/W/E hotkey
  badges), minimap card (bottom-right).
- [x] Title layout: title + tagline + full-width START button + footer.
- [x] Committed under Jeremy.
- [ ] **Blocked on user:** visual verify at :8004 — upload any
  component, click "See in a game screen", click between the three
  tabs, confirm each scene renders with the right textures.

<!-- resume here: user visual-test on :8004 when awake. If layouts look good, cherry-pick c3e960f into kit-batch. If a layout feels weak, obvious polish knobs: (1) HUD: make the health-bar fill animated (CSS keyframes slowly draining), (2) Title: animate the START button with a slow pulse, (3) Pause: add a small 'CONTINUE' indicator at the bottom. -->

### Review

_Filled in when the tabs are wired and all three layouts render._
