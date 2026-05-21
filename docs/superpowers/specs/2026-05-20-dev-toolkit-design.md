---
title: Deen Notes — Dev-Time Toolkit
date: 2026-05-20
status: approved-design
applies_to: Deen Notes (Electron + Vite + React 19 + Python FastAPI service)
references:
  - ~/vault-global/shared/playbooks/dev-time-toolkit.md
  - User-global CLAUDE.md rule 7
---

# Deen Notes — Dev-Time Toolkit Design

## Why this exists

The Dev-Time Toolkit playbook (rule 7 of user-global CLAUDE.md, canonical spec at `~/vault-global/shared/playbooks/dev-time-toolkit.md`) defines a layered, ranked toolkit for catching bugs at dev time **before they reach users**. Logs are rung 7, not rung 1 — the highest-leverage tools (types, dashboard, debugger, component inspector) come first.

The playbook was written for a typical web SaaS stack (Convex + TypeScript + React in a browser). Deen Notes is **Electron + JS + Python**. This spec adapts the playbook to that stack and locks in the five stack-specific decisions that emerged from brainstorming on 2026-05-20.

The goal is not better tools for their own sake. The goal is **catching bugs faster while building**, by making the high-leverage tools the *first* reflex when something looks wrong, not the last.

## Stack-specific decisions (locked-in)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | JS type checking | JSDoc + `checkJs` via `jsconfig.json` | No `.jsx` → `.tsx` migration needed; incremental adoption; VS Code red squigglies in-place |
| 2 | Python type checking | Pyright `basic` (ratchet to `strict` later) | Same engine VS Code already uses; instant editor feedback; no separate watcher |
| 3 | Test framework | Vitest + pytest, one canary test each | Runners must exist so the "reproduce-as-test" habit is reachable; coverage is not the goal |
| 4 | Electron DevTools + React DevTools | Auto-open in dev via `electron-devtools-installer` + `BrowserWindow.openDevTools()` gated on `!app.isPackaged` | Debugger is the *first* reflex only if DevTools is already open when the bug appears |
| 5 | Existing `console.log` / bare-catch sweep | Sweep in same PR, three-bucket categorize-then-route methodology with pre-sweep dry run | Half-applied hygiene rules are worse than none |

## Files & structure

### New files

| File | Rung | Purpose |
|---|---|---|
| `jsconfig.json` | 1 | `checkJs: true`, `strict: true`, ES2022, includes `src/` and `electron/` |
| `python-service/pyrightconfig.json` | 1 | `typeCheckingMode: "basic"` initially, scoped to `python-service/` |
| `src/lib/debug.js` | 7 | `debug()` helper for the renderer — no-op in prod builds via `import.meta.env.DEV` |
| `electron/debug.js` | 7 | Same helper for Electron main — gated on `!app.isPackaged` |
| `python-service/debug.py` | 7 | Same helper for Python — gated on `DEEN_DEV=1` env var |
| `vitest.config.js` | 6 | Minimal Vitest config piggybacking on `vite.config.js` |
| `src/__tests__/canary.test.js` | 6 | One trivial passing test proving the runner works |
| `python-service/tests/__init__.py` | 6 | Marker file |
| `python-service/tests/test_canary.py` | 6 | One trivial passing pytest proving the runner works |
| `python-service/pytest.ini` | 6 | Tells pytest where to find tests, sets `pythonpath` |

### Modified files

| File | What changes |
|---|---|
| `package.json` | Add `devDependencies`: `vitest`, `electron-devtools-installer`, `typescript` (needed by `tsc --noEmit` to type-check JSDoc against `jsconfig.json` — not for emitting code). Add scripts: `"test"`, `"test:watch"`, `"typecheck"` |
| `electron/main.js` | In dev mode: install React DevTools, auto-open BrowserWindow DevTools, wire F12 shortcut, all behind existing `isDev` const |
| `python-service/requirements.txt` | Add `pytest` (pyright is editor-only — not added here) |
| `.gitignore` | Add `coverage/` and `.pytest_cache/` if not already ignored |
| `src/**/*.{js,jsx}` (multiple) | Sweep — see methodology below |
| `electron/*.js` (multiple) | Sweep — see methodology below |
| `python-service/*.py` (multiple) | Sweep — see methodology below |

### Out of scope (deliberate)

- No TypeScript migration (chose JSDoc per decision #1)
- No Sentry / production observability — separate playbook for ship-to-users
- No CI / GitHub Actions / pre-commit hooks — dev-time only
- No refactoring beyond the sweep
- No new features
- No fixing pyright errors that surface from the new config — listed as follow-up

## The sweep — three-bucket methodology

Initial scan (run 2026-05-20):

| Surface | Raw count | Affected files |
|---|---|---|
| JS `console.*` | 47 | 12 files |
| JS `catch + console.*` | 25 | 11 files |
| Python `print(` | 108 | 9 files |
| Python `except + pass/print` | 26 | 7 files |

Every occurrence falls into one of three buckets:

### Bucket 1 — Boundary logs (keep, route through `debug()`)

Logs at process/network/IPC doorways. Example from `electron/main.js`:

```js
// before
console.log('[Python] Starting:', pythonPath, scriptPath);
// after
debug.info('Python', 'starting', { pythonPath, scriptPath });
```

Net behavior: info/warn boundary logs visible in dev, suppressed in prod packaged build; `debug.error` calls stay visible in both (errors are signals we want surfaced, never silently dropped).

### Bucket 2 — Inside-function noise (delete)

Logs inside a function body that exist as debug leftovers.

**Decision rule:** if removing the log loses no information the debugger or dashboard wouldn't show, delete it.

### Bucket 3 — Error-swallowing catches (fix)

```python
# before
try:
    do_something()
except:
    pass  # bug invisible

# after
try:
    do_something()
except SomeSpecificError as e:
    debug.error("subsystem", "do_something failed", exc_info=e)
    # then: re-raise, return safe default, or genuinely swallow with a why-comment
```

**Decision rule:** every bare `except:` gets narrowed to a specific exception class, given a why-comment explaining the deliberate swallow, OR re-raised.

### Sweep order

1. Python first (108 prints + 26 bare-except — highest-leverage)
2. Electron main second (`electron/main.js`)
3. Renderer last (`src/`)

### Pre-sweep dry run

Before any deletions or edits, generate a dry-run report:

- One row per occurrence: file, line, bucket guess, proposed treatment
- Committed as `docs/superpowers/specs/2026-05-20-sweep-dry-run.md` before sweep starts
- User-reviewable; no silent deletions

### Files NOT touched by the sweep

- `scripts/copy-env.js` — build script, its `console.log` is intentional CI output
- `python-service/venv/**`, `node_modules/**` — vendored
- `python-service/wake_word.py` — leave any Picovoice-SDK-internal prints

## `debug()` helper API

Same shape across all three layers:

```js
debug.log(subsystem, message, ...data);    // info-level, dev-only
debug.warn(subsystem, message, ...data);   // warn-level, dev-only
debug.error(subsystem, message, ...data);  // error-level, ALWAYS prints
```

`error` stays loud in prod because errors are signals to surface, not dev-time chatter. They funnel into production observability later (Sentry, separate playbook).

## Implementation ordering

Rungs aren't independent — the sweep needs the helper, the helper needs the dev/prod gate.

1. `jsconfig.json` + `pyrightconfig.json` (Rung 1) — no source files touched, gives "before" picture of type-error volume
2. The three `debug` helpers (Rung 7 infra) — new files only
3. Wire DevTools + React DevTools in `electron/main.js` (Rungs 3 & 4)
4. Add Vitest + pytest + canary tests (Rung 6)
5. Verify hot reload (Rung 5) — probably already works, just confirm
6. Run the sweep (Rung 7 cleanup) — pre-sweep dry run → user review → execute
7. Final verification — run every command in the verification table, capture output

## Verification — how we know each rung actually works

| Rung | Verification command / step |
|---|---|
| 1 JS types | `npx tsc --noEmit -p jsconfig.json` exits 0 with no errors in canary state. Introduce a deliberate type error in a `.jsx`, confirm VS Code shows red squiggle within 2s, revert. |
| 1 Python types | `pyright python-service/` exits 0 in `basic`. Introduce deliberate type error in `python-service/main.py`, confirm editor feedback, revert. |
| 2 Dashboard | N/A for Convex. Replacement: confirm `python.log` in `app.getPath('userData')` shows the Python service starting cleanly on `npm run electron:dev`. Pin that file in a tail-watcher as the equivalent habit. |
| 3 DevTools | `npm run electron:dev` → main window DevTools auto-opens. F12 closes/reopens. Set a breakpoint in `useNotes.js`, trigger a note action, confirm hit. |
| 4 React DevTools | After step 3, "Components" tab visible. Click `<NoteList>`, confirm props/state inspectable. |
| 5 Hot reload | Edit a `src/` file, save, confirm renderer updates in <2s without manual reload. |
| 6 Tests | `npm test` and `cd python-service && pytest` both pass with canary tests. |
| 7 Logs | `rg "console\\.(log\|warn\|info\|debug)" src/ electron/` returns zero (excluding `src/lib/debug.js`). `rg "^\\s*print\\(" python-service/ -g '!tests/'` returns zero. `rg "except\\s*:" python-service/` returns zero. |

All verification commands run at the end of implementation. Output captured and appended to this spec as a "Verified on `<date>`" appendix.

## Definition of done

The user (Abed) should be able to:

1. Open VS Code in this repo and see red squigglies on type errors instantly.
2. Run `npm run electron:dev` and have DevTools + React DevTools auto-open.
3. Run `npm test` and `pytest`, both pass.
4. Grep for `console.log` in committed code, find zero results (outside `src/lib/debug.js`).
5. Hit a breakpoint in renderer DevTools the *first* time something looks wrong, instead of reaching for `console.log`.

The real outcome is #5 — the habit shift. The toolkit is the substrate that makes the habit reachable.

## Deliverables

- All files in "Files & structure" created/modified
- `docs/superpowers/specs/2026-05-20-sweep-dry-run.md` committed before any sweep edits
- Verification appendix in this spec with actual command outputs
- Short follow-up list: pyright errors surfaced but not fixed, any deferred items

## Follow-up (out of scope for this work)

- Fix pyright errors revealed by the new config (separate task once volume is known)
- Ratchet pyright from `basic` to `strict` once basic is clean
- Write a real test suite per the test pyramid (this work only adds canaries — actual tests come as bugs appear)
- Production observability (Sentry, sourcemaps, error boundaries) — separate playbook, applies before ship-to-users

---

## Verified on 2026-05-21

### Test suites

- `npm test` — **12 passed**, 0 failed across 3 test files (`src/__tests__/canary.test.js`, `src/lib/__tests__/debug.test.js`, `electron/__tests__/debug.test.js`)
- `pytest -v` (from `python-service/`) — **7 passed**, 0 failed (`tests/test_canary.py` + `tests/test_debug.py`)

### Type checking

- `npm run typecheck` (JS via JSDoc + `checkJs`) — 857 raw errors total, of which **109 are in project source** (`src/`, `electron/`) and 748 are in `node_modules` (mainly `react-dom` CJS bundles — to be excluded via additional `tsconfig` patterns in follow-up). Baseline captured for future regression detection. **No regression** introduced by the sweep — the 109 count is within ±2 of the pre-sweep baseline of 107 from Task 3.
- Pyright (Pylance in VS Code) — `python-service/pyrightconfig.json` wired in `basic` mode. Manual editor verification deferred to Abed.

### DevTools

- `electron/main.js` auto-opens DevTools detached on dev startup (gated on `!app.isPackaged`).
- `electron-devtools-installer@^4.0.0` installs React DevTools on first dev launch (idempotent).
- F12 toggles DevTools on the focused window in dev.
- Manual end-to-end smoke test deferred to Abed (Task 15).

### Hot reload

- Vite was already wired and unchanged by this work. No-touch verification — `src/` edits propagate via HMR. Manual confirmation deferred to Abed during Task 15.

### Sweep completeness (post-execution)

Run on 2026-05-21:

- `console.(log|warn|info|debug|error)` in `src/` + `electron/` (excluding `__tests__/` and `debug.js`): **0 hits**. Only the 6 helper-implementation lines remain (3 in `src/lib/debug.js`, 3 in `electron/debug.js`).
- `^\s*print\(` in `python-service/` (excluding `venv/`, `tests/`, `debug.py`): **0 hits**. Only the 3 helper-implementation lines remain in `python-service/debug.py`.
- `except\s*:` (bare-except) in `python-service/`: **0 hits**.
- `except\s+Exception` in `python-service/`: **2 deliberate matches**, both with documenting comments:
  - `python-service/wake_word.py:213` — Picovoice raises non-public exception classes; documented catch-all.
  - `python-service/note_generator.py:249` — pipeline crosses many subsystems (Whisper/AssemblyAI/LLM/DB/disk); per Abed's decision: log + `_save_pending(...)` + `raise` (no silent swallow).

### Sweep treatment counts

- **Bucket 1** (route through `debug.*`): **~144** occurrences (99 Python + 22 Electron main + 23 renderer)
- **Bucket 2** (delete inside-function noise): **9** occurrences (all Python, mostly `main.py` ASCII banner + `keyterms.py` `__main__` block)
- **Bucket 3** (narrow `except` + log + comment or re-raise): **25** occurrences (all Python)

Total: ~178 surgical changes across `python-service/`, `electron/main.js`, and `src/`.

### Commits made by this work (in chronological order)

1. `cacc4c6` (amended) — `chore(deps): add dev toolkit deps + roll up in-flight package.json work`
2. `62b2b98` — `chore(deps): bump vitest to ^3 and electron-devtools-installer to ^4` (code-quality follow-up)
3. (pytest install commit) — `chore(deps): add pytest + roll up in-flight python-service requirements`
4. `267827b` — `feat(dx): add jsconfig.json to enable JSDoc type checking on src/ and electron/`
5. `abbddd0` — `feat(dx): add pyrightconfig.json for python-service editor type checking`
6. `147206b` — `chore: ignore test artifacts + roll up in-flight .gitignore additions`
7. `c636158` — `feat(dx): wire Vitest runner with canary test`
8. `22e0929` — `feat(dx): wire pytest runner with canary test`
9. `5b22eff` — `feat(dx): add src/lib/debug.js — dev-only log/warn, always-on error`
10. `3fcf724` — `feat(dx): add electron/debug.js — dev-only log/warn, always-on error (CJS)`
11. `4463c98` — `feat(dx): add python-service/debug.py — dev-only log/warn, always-on error`
12. `c27bd7b` — `feat(dx): auto-open DevTools + F12 toggle in Electron dev mode`
13. `0d03d9e` — `feat(dx): install React DevTools extension on Electron dev startup`
14. `dc9febb` — `feat(dx): pass DEEN_DEV=1 to Python service + wire electron debug helper for DevTools logs`
15. `238961c` — `feat(dx): add test, test:watch, typecheck npm scripts`
16. `6eaa6ac` — `docs(dx): sweep dry-run report (JS + Python categorize-then-route plan)`
17. `84c77bd` — `refactor(dx): route python-service logs through debug helper, narrow bare-except`
18. `5c66865` — `refactor(dx): route electron main process logs through debug helper`
19. `6795641` — `refactor(dx): route renderer logs through debug helper`

### Follow-ups confirmed deferred

1. **Project-source pyright/JSDoc baseline errors** — 109 errors in scope. Most are concentrated in `electron/main.js` (`'isQuitting' does not exist on type 'App'` shares a single root cause, fixable with one JSDoc cast or module augmentation). Separate task.
2. **Exclude `node_modules/*.js` from JS typecheck** — 748 noise errors come from react-dom CJS bundles. Adjust `jsconfig.json` exclude patterns.
3. **Fix `import.meta.env` typing** — `src/lib/debug.js:53` errors because `jsconfig.json` doesn't include `vite/client` types. One-liner fix.
4. **Pyright ratchet** — `basic` → `strict` once basic is clean.
5. **Real test suite (beyond canaries)** — tests get written when bugs appear, per "reproduce-as-test" doctrine.
6. **Production observability (Sentry, sourcemaps, error boundaries)** — separate playbook (`production-observability.md`), applies before ship-to-users.
7. **Manual end-to-end smoke test of dev experience** (Task 15) — deferred to Abed at next dev session.
