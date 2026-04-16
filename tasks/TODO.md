# Tasks

<!--
HOW TO USE THIS FILE
====================
Active plan for the current initiative. One TODO.md at a time — don't spawn
parallel plans. When an initiative wraps, move this file to
tasks/archive/YYYY-MM-DD-<name>.md and start a fresh TODO.md for the next one.

STATUS MARKERS
- [ ]  todo
- [~]  in progress (only one at a time)
- [x]  done
- [?]  blocked — next line explains why

THE `<!-- resume here -->` MARKER
- Exactly one in the file, always.
- It points at the very next action you'd take if the session ended right now.
- First thing to read when resuming work in a new session — jump straight to it.
- Move it every time you finish a step. Stale resume markers are worse than none.

WHEN TO UPDATE
- Before starting: skim the plan, confirm it still matches reality.
- After each meaningful step: tick the box, move `<!-- resume here -->`.
- On blocker: flip to [?], note the blocker on the next line, move resume
  marker to whatever unblocks it.
- On user correction: fix the plan AND consider whether MEMORY.md needs
  an entry for the lesson.

WHEN TO START A NEW PLAN
- Current initiative is done (archive this file first).
- Scope pivots enough that the existing checklist is stale.
- Never "just rewrite" an active plan silently — either archive or explicitly
  supersede with a note.

KEEP IT SHORT
- If a step has 3+ sub-steps, break it out as its own plan or sub-list.
- Delete finished sections you don't need to reference anymore; git has history.
-->

## Current initiative: v0 end-to-end pipeline

**Goal:** Drop a cropped UI-element image in, get back a Godot component zip that works. Prove the loop, then wrap in a web UI.
**Started:** 2026-04-16

### Plan

**Phase 1 — backend pipeline (callable by HTTP, no UI yet)**

- [x] Scaffold Python backend: `pyproject.toml`, FastAPI skeleton, env config, stubbed pipeline modules
- [x] `pipeline/generate.py` — call Nano Banana with reference image + state instruction; return PNG bytes per requested state
- [x] `pipeline/cleanup.py` — alpha-bbox trim, size-align all variants, detect-if-pixel-art + palette snap + nearest-neighbour downsample when true
- [x] `pipeline/godot.py` — emit `example.tscn`, `README.md` from a template, drop PNGs alongside. (Swapped plan: TextureButton instead of Theme+StyleBoxTexture for v1 — drops in with zero import ceremony. Theme can return when we add 9-slice panels.)
- [x] `pipeline/bundle.py` — zip the output folder
- [x] Wire `/generate` endpoint: accept image + component type → run pipeline → return zip
- [x] Offline chain verified with synthetic inputs (cleanup → godot → bundle)
- [~] Smoke test with a real pixel-art button and one flat-vector button. Inspect outputs by eye, drop zip in a Godot project, verify hover/press.

**Phase 2 — web UI (demo surface)**

- [ ] Next.js + shadcn + Tailwind skeleton in `frontend/`
- [ ] Upload page: drag-drop, component-type dropdown, generate button
- [ ] Call backend, show loading, render preview grid (original | normal | hover | pressed | disabled)
- [ ] Download-zip button

**Phase 3 — polish for the demo**

- [ ] Live CSS mock of the Godot component so they see it "work" in-browser before download
- [ ] Error + loading states
- [ ] Style pass (ChatForce look, or neutral-clean if no brand guide handed over)

### Open items (not blocking)

- Which art styles to stress-test on in step 7 of Phase 1. I'll grab one pixel-art and one clean-vector from free asset sites unless Jeremy hands me specific inputs.
- Exact Gemini model id — starting with `gemini-3-pro-image` per the Nov announcement; if the Nano Banana 2 unified endpoint is live by the time we call, swap it.

<!-- resume here: real-image smoke test. Server runs with `cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app`. Post a cropped button PNG to POST /generate with component_type=button (or open /docs). Inspect the returned zip's contents, then drop the folder into a Godot 4 project at res://bananadot_button/ and open example.tscn. If the textures look wrong: start by inspecting the raw Nano Banana outputs BEFORE cleanup (log them out of generate.py) to separate model quality issues from pipeline bugs. -->

### Review

_Filled in when the initiative closes: what shipped, what surprised us,
what belongs in MEMORY.md, what to archive._
