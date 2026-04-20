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
- [ ] CSS for the poster step (preview + download button)
- [ ] HTML: launcher on results + `step-poster` with a `<canvas>` host
- [ ] JS: `openPoster()` builds the canvas asynchronously (loads each
  history entry's source data URL into an `Image`, draws with layout
  math). Shows canvas inline + a "Download PNG" button. "Back" returns
  to results.
- [ ] Layout math: dynamic grid (1–6 tiles). Tile size scales to fit.
  Checkerboard behind each tile matches the rest of the app.
- [ ] Palette swatches from the most-recent entry's
  `source_analysis.dominant_colors` (or first five from all entries
  combined).
- [ ] Test at :8007 — upload 2–3 components, click Export kit poster,
  confirm canvas renders + download works.
- [ ] Commit under Jeremy.

<!-- resume here: write the openPoster / _drawPoster / _downloadPoster JS. Canvas is 1600×900, 60px padding. Title uses Inter 48 weight 700, subtitle Inter 14 weight 400. Tiles: 3-column grid if <=3 entries, 4-column if 4, 3×2 if 5-6. -->

### Review

_Filled in when a poster downloads cleanly and shows all components._
