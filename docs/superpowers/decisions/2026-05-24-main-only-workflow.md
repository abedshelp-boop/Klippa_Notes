---
title: Canvas redesign git workflow — main only
date: 2026-05-24
status: decided
supersedes: this file's earlier version (worktree-convention.md)
---

# Main-only git workflow

## Decision

Every session in the canvas redesign — and the project in general — works **directly on `main`**:

```bash
git pull
# ... do the work, commit in small focused steps ...
npm test && npm run typecheck   # confirm green
git push origin main
```

No feature branches. No PRs. No worktrees. If a push lands a broken commit on main, recover with `git revert <sha> && git push`.

## Why

Abed is the sole developer. PR-style ceremony (review, isolation, merge) provides safety for teams and adds friction for solo work. The discipline PRs offer is replaced by:

- **Local verification** before each push: tests pass, typecheck adds no new errors, the app actually runs in dev.
- **Small descriptive commits** so `git log` is the review surface.
- **Sequential sessions** for the canvas redesign — one sub-project at a time, finishing each before starting the next, so push races don't happen.

## What this replaces

The earlier `2026-05-24-worktree-convention.md` decision (committed an hour before this one) said each session should use a worktree, a `canvas/<n>-<short-name>` branch, and a PR. That ceremony was wrong for this project. Renaming + rewriting that doc here so the decision history is honest.

## What sub-projects do

Each sub-project session:

1. `git pull origin main` — start from the latest.
2. Read the relevant prompt in `docs/superpowers/plans/2026-05-24-canvas-redesign-session-prompts.md`.
3. Do the work. Commit per task. `git push origin main` when verification passes.

The dependency ordering still matters:
- Session 1 before 2.
- Session 1, 2, 5 before 6.
- All before 7.
- Sessions 3, 4, 5 don't strictly depend on each other.

## CSS namespace prefixes (collision avoidance, still in force)

Even without branch-level isolation, namespacing keeps each session's CSS from stepping on others:

- Sub-project 1: `.ic-` (inner canvas)
- Sub-project 3: `.oc-` (outer canvas)
- Sub-project 5: `.bubble-` (bubble + picker)
- Sub-projects 2, 4, 6: inherit from the namespaces they extend.

## Shared files at risk

These get touched by multiple sub-projects. Pull main fresh before editing them, keep edits additive:

- `src/App.jsx` — multiple sub-projects swap top-level components.
- `src/lib/types.js` — additive only, never rename a field, never remove a field without a `schemaVersion` bump and a migration in `src/lib/canvas/migrate.js`.
- `package.json` — multiple sub-projects add deps.
- `python-service/main.py` — multiple sub-projects add endpoints.

## Tag retained

The `canvas-foundation-v1` tag was created on the foundation merge commit and remains as a historical marker pointing at "everything Session 0 produced." Useful for `git diff canvas-foundation-v1..HEAD` to see what the redesign has added since the foundation.
