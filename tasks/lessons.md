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

## Constraints & gotchas

_Things the model, Godot, or external services will do that bit us once and
shouldn't bite us twice._

## Superseded

_Old decisions that got reversed. Keep them — "why we don't do X anymore"
is as valuable as "why we do Y"._
