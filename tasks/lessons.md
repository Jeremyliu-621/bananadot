# Project Memory

<!--
HOW TO USE THIS FILE
====================
Persistent facts about THIS project that should survive across sessions.
Three things this file is NOT:
  - Rules for how Claude should behave        → that's CLAUDE.md
  - In-flight work, plans, or checklists      → that's TODO.md
  - Anything derivable from code or git log   → don't duplicate the repo

This file is for the stuff future-you wouldn't figure out by reading the
code: decisions that were made, constraints that were discovered, the
"why" behind non-obvious choices.

WHEN TO WRITE HERE
- User corrects an approach → capture the correction + why.
- A design decision gets made (stack, API shape, pipeline order, file layout).
- A real-world constraint surfaces (rate limit, model quirk, Godot gotcha,
  perf ceiling).
- "How it's wired" knowledge that would take 20 min to rediscover from code.

WHEN NOT TO WRITE HERE
- It's already in the code or commit messages.
- It's about the current task (→ TODO.md).
- It's a global preference about Jeremy or Claude's style (→ ~/.claude memory).

FORMAT FOR EACH ENTRY
- One decision/fact per entry.
- Dated: `(YYYY-MM-DD)` next to the title.
- Lead with the rule/fact, then:
    **Why:** the reason (incident, constraint, user preference)
    **How it applies:** when this should shape future work
- Newest entries at the top of each section.

WHEN TO PRUNE
- An entry contradicts current reality → update it, don't stack a new one.
- A decision gets reversed → move the old entry to "Superseded" with
  the date it was replaced. Don't silently delete — the history matters.
-->

## Decisions

_Newest first. Format: `### Title (YYYY-MM-DD)` then the rule + Why + How it applies._

### Component metadata is duplicated in two places on purpose (2026-04-16)

`generate.STATE_INSTRUCTIONS` (prompt per state per component) and
`godot._SPECS` (states list, canonical state, `.tscn`/README renderers) are
parallel dicts keyed by `component_type`. The web UI has a matching
`COMPONENTS` registry in `index.html`.

**Why:** Each dict lives in its own layer (model prompts / Godot emission /
browser rendering). Pulling them into a single source of truth would couple
the three files across two languages for no real payoff. Instead, `app.main`
boot-time asserts that the backend two agree, and the frontend's registry is
checked-in alongside the template so drift is reviewable in one PR.

**How it applies:** When adding a new component type, touch all three places
in one commit: add STATE_INSTRUCTIONS entry, add `_ComponentSpec` with
tscn/readme renderers, add a `COMPONENTS` entry in index.html. Also add the
radio option and live-preview widget HTML.

### Checkbox = TextureButton with toggle_mode, not CheckBox+Theme (2026-04-16)

The generated Godot scene for a checkbox is a `TextureButton` with
`toggle_mode = true`, `texture_normal = unchecked.png`,
`texture_pressed = checked.png`. No `CheckBox` node, no Theme resource.

**Why:** Matches the v1 rule we already used for buttons — zero import
ceremony, drops in and runs. `CheckBox` requires a Theme with icon overrides
to swap sprites, which is more setup than the whole pipeline is worth at v1.
`TextureButton` with toggle_mode covers the full behavior (toggle state
persists, emits `toggled(pressed)` signal) for ~4 lines of scene text.

**How it applies:** When/if we add full Theme resource emission (for proper
radio buttons, tabs, etc.) we'll revisit — until then, keep all toggleable
sprite-swap widgets on the TextureButton path.

### Panel 9-slice preview in the browser uses CSS border-image (2026-04-16)

The live panel preview is a `div` with `border-image-source: url(normal.png)`,
`border-image-slice: 25% fill`, stretching content across a resizable width.
The Godot output uses `NinePatchRect` with `patch_margin_*` auto-computed
from the image as `clamp(4, min(w,h) * 0.25, 64)`.

**Why:** Real 9-slice in the browser requires `border-image` — there's no
simpler primitive. A 25% slice matches the same visual behaviour as the
Godot-side auto-margin, so the web preview and the downloaded scene agree.

**How it applies:** If frames with unusual thick borders start slicing badly,
tune `_PANEL_PATCH_FRACTION` in `godot.py` AND `border-image-slice` in
`index.html` in lockstep — they're the same design decision expressed twice.

## Constraints & gotchas

_Things the model, Godot, or external services will do that bit us once and
shouldn't bite us twice._

## Superseded

_Old decisions that got reversed. Keep them — "why we don't do X anymore"
is as valuable as "why we do Y"._
