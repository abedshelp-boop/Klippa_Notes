---
title: Canvas redesign worktree + branch convention
date: 2026-05-24
status: decided
---

# Canvas redesign worktree convention

## Branch naming

`canvas/<n>-<short-name>`, where `<n>` is the sub-project number from `docs/superpowers/plans/2026-05-24-canvas-redesign-session-prompts.md`:

- `canvas/0-foundation` (this PR)
- `canvas/1-inner-foundation`
- `canvas/2-inner-primitives`
- `canvas/3-outer-pinboard`
- `canvas/4-dictation-models`
- `canvas/5-voice-routing`
- `canvas/6-structure-aware-placement`
- `canvas/7-integration`

## Base ref

- Foundation (this PR) branched off main HEAD at the time of session start.
- Sub-projects 1, 3, 4, 5: branch off the **`canvas-foundation-v1` tag** (the merge commit of this PR).
- Sub-project 2: branch off latest main (after Sub-project 1 merges).
- Sub-project 6: branch off latest main (after Sub-projects 1, 2, 5 merge).
- Sub-project 7: branch off latest main after all the others merge.

## Worktree location

Each session creates its worktree under `.claude/worktrees/<branch-suffix>/` in the main repo. Use:

```bash
git worktree add ".claude/worktrees/canvas-1-inner-foundation" -b canvas/1-inner-foundation canvas-foundation-v1
```

Note the explicit base ref — the `using-git-worktrees` skill default may differ.

## CSS namespace prefixes (collision avoidance)

Already declared in session-prompts. Recapped here for one-stop reference:

- Sub-project 1: `.ic-` (inner canvas)
- Sub-project 3: `.oc-` (outer canvas)
- Sub-project 5: `.bubble-` (bubble + picker)
- Sub-projects 2, 4, 6: inherit from the namespaces they extend.

## Shared files at conflict risk

Sub-projects must read these before editing and prefer additive changes:

- `src/App.jsx` — multiple sub-projects swap top-level components.
- `src/lib/types.js` — additive only, never rename a field, never remove a field without a `schemaVersion` bump.
- `package.json` — multiple sub-projects add deps.
- `python-service/main.py` — multiple sub-projects add endpoints.

## Tag

This PR's merge commit is tagged `canvas-foundation-v1` and pushed. That is the canonical branching point for Sub-projects 1, 3, 4, 5.
