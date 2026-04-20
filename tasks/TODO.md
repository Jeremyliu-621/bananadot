# Tasks

## Current initiative: kit poster (one PNG of the whole session)

**Goal:** A new "Export kit poster" button on the results page composites
every session-history entry into a single shareable PNG: title, component
tiles in a grid with labels, palette swatches, dated footer. The artifact
a user actually wants to post on X or drop in a deck.

**Started:** 2026-04-20 (tick 5 of /loop 2h)
**Base branch:** `worktree-compare` (commit `e9984c7`)
**Author:** `Jeremyliu-621 <jeremyliu621@gmail.com>`

### Why Canvas, not dom-to-image

Our CSS uses border-image, clip-path, CSS custom properties. DOM-rasterize
libraries have bugs with all three. We have the raw PNG data URLs already;
composite them onto a native `<canvas>` with layout math. No third-party
libraries. Reliable across browsers.

### Canvas layout (1600×900)

```
 ┌────────────────────────────────────────────────────┐
 │             BANANADOT KIT                          │  title (48px)
 │             bananadot · 2026-04-20                 │  subtitle (14px)
 │                                                    │
 │   ┌───┐   ┌───┐   ┌───┐   ┌───┐                    │
 │   │btn│   │pnl│   │chk│   │prg│                    │  tile grid
 │   └───┘   └───┘   └───┘   └───┘                    │  (up to 6 tiles)
 │   normal  panel   checkbox progress                │
 │                                                    │
 │   ┌───┐   ┌───┐                                    │
 │   │...│   │...│                                    │
 │                                                    │
 │ ───────────────────────────────────────────────    │
 │ [■][■][■][■][■]             made with bananadot    │  footer
 └────────────────────────────────────────────────────┘
```

### Plan

- [x] Spawn `poster` worktree from compare tip
- [x] Boot server on :8007
- [x] CSS: poster-section, poster-stage, poster-actions, launcher
- [x] HTML: launcher + `step-poster` with canvas host + download button
- [x] JS: `openPoster()` loads all history images, draws title +
  subtitle + tile grid + palette swatches + footer on a 1600×900
  canvas. `_drawTile` renders checkerboard + image + label per entry.
- [x] Grid math: auto-picks cols based on N entries (≤3 = one row,
  4 = 4 cols, 5–6 = 3×2).
- [x] Palette from `source_analysis.dominant_colors`, deduped.
- [x] Pixel-art rendering preserved: imageSmoothingEnabled toggles per
  entry.
- [x] Committed under Jeremy.
- [ ] **Blocked on user:** visual verify at :8007 — upload 2–3
  components (or a kit), click Export kit poster, see the canvas
  preview, click Download PNG, confirm the file opens with all tiles
  visible.

<!-- resume here: user smoke-test on :8007 when awake. If the poster looks good, cherry-pick f613ca7 into kit-batch. Polish knobs: (1) choose between multiple layout styles (landscape vs portrait vs grid-only), (2) add the user's source image as a hero at the top, (3) show ALL history entries (not just 6 most-recent) with auto-pagination if more than 6. -->

### Review

_Filled in when a poster downloads cleanly and shows all components._
