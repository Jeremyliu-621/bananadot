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
- [ ] Refactor `openMockup()` / `_mockupCenter()` pattern so each
  layout lives in its own builder function — `_layoutPauseMenu()` is
  existing; add `_layoutHUD()` and `_layoutTitle()` as siblings.
- [ ] Add tab bar at the top of the mockup step. Click = switch
  active layout; session history is stored separately from the stage
  DOM so re-rendering is cheap.
- [ ] HUD layout: top-left health bar (panel+progress), top-right
  score panel with dummy number, bottom-row ability buttons
  (3 buttons), optional inventory slot (checkbox?).
- [ ] Title layout: big title + tagline, single Start button centred,
  a small version string using progress bar as a seed spinner (low
  priority if time-constrained).
- [ ] Verify at :8004 — upload any component, click mockup, tab
  through all three layouts, confirm textures render per-layout.
- [ ] Commit each layout separately under Jeremy.

<!-- resume here: refactor openMockup to dispatch on a current-tab state. Create const LAYOUTS = {'pause': _layoutPauseMenu, 'hud': _layoutHUD, 'title': _layoutTitle}. Add tab-bar HTML above the stage host. Click handler sets state.mockupLayout and re-renders. -->

### Review

_Filled in when the tabs are wired and all three layouts render._
