# Dev-Time Toolkit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Commit handling:** The user's CLAUDE.md says don't commit without explicit ask. Each task ends with a "Commit" step — during execution, **ask the user before running each commit**, don't auto-commit. The step is documented so the message and staged files are pre-decided.

**Goal:** Apply the Dev-Time Toolkit playbook to Deen Notes so type errors, broken state, and silent exceptions surface at dev time instead of after the user reports them. Replace `console.log`-sprinkling with a layered toolkit: types → dashboard → debugger → React DevTools → hot reload → tests → strategic dev-only logs.

**Architecture:** Five stack-specific decisions from the approved spec — JSDoc + `checkJs` for JS, Pyright `basic` for Python, Vitest + pytest with canary tests, Electron DevTools + React DevTools auto-opening in dev mode, and a three-bucket categorize-then-route sweep of existing `console.log`/`print`/bare-catch calls. All gated on `!app.isPackaged` (Electron main), `import.meta.env.DEV` (Vite renderer), and `DEEN_DEV=1` env var (Python).

**Tech Stack:** Electron 41 (CJS main process), Vite 8 + React 19 (ESM renderer), Python FastAPI service, SQLite. New: `typescript` (used only as a type-checker for JSDoc, never compiled), `vitest`, `electron-devtools-installer`, `pytest`. Pyright is editor-only (no devDependency entry).

**Spec reference:** `docs/superpowers/specs/2026-05-20-dev-toolkit-design.md`

---

## Phase 1 — Foundation (install deps + type configs)

### Task 1: Install JS dev dependencies

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Edit `package.json` to add new devDependencies**

In the `devDependencies` block, add three entries (alphabetically next to existing ones):

```json
"devDependencies": {
  "@vitejs/plugin-react": "^6.0.1",
  "concurrently": "^9.2.1",
  "electron": "^41.0.3",
  "electron-builder": "^26.0.12",
  "electron-devtools-installer": "^3.2.0",
  "typescript": "^5.7.0",
  "vite": "^8.0.0",
  "vitest": "^2.1.0",
  "wait-on": "^9.0.4"
}
```

- [ ] **Step 2: Install**

Run: `npm install`

Expected: Lockfile updates, `node_modules` populated. No errors.

- [ ] **Step 3: Verify each tool is callable**

Run all three in sequence:
```bash
npx tsc --version
npx vitest --version
node -e "console.log(require('electron-devtools-installer').REACT_DEVELOPER_TOOLS)"
```

Expected:
- `tsc` prints e.g. `Version 5.7.x`
- `vitest` prints e.g. `vitest/2.1.x`
- The Node command prints the React DevTools extension ID (a long hash string)

- [ ] **Step 4: Commit**

```bash
git add package.json package-lock.json
git commit -m "chore(deps): add typescript, vitest, electron-devtools-installer for dev toolkit"
```

---

### Task 2: Install pytest in python-service venv

**Files:**
- Modify: `python-service/requirements.txt`

- [ ] **Step 1: Add pytest to requirements**

Append to `python-service/requirements.txt` (preserve existing entries):

```
pytest>=8.0
```

- [ ] **Step 2: Install into the existing venv**

Run from repo root:
```bash
"python-service/venv/Scripts/python.exe" -m pip install -r python-service/requirements.txt
```

Expected: pytest gets installed; existing deps already satisfied.

- [ ] **Step 3: Verify pytest is callable**

Run:
```bash
"python-service/venv/Scripts/python.exe" -m pytest --version
```

Expected: `pytest 8.x.x`

- [ ] **Step 4: Commit**

```bash
git add python-service/requirements.txt
git commit -m "chore(deps): add pytest to python-service for canary test runner"
```

---

### Task 3: Create jsconfig.json (enables JSDoc type checking)

**Files:**
- Create: `jsconfig.json` (repo root)

- [ ] **Step 1: Create `jsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "checkJs": true,
    "allowJs": true,
    "noEmit": true,
    "strict": true,
    "noImplicitAny": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "jsx": "preserve",
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src/**/*", "electron/**/*", "scripts/**/*"],
  "exclude": ["node_modules", "dist", "release", "python-service"]
}
```

**Why `noImplicitAny: false`:** existing code is untyped, so leaving this strict would surface hundreds of errors on day one. We start permissive and ratchet up later (see follow-up in spec).

- [ ] **Step 2: Run the type checker, capture baseline**

Run:
```bash
npx tsc --noEmit -p jsconfig.json 2>&1 | tee /tmp/typecheck-baseline.txt
echo "---"
grep -c "error TS" /tmp/typecheck-baseline.txt || echo "0 errors"
```

Expected: Some number of errors (probably 5–50). **This is the "before" picture — we are NOT fixing these in this work.** Record the count.

- [ ] **Step 3: Manual verification of in-editor feedback**

Open `src/App.jsx` in VS Code. Add a line near the top:

```js
const _typecheck_canary = "hello" - 1;
```

Expected: red squiggle under `"hello" - 1` within ~2 seconds, hover shows "The left-hand side of an arithmetic operation must be of type 'any', 'number'…" or similar. **Then delete that line.**

If no squiggle appears: confirm VS Code is using the workspace TypeScript via `Cmd/Ctrl+Shift+P → "TypeScript: Select TypeScript Version" → Use Workspace Version`.

- [ ] **Step 4: Commit**

```bash
git add jsconfig.json
git commit -m "feat(dx): add jsconfig.json to enable JSDoc type checking on src/ and electron/"
```

---

### Task 4: Create pyrightconfig.json

**Files:**
- Create: `python-service/pyrightconfig.json`

- [ ] **Step 1: Create the config**

```json
{
  "include": ["."],
  "exclude": ["venv", "**/__pycache__", "tests"],
  "typeCheckingMode": "basic",
  "useLibraryCodeForTypes": true,
  "reportMissingImports": "warning",
  "reportMissingTypeStubs": false,
  "pythonVersion": "3.11"
}
```

- [ ] **Step 2: Manual editor verification**

Open `python-service/main.py` in VS Code (assuming Pylance extension is installed — it ships with the Python extension and is the Pyright frontend). Add:

```python
_typecheck_canary: int = "not a number"
```

Expected: red squiggle under `"not a number"` within ~2 seconds with a message like "Expression of type 'str' cannot be assigned to declared type 'int'." **Then delete the line.**

If Pylance isn't installed: install the VS Code "Python" extension (Microsoft), reload, retry. Pylance is bundled.

- [ ] **Step 3: Commit**

```bash
git add python-service/pyrightconfig.json
git commit -m "feat(dx): add pyrightconfig.json for python-service editor type checking"
```

---

### Task 5: Update .gitignore for test artifacts

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Check current state of .gitignore**

Read the file. If `coverage/` and `.pytest_cache/` are already present, skip to Step 3.

- [ ] **Step 2: Append the new ignore entries**

Add to the bottom of `.gitignore`:

```
# Test artifacts
coverage/
.pytest_cache/
.vitest-cache/
```

- [ ] **Step 3: Commit (only if changed)**

```bash
git add .gitignore
git commit -m "chore: ignore test runner artifacts"
```

If `.gitignore` was unchanged, skip the commit.

---

## Phase 2 — Test runners + canary tests

### Task 6: Wire Vitest + canary test (JS side)

**Files:**
- Create: `vitest.config.js`
- Create: `src/__tests__/canary.test.js`

- [ ] **Step 1: Create `vitest.config.js`**

```js
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
    globals: false,
    include: ['src/**/*.test.{js,jsx}', 'electron/**/*.test.js'],
    exclude: ['node_modules', 'dist', 'release', 'python-service'],
  },
});
```

**Why `environment: 'node'`:** the canary doesn't need a DOM. We'll switch to `jsdom` per-file later if a renderer-component test needs it.

- [ ] **Step 2: Create the canary test**

`src/__tests__/canary.test.js`:

```js
import { describe, it, expect } from 'vitest';

describe('canary', () => {
  it('proves the Vitest runner is wired correctly', () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 3: Run the canary**

Run: `npx vitest run`

Expected: 1 passed, 0 failed. If it fails to find the test, check `include` patterns in `vitest.config.js`.

- [ ] **Step 4: Commit**

```bash
git add vitest.config.js src/__tests__/canary.test.js
git commit -m "feat(dx): wire Vitest runner with canary test"
```

---

### Task 7: Wire pytest + canary test (Python side)

**Files:**
- Create: `python-service/pytest.ini`
- Create: `python-service/tests/__init__.py`
- Create: `python-service/tests/test_canary.py`

- [ ] **Step 1: Create `python-service/pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -ra --strict-markers
pythonpath = .
```

`pythonpath = .` lets test files import from the service root (e.g., `from debug import create_debug`) without needing a setup.py.

- [ ] **Step 2: Create the tests directory marker**

`python-service/tests/__init__.py`:

```python
# Marks tests/ as a package so pytest can discover it cleanly.
```

- [ ] **Step 3: Create the canary test**

`python-service/tests/test_canary.py`:

```python
def test_canary_proves_pytest_runner_wired():
    assert 1 + 1 == 2
```

- [ ] **Step 4: Run the canary**

Run from repo root:
```bash
cd python-service && "venv/Scripts/python.exe" -m pytest -v
```

Expected: `1 passed`. If it can't find tests, check `testpaths` in pytest.ini.

- [ ] **Step 5: Commit**

```bash
git add python-service/pytest.ini python-service/tests/__init__.py python-service/tests/test_canary.py
git commit -m "feat(dx): wire pytest runner with canary test"
```

---

## Phase 3 — `debug()` helpers (TDD)

The three helpers share the same API contract: `log(subsystem, message, ...data)`, `warn(...)`, `error(...)`. `error` always prints; `log` and `warn` are dev-gated. Each is built TDD-style.

### Task 8: Build `src/lib/debug.js` (renderer helper) with TDD

**Files:**
- Create: `src/lib/__tests__/debug.test.js`
- Create: `src/lib/debug.js`

- [ ] **Step 1: Write the failing tests**

`src/lib/__tests__/debug.test.js`:

```js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createDebug } from '../debug.js';

describe('createDebug (renderer)', () => {
  let logSpy, warnSpy, errorSpy;

  beforeEach(() => {
    logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('log() is a no-op when isDev=false', () => {
    const d = createDebug(false);
    d.log('Sub', 'message', { extra: 1 });
    expect(logSpy).not.toHaveBeenCalled();
  });

  it('log() prints prefixed message when isDev=true', () => {
    const d = createDebug(true);
    d.log('Sub', 'message', { extra: 1 });
    expect(logSpy).toHaveBeenCalledWith('[Sub] message', { extra: 1 });
  });

  it('warn() is a no-op when isDev=false', () => {
    const d = createDebug(false);
    d.warn('Sub', 'careful');
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it('warn() prints prefixed message when isDev=true', () => {
    const d = createDebug(true);
    d.warn('Sub', 'careful', 42);
    expect(warnSpy).toHaveBeenCalledWith('[Sub] careful', 42);
  });

  it('error() ALWAYS prints, even when isDev=false', () => {
    const d = createDebug(false);
    d.error('Sub', 'boom', { code: 500 });
    expect(errorSpy).toHaveBeenCalledWith('[Sub] boom', { code: 500 });
  });

  it('error() prints when isDev=true', () => {
    const d = createDebug(true);
    d.error('Sub', 'boom');
    expect(errorSpy).toHaveBeenCalledWith('[Sub] boom');
  });
});
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `npx vitest run src/lib/__tests__/debug.test.js`

Expected: FAIL with `Failed to resolve import "../debug.js"` — the module doesn't exist yet.

- [ ] **Step 3: Write the minimal implementation**

`src/lib/debug.js`:

```js
/**
 * Dev-time debug helper. `log` and `warn` are no-ops in production builds.
 * `error` always surfaces — errors are signals we want visible, not silently dropped.
 *
 * Boundary-log doctrine: prefer one log at a process/network doorway over many
 * logs inside function bodies. Use the debugger or React DevTools for state.
 */

/**
 * @param {boolean} isDev
 */
export function createDebug(isDev) {
  /**
   * @param {string} subsystem
   * @param {string} message
   */
  const format = (subsystem, message) => `[${subsystem}] ${message}`;

  return {
    /**
     * @param {string} subsystem
     * @param {string} message
     * @param {...unknown} data
     */
    log(subsystem, message, ...data) {
      if (!isDev) return;
      // eslint-disable-next-line no-console
      console.log(format(subsystem, message), ...data);
    },
    /**
     * @param {string} subsystem
     * @param {string} message
     * @param {...unknown} data
     */
    warn(subsystem, message, ...data) {
      if (!isDev) return;
      // eslint-disable-next-line no-console
      console.warn(format(subsystem, message), ...data);
    },
    /**
     * @param {string} subsystem
     * @param {string} message
     * @param {...unknown} data
     */
    error(subsystem, message, ...data) {
      // ALWAYS prints — errors stay loud, even in prod.
      // eslint-disable-next-line no-console
      console.error(format(subsystem, message), ...data);
    },
  };
}

export const debug = createDebug(import.meta.env.DEV);
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `npx vitest run src/lib/__tests__/debug.test.js`

Expected: 6 passed, 0 failed.

- [ ] **Step 5: Commit**

```bash
git add src/lib/debug.js src/lib/__tests__/debug.test.js
git commit -m "feat(dx): add src/lib/debug.js — dev-only log/warn, always-on error"
```

---

### Task 9: Build `electron/debug.js` (Electron main helper) with TDD

**Files:**
- Create: `electron/__tests__/debug.test.js`
- Create: `electron/debug.js`

- [ ] **Step 1: Write the failing tests**

`electron/__tests__/debug.test.js`:

```js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createDebug } from '../debug.js';

describe('createDebug (electron main)', () => {
  let logSpy, warnSpy, errorSpy;

  beforeEach(() => {
    logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('log() is a no-op when isDev=false', () => {
    const d = createDebug(false);
    d.log('Python', 'starting');
    expect(logSpy).not.toHaveBeenCalled();
  });

  it('log() prints prefixed when isDev=true', () => {
    const d = createDebug(true);
    d.log('Python', 'starting', { port: 8765 });
    expect(logSpy).toHaveBeenCalledWith('[Python] starting', { port: 8765 });
  });

  it('warn() prints prefixed when isDev=true', () => {
    const d = createDebug(true);
    d.warn('Target', 'retry');
    expect(warnSpy).toHaveBeenCalledWith('[Target] retry');
  });

  it('warn() is a no-op when isDev=false', () => {
    const d = createDebug(false);
    d.warn('Target', 'retry');
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it('error() always prints, even when isDev=false', () => {
    const d = createDebug(false);
    d.error('Picker', 'list-notes failed', { err: 'ECONNREFUSED' });
    expect(errorSpy).toHaveBeenCalledWith('[Picker] list-notes failed', { err: 'ECONNREFUSED' });
  });
});
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `npx vitest run electron/__tests__/debug.test.js`

Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation (CommonJS to match existing electron/ files)**

`electron/debug.js`:

```js
// Dev-time debug helper for the Electron main process.
// `log` / `warn` are dev-gated. `error` always prints (errors stay loud).
// CommonJS module — matches the rest of electron/.

function createDebug(isDev) {
  const format = (subsystem, message) => `[${subsystem}] ${message}`;

  return {
    log(subsystem, message, ...data) {
      if (!isDev) return;
      console.log(format(subsystem, message), ...data);
    },
    warn(subsystem, message, ...data) {
      if (!isDev) return;
      console.warn(format(subsystem, message), ...data);
    },
    error(subsystem, message, ...data) {
      console.error(format(subsystem, message), ...data);
    },
  };
}

module.exports = { createDebug };
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `npx vitest run electron/__tests__/debug.test.js`

Expected: 5 passed.

If you see an "Cannot use import statement outside a module" or interop error: Vitest's CJS interop usually handles `module.exports` cleanly for ESM imports. If it fails, replace the test's `import { createDebug } from '../debug.js'` with `const { createDebug } = await import('../debug.js')` inside a `beforeEach`.

- [ ] **Step 5: Commit**

```bash
git add electron/debug.js electron/__tests__/debug.test.js
git commit -m "feat(dx): add electron/debug.js — dev-only log/warn, always-on error (CJS)"
```

---

### Task 10: Build `python-service/debug.py` with TDD

**Files:**
- Create: `python-service/tests/test_debug.py`
- Create: `python-service/debug.py`

- [ ] **Step 1: Write the failing tests**

`python-service/tests/test_debug.py`:

```python
import sys

import pytest

from debug import create_debug


def test_log_is_noop_when_not_dev(capsys):
    d = create_debug(is_dev=False)
    d.log("Sub", "message", {"extra": 1})
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_log_prints_prefixed_when_dev(capsys):
    d = create_debug(is_dev=True)
    d.log("Sub", "message")
    captured = capsys.readouterr()
    assert "[Sub] message" in captured.out


def test_warn_is_noop_when_not_dev(capsys):
    d = create_debug(is_dev=False)
    d.warn("Sub", "careful")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_warn_prints_to_stderr_when_dev(capsys):
    d = create_debug(is_dev=True)
    d.warn("Sub", "careful")
    captured = capsys.readouterr()
    assert "[WARN][Sub] careful" in captured.err


def test_error_always_prints_to_stderr(capsys):
    d = create_debug(is_dev=False)
    d.error("Sub", "boom")
    captured = capsys.readouterr()
    assert "[ERROR][Sub] boom" in captured.err


def test_error_prints_extra_data(capsys):
    d = create_debug(is_dev=True)
    d.error("Sub", "boom", {"code": 500})
    captured = capsys.readouterr()
    assert "[ERROR][Sub] boom" in captured.err
    assert "500" in captured.err
```

- [ ] **Step 2: Run the test, verify it fails**

Run from repo root:
```bash
cd python-service && "venv/Scripts/python.exe" -m pytest tests/test_debug.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'debug'`.

- [ ] **Step 3: Write the implementation**

`python-service/debug.py`:

```python
"""
Dev-time debug helper. `log` / `warn` are no-ops unless is_dev is True.
`error` always prints — errors stay loud in dev and prod.

Routing convention (matches electron/main.js stdout/stderr pipes):
- log()   -> stdout, shows up in Electron as "[Python] [Subsystem] message"
- warn()  -> stderr, shows up as "[Python ERROR] [WARN][Subsystem] message"
- error() -> stderr, shows up as "[Python ERROR] [ERROR][Subsystem] message"
"""

from __future__ import annotations

import os
import sys
from typing import Any


class Debug:
    def __init__(self, is_dev: bool) -> None:
        self._is_dev = is_dev

    def log(self, subsystem: str, message: str, *data: Any) -> None:
        if not self._is_dev:
            return
        print(f"[{subsystem}] {message}", *data)

    def warn(self, subsystem: str, message: str, *data: Any) -> None:
        if not self._is_dev:
            return
        print(f"[WARN][{subsystem}] {message}", *data, file=sys.stderr)

    def error(self, subsystem: str, message: str, *data: Any) -> None:
        # ALWAYS prints, even when is_dev=False.
        print(f"[ERROR][{subsystem}] {message}", *data, file=sys.stderr)


def create_debug(is_dev: bool) -> Debug:
    return Debug(is_dev)


# Default singleton wired against env var. Electron sets DEEN_DEV=1 in dev mode
# (see electron/main.js task in Phase 4). In packaged builds the var is absent.
debug = create_debug(os.environ.get("DEEN_DEV", "0") == "1")
```

- [ ] **Step 4: Run the test, verify it passes**

Run:
```bash
cd python-service && "venv/Scripts/python.exe" -m pytest tests/test_debug.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add python-service/debug.py python-service/tests/test_debug.py
git commit -m "feat(dx): add python-service/debug.py — dev-only log/warn, always-on error"
```

---

## Phase 4 — Wire DevTools auto-open + React DevTools

### Task 11: Auto-open Electron DevTools in dev + F12 shortcut

**Files:**
- Modify: `electron/main.js` (around the existing `createWindow` function at lines 72–112)

- [ ] **Step 1: Read the current state of `createWindow` and locate the insertion point**

Confirm `electron/main.js` line 41 still defines `const isDev = !app.isPackaged;` (it does as of this writing). The DevTools open call belongs inside `createWindow` after `mainWindow.loadURL(...)` / `mainWindow.loadFile(...)`.

- [ ] **Step 2: Add the auto-open block inside `createWindow`**

In `electron/main.js`, find this section:

```js
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }
```

Right after that block (before the `setPermissionRequestHandler` call), add:

```js
  if (isDev) {
    // Open DevTools alongside the renderer so debugger + Components tab is
    // the FIRST reflex when something looks wrong, not the last.
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }
```

- [ ] **Step 3: Wire F12 toggle so it works on every BrowserWindow in dev**

In `electron/main.js`, find the `app.whenReady().then(() => { ... })` block (around line 752). Inside that block, AFTER `createWindow();` but BEFORE `startPythonService();`, insert:

```js
  if (isDev) {
    // F12 toggles DevTools on the currently-focused window. Cheap, predictable.
    globalShortcut.register('F12', () => {
      const w = BrowserWindow.getFocusedWindow();
      if (w) w.webContents.toggleDevTools();
    });
  }
```

- [ ] **Step 4: Manual smoke test**

Run: `npm run electron:dev`

Expected:
- Main window opens, DevTools panel opens detached.
- Close DevTools with the X.
- Press F12 — DevTools re-opens.
- Press F12 again — DevTools closes.

Then `Ctrl+C` the dev server.

- [ ] **Step 5: Commit**

```bash
git add electron/main.js
git commit -m "feat(dx): auto-open DevTools + F12 toggle in dev mode"
```

---

### Task 12: Install React DevTools extension on dev startup

**Files:**
- Modify: `electron/main.js`

- [ ] **Step 1: Add the require at the top of `electron/main.js`**

Currently the imports at lines 1–6 look like:

```js
const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, globalShortcut, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');
const { generateDIcon } = require('./icon');
```

This task does NOT add a top-level `require('electron-devtools-installer')` because that package needs to be lazily required inside `app.whenReady()` — it crashes if loaded before Electron is ready.

- [ ] **Step 2: Add the installer call inside `app.whenReady()`**

In `electron/main.js`, find the `app.whenReady().then(() => { ... })` block. At the TOP of that callback (before `appState = readAppState();`), add:

```js
  if (isDev) {
    // Lazy require — the package touches Electron internals that aren't
    // available before whenReady fires. Installs once into the userData
    // directory; subsequent dev launches are no-ops.
    try {
      const installer = require('electron-devtools-installer');
      const { default: install, REACT_DEVELOPER_TOOLS } = installer;
      install(REACT_DEVELOPER_TOOLS)
        .then((name) => console.log(`[DevTools] Installed: ${name}`))
        .catch((err) => console.warn('[DevTools] Install failed:', err.message));
    } catch (err) {
      console.warn('[DevTools] electron-devtools-installer not available:', err.message);
    }
  }
```

Note the deliberate `console.log`/`console.warn` here — this code runs *before* `electron/debug.js` is wired up in Task 13. It's safe because the block is dev-only. We'll route it through the helper in Task 13.

- [ ] **Step 3: Manual smoke test**

Run: `npm run electron:dev`

Expected on first run:
- Terminal shows `[DevTools] Installed: React Developer Tools`
- DevTools opens, click the `>>` to find the "Components" and "Profiler" tabs from React DevTools
- Click "Components" → see the React tree, with `<App>` at the root

Then close the dev server.

Run `npm run electron:dev` again. On second run:
- Terminal shows `[DevTools] Installed: React Developer Tools` (the installer is idempotent; logs the name even when already-installed)
- Components tab still works

- [ ] **Step 4: Commit**

```bash
git add electron/main.js
git commit -m "feat(dx): install React DevTools extension in Electron dev mode"
```

---

### Task 13: Pass `DEEN_DEV=1` to Python process + route Electron main logs through `debug` helper

**Files:**
- Modify: `electron/main.js`

- [ ] **Step 1: Pass DEEN_DEV=1 when spawning Python in dev mode**

In `electron/main.js`, find `startPythonService()` (around line 516). The current `env` block in the `spawn(...)` call:

```js
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      DEEN_NOTES_DATA_DIR: app.getPath('userData'),
    },
```

Replace with:

```js
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      DEEN_NOTES_DATA_DIR: app.getPath('userData'),
      ...(isDev ? { DEEN_DEV: '1' } : {}),
    },
```

This causes `python-service/debug.py`'s module-level `debug = create_debug(...)` to wire as dev-enabled when Electron launched Python.

- [ ] **Step 2: Require the debug helper and instantiate it**

Add to the imports block at the top of `electron/main.js`:

```js
const { createDebug } = require('./debug');
```

Then find the existing line (currently line 41):

```js
const isDev = !app.isPackaged;
```

Immediately AFTER that line, add:

```js
const debug = createDebug(isDev);
```

Reusing the existing `isDev` constant keeps the dev-gate definition in one place — a single line to flip if it ever changes.

- [ ] **Step 3: Replace the Task 12 logs with `debug.*` calls**

In the Task 12 block we added inside `app.whenReady()`, replace:

```js
install(REACT_DEVELOPER_TOOLS)
  .then((name) => console.log(`[DevTools] Installed: ${name}`))
  .catch((err) => console.warn('[DevTools] Install failed:', err.message));
```

with:

```js
install(REACT_DEVELOPER_TOOLS)
  .then((name) => debug.log('DevTools', 'installed', name))
  .catch((err) => debug.warn('DevTools', 'install failed', err.message));
```

And replace:

```js
console.warn('[DevTools] electron-devtools-installer not available:', err.message);
```

with:

```js
debug.warn('DevTools', 'installer not available', err.message);
```

**Do NOT do the full sweep of electron/main.js here — that's Phase 8.** This task only routes the DevTools-block logs we just added, so we don't leave fresh `console.log`s behind.

- [ ] **Step 4: Manual smoke test**

Run: `npm run electron:dev`

Expected:
- Terminal shows `[DevTools] installed React Developer Tools` (no `[DevTools]:` prefix — the helper formats it as `[Subsystem] message`)
- Python service starts; its `print()` calls still show via `[Python]` prefix (these get swept in Phase 8)

- [ ] **Step 5: Commit**

```bash
git add electron/main.js
git commit -m "feat(dx): pass DEEN_DEV=1 to Python service + wire electron debug helper for DevTools logs"
```

---

## Phase 5 — Package.json scripts

### Task 14: Add npm scripts for test + typecheck

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Edit `package.json` scripts block**

Current scripts:

```json
"scripts": {
  "dev": "vite",
  "build": "vite build",
  "electron:dev": "concurrently \"vite\" \"wait-on http://localhost:5173 && electron .\"",
  "start": "electron .",
  "dist": "node scripts/copy-env.js && vite build && electron-builder --win nsis --x64",
  "electron:build": "npm run dist"
},
```

Replace with:

```json
"scripts": {
  "dev": "vite",
  "build": "vite build",
  "electron:dev": "concurrently \"vite\" \"wait-on http://localhost:5173 && electron .\"",
  "start": "electron .",
  "dist": "node scripts/copy-env.js && vite build && electron-builder --win nsis --x64",
  "electron:build": "npm run dist",
  "test": "vitest run",
  "test:watch": "vitest",
  "typecheck": "tsc --noEmit -p jsconfig.json"
},
```

- [ ] **Step 2: Verify each script**

Run all three:
```bash
npm test
npm run typecheck
```

Expected:
- `npm test` — Vitest runs all tests across `src/`, `electron/`. Shows passing canary + debug tests.
- `npm run typecheck` — same baseline error count we captured in Task 3. **Errors are expected and not blocking** (they're the existing untyped code, not regressions from this PR).

(We skip running `test:watch` here because it doesn't terminate.)

- [ ] **Step 3: Commit**

```bash
git add package.json
git commit -m "feat(dx): add test, test:watch, typecheck scripts"
```

---

## Phase 6 — Manual verification of the dev experience

### Task 15: End-to-end smoke test of the dev loop

**Files:** None (verification only).

- [ ] **Step 1: Clean dev launch**

Run: `npm run electron:dev`

Verify, in order:
1. Vite dev server starts on `http://localhost:5173`
2. Electron window opens
3. DevTools opens detached
4. React DevTools "Components" tab is present and shows `<App>` tree
5. Terminal shows `[DevTools] installed React Developer Tools`
6. Terminal shows `[Python] Starting:` and Python service is reachable on 8765

- [ ] **Step 2: Hot reload check**

In a separate editor, open `src/App.jsx`. Find a string literal in JSX (any visible text — for example `<h1>` or a button label). Change it to something obvious. Save.

Expected: renderer updates in <2 seconds without a manual reload. **Then revert the change.**

If hot reload doesn't fire: check the Vite terminal for HMR errors.

- [ ] **Step 3: Breakpoint check (the *real* habit shift)**

In DevTools → Sources tab, find `src/hooks/useNotes.js` (under the webpack-internal:// or http://localhost:5173/ tree). Set a breakpoint inside `useNotes` near the top of the function body.

Trigger any note interaction in the app (click a note, etc.).

Expected: execution pauses at the breakpoint. You can inspect the React state, call stack, scopes. **Remove the breakpoint.**

- [ ] **Step 4: React DevTools state inspection check**

In DevTools → Components tab, click `<NoteList>` (or any visible component). The right pane should show its `props` and `state`/`hooks` — concrete values, not just types.

- [ ] **Step 5: Capture results**

Note down whether all four steps passed. If any failed, **stop and debug before continuing to Phase 7** — the toolkit needs to be working before we run the sweep.

There's nothing to commit in this task — it's pure verification.

---

## Phase 7 — Sweep dry run (PAUSE GATE)

### Task 16: Generate the JS-side sweep dry-run report

**Files:**
- Create: `docs/superpowers/specs/2026-05-20-sweep-dry-run.md`

- [ ] **Step 1: Run the scans**

Run all four scans, capturing the file:line:content of each match:

```bash
# 1. JS console.* across renderer + electron
rg "console\.(log|warn|info|debug|error)" src/ electron/ -n --no-heading > /tmp/sweep-js-console.txt

# 2. JS bare-catch + console (multiline)
rg -U "catch\s*\([^)]*\)\s*\{[^}]*console\." src/ electron/ -n --no-heading > /tmp/sweep-js-catch.txt
```

- [ ] **Step 2: Categorize each match into a bucket**

For each line in the scan output, decide:
- **Bucket 1** — Boundary log at a doorway (IPC handler, HTTP boundary, process spawn): KEEP, route through `debug.*` helper
- **Bucket 2** — Inside-function noise (debug leftover, no longer needed): DELETE
- **Bucket 3** — Inside a catch block: cross-check with Bucket 1/2 rules. Most are Bucket 1 (catch-and-log-at-boundary) — keep, but route through `debug.error`.

- [ ] **Step 3: Write the dry-run report**

Create `docs/superpowers/specs/2026-05-20-sweep-dry-run.md` with this structure:

```markdown
# Dev Toolkit Sweep — Dry Run Report

Date: 2026-05-20
Scope: JS (src/, electron/) and Python (python-service/) — categorize-then-route per Section 2 of the design spec.

## JS occurrences

### electron/main.js
| Line | Current code (truncated) | Bucket | Proposed treatment |
|---|---|---|---|
| 61 | `console.error('[State] Failed to persist:', err.message)` | 1 | `debug.error('State', 'failed to persist', err.message)` |
| 306 | `console.log('[Target] Restored to Python:', target)` | 1 | `debug.log('Target', 'restored to Python', target)` |
| ... | ... | ... | ... |

### src/App.jsx
...

### src/hooks/useNotes.js
...

(Continue for every file with hits)
```

Fill in every row. Do not skip files. The full set is the 12 JS files identified in the initial scan.

- [ ] **Step 4: Commit the dry-run report**

```bash
git add docs/superpowers/specs/2026-05-20-sweep-dry-run.md
git commit -m "docs(dx): JS sweep dry-run report (categorize-then-route plan)"
```

---

### Task 17: Append the Python-side sweep dry run

**Files:**
- Modify: `docs/superpowers/specs/2026-05-20-sweep-dry-run.md` (append)

- [ ] **Step 1: Run the Python scans**

```bash
# 1. Python prints
rg "^\s*print\(" python-service/ -g '!venv/**' -g '!tests/**' -n --no-heading > /tmp/sweep-py-print.txt

# 2. Bare except patterns
rg -U "except\s*[A-Za-z_,\s]*:\s*(pass|print|continue|return)" python-service/ -g '!venv/**' -g '!tests/**' -n --no-heading > /tmp/sweep-py-except.txt
```

- [ ] **Step 2: Categorize each Python match into a bucket**

For each line:
- **Bucket 1** — Doorway print (request entry/exit, service startup, IPC reply): route through `debug.log` / `debug.error`
- **Bucket 2** — Inside-function noise: DELETE
- **Bucket 3** — Bare-except patterns: narrow to specific exception class + route via `debug.error` + decide if a why-comment is needed for an intentional swallow

- [ ] **Step 3: Append the Python sections to the dry-run report**

Append to `docs/superpowers/specs/2026-05-20-sweep-dry-run.md`:

```markdown

## Python occurrences

### python-service/main.py
| Line | Current code (truncated) | Bucket | Proposed treatment |
|---|---|---|---|
| ... | ... | ... | ... |

### python-service/ai_client.py
...

(Continue for all 9 Python files)

## Files NOT touched by this sweep

- `scripts/copy-env.js` (build script — intentional CI output)
- `python-service/venv/**`, `node_modules/**` (vendored)
- `python-service/wake_word.py` Picovoice-SDK-internal prints (leave them)
- `python-service/tests/**` (test code, not service code)

## Summary

- Bucket 1 (route through helper): NN occurrences across MM files
- Bucket 2 (delete): NN occurrences across MM files
- Bucket 3 (narrow + route + comment): NN occurrences across MM files
```

Fill in actual counts.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-05-20-sweep-dry-run.md
git commit -m "docs(dx): Python sweep dry-run report + summary counts"
```

---

### Task 18: PAUSE — user reviews the dry-run report

**Files:** None.

- [ ] **Step 1: Surface the report to the user**

Tell the user:

> "Dry-run report ready at `docs/superpowers/specs/2026-05-20-sweep-dry-run.md`. It lists every existing `console.log`, `print()`, and bare-catch block, with the bucket I'm planning to put it in and the proposed treatment. Before I run the sweep, please review it — flag any rows where the bucket guess looks wrong, or anything you want me to leave alone. Once you approve, I'll execute Phase 8."

- [ ] **Step 2: Wait for approval**

Do not start Phase 8 until the user explicitly approves the dry-run report. If they want changes, edit the report and re-commit before continuing.

---

## Phase 8 — Apply the sweep (after user approval of dry run)

### Task 19: Apply Python sweep

**Files:**
- Modify: `python-service/*.py` (multiple — driven by the dry-run report)

- [ ] **Step 1: Process files one at a time, smallest first**

For each Python file in the dry-run report (sort by occurrence count, ascending):

1. Open the file
2. Add `from debug import debug` at the top with the other imports (skip if already importing from a relative path that conflicts — use `from .debug import debug` if needed based on the module structure)
3. For each Bucket 1 occurrence: replace `print(f"[Subsystem] message", x)` with `debug.log("Subsystem", "message", x)` (or `debug.warn` / `debug.error` based on context)
4. For each Bucket 2 occurrence: delete the line
5. For each Bucket 3 occurrence: narrow the `except:` to a specific exception class, add `debug.error(...)`, and either re-raise or add a why-comment if the swallow is deliberate
6. Run the per-file tests if they exist; if not, at minimum import the file to confirm no syntax errors:
   ```bash
   "python-service/venv/Scripts/python.exe" -c "import <module_name>"
   ```

- [ ] **Step 2: Run the full pytest suite after each file**

```bash
cd python-service && "venv/Scripts/python.exe" -m pytest -v
```

Expected: All tests still pass (only the canary and debug tests exist; both should remain green).

- [ ] **Step 3: Run a service-startup smoke test**

```bash
"python-service/venv/Scripts/python.exe" -c "import main; print('imports ok')"
```

Expected: `imports ok`. (We're not booting the full FastAPI server here, just confirming the module graph imports cleanly.)

- [ ] **Step 4: Commit (one commit per file is reasonable; or one commit for the whole sweep — your call)**

```bash
git add python-service/
git commit -m "refactor(dx): route python-service logs through debug helper, narrow bare-except blocks"
```

---

### Task 20: Apply Electron main sweep

**Files:**
- Modify: `electron/main.js` (and any other electron/*.js files with hits — `electron/icon.js`, etc., per the dry-run report)

- [ ] **Step 1: For `electron/main.js`**

The `createDebug` import + `const debug` instance were added in Task 13 — already present. Confirm by reading the top of the file.

For each Bucket 1 occurrence in the dry-run report (lines 61, 306, 312, 320, 329, 469, 474, 483, 502, 521, 538, 544, 549, 554, 557, 609, 623, 643, 655, 671, 686, 728 per initial scan):
- Replace `console.log('[Subsystem] message', x)` → `debug.log('Subsystem', 'message', x)`
- Replace `console.warn(...)` → `debug.warn(...)`
- Replace `console.error(...)` → `debug.error(...)`

For each Bucket 2 occurrence: delete.

- [ ] **Step 2: For any other electron/*.js files with hits**

Apply the same pattern. They'll need `const { createDebug } = require('./debug');` added at the top, then either `const debug = createDebug(!app.isPackaged);` if `app` is available, OR receive `debug` as a parameter from `main.js`.

(For `electron/icon.js`, if it has any console calls, the simplest path is to require `./debug` and instantiate locally with a hardcoded `false` — icon generation only happens at startup and isn't worth surfacing in dev logs.)

- [ ] **Step 3: Smoke test**

Run: `npm run electron:dev`

Expected:
- All previous `[Subsystem]` boundary logs still appear in the terminal (now coming from `debug.log` instead of raw `console.log`)
- DevTools auto-opens
- Python service starts
- Bubble + main window render correctly
- No new errors in the renderer DevTools console

`Ctrl+C` to stop.

- [ ] **Step 4: Run Vitest**

Run: `npm test`

Expected: All tests still pass.

- [ ] **Step 5: Commit**

```bash
git add electron/
git commit -m "refactor(dx): route electron main logs through debug helper"
```

---

### Task 21: Apply renderer sweep

**Files:**
- Modify: `src/**/*.{js,jsx}` (driven by the dry-run report — `src/App.jsx`, `src/hooks/useGroups.js`, `src/hooks/useMicRecorder.js`, `src/hooks/useNoteOverlay.js`, `src/hooks/useNotes.js`, `src/hooks/useWebSocket.js`, `src/components/MermaidBlock.jsx`, `src/components/NoteList.jsx`, `src/components/NoteView.jsx`, `src/components/Settings.jsx`)

- [ ] **Step 1: For each renderer file with hits**

At the top of the file, add:

```js
import { debug } from '@/lib/debug';
```

(Or use a relative path like `../lib/debug` based on the file's location.)

Replace each occurrence per its bucket assignment from the dry-run report.

- [ ] **Step 2: Run Vitest after each file**

```bash
npm test
```

Expected: All tests pass.

- [ ] **Step 3: Manual smoke test**

Run: `npm run electron:dev`

Click around the app. Trigger a note creation, switch between notes, toggle settings. Watch the DevTools console — it should be quiet except for any intentional dev logs.

- [ ] **Step 4: Commit**

```bash
git add src/
git commit -m "refactor(dx): route renderer logs through debug helper"
```

---

## Phase 9 — Final verification + spec appendix

### Task 22: Run all verification commands, capture outputs

**Files:** None during execution; outputs captured in the next task.

- [ ] **Step 1: Run each verification command and capture stdout/stderr**

Run each, save the output:

```bash
# 1. JS typecheck (baseline error count — should match what we captured in Task 3)
npm run typecheck 2>&1 | tee /tmp/verify-typecheck.txt

# 2. Python typecheck — pyright is editor-only, but we can run it from CLI if installed.
#    Skip with "manual" if pyright CLI isn't installed; the editor verification is the binding check.

# 3. JS test suite
npm test 2>&1 | tee /tmp/verify-vitest.txt

# 4. Python test suite
cd python-service && "venv/Scripts/python.exe" -m pytest -v 2>&1 | tee /tmp/verify-pytest.txt && cd ..

# 5. Sweep verifications — these should now return ZERO results
rg "console\.(log|warn|info|debug)" src/ electron/ -g '!**/__tests__/**' -g '!**/debug.js' 2>&1 | tee /tmp/verify-console-sweep.txt
echo "---"
rg "^\s*print\(" python-service/ -g '!venv/**' -g '!tests/**' -g '!debug.py' 2>&1 | tee /tmp/verify-print-sweep.txt
echo "---"
rg "except\s*:" python-service/ -g '!venv/**' -g '!tests/**' 2>&1 | tee /tmp/verify-except-sweep.txt
```

- [ ] **Step 2: Confirm expectations**

| Check | Expected outcome |
|---|---|
| `npm run typecheck` | Exits with the same baseline error count from Task 3 (no regression) |
| `npm test` | All passes — canary + 3 debug helper test files |
| `pytest` | All passes — canary + Python debug helper test file |
| `rg console.*` in src/ + electron/ | Zero hits (excluding tests and `debug.js`) |
| `rg ^print(` in python-service/ | Zero hits (excluding tests and `debug.py`) |
| `rg except:` in python-service/ | Zero hits |

If any check fails: go back, find the offender, fix, re-run.

---

### Task 23: Append verification appendix to the spec

**Files:**
- Modify: `docs/superpowers/specs/2026-05-20-dev-toolkit-design.md` (append)

- [ ] **Step 1: Append the appendix**

At the bottom of the spec file, append:

```markdown

---

## Verified on 2026-05-20 (or actual completion date)

### Type checking
- `npm run typecheck`: <N> pre-existing JSDoc errors (baseline carried forward, not regressions). Inline VS Code feedback confirmed working.
- Pyright editor feedback confirmed working in `python-service/main.py`.

### Test suites
- `npm test`: <N> passed, 0 failed.
- `pytest`: <N> passed, 0 failed.

### DevTools
- DevTools auto-opens on `npm run electron:dev`: ✓
- F12 toggle works: ✓
- React DevTools "Components" tab functional: ✓

### Hot reload
- `src/` edit-save → renderer updates in <2s: ✓

### Sweep completeness
- `rg "console\.(log|warn|info|debug)" src/ electron/ -g '!**/__tests__/**' -g '!**/debug.js'`: 0 hits
- `rg "^\s*print\(" python-service/ -g '!venv/**' -g '!tests/**' -g '!debug.py'`: 0 hits
- `rg "except\s*:" python-service/`: 0 hits

### Follow-ups confirmed deferred
- Pre-existing JSDoc type errors: <N> remaining (separate task)
- Pyright ratchet from `basic` to `strict`: deferred
- Real test suite (beyond canaries): deferred
- Production observability (Sentry): separate playbook, applies before user-facing deploy
```

Fill in actual numbers from Task 22 outputs.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-05-20-dev-toolkit-design.md
git commit -m "docs(dx): verification appendix for dev toolkit rollout"
```

---

### Task 24: Final summary commit (if anything still uncommitted)

**Files:** Any stragglers.

- [ ] **Step 1: Status check**

Run: `git status`

Expected: clean working tree.

If anything is uncommitted, group it logically and commit with a clear message.

- [ ] **Step 2: Hand back to the user**

Tell them:

> "Dev Toolkit applied. The five rungs that needed work are live: JSDoc + checkJs for JS, Pyright basic for Python, Vitest + pytest canaries, DevTools + React DevTools auto-opening, and the three-bucket sweep is complete. Verification appendix is in the spec at `docs/superpowers/specs/2026-05-20-dev-toolkit-design.md`.
>
> The real test is the next bug you hit — your first reflex should be the debugger or React DevTools, not `console.log`."

---

## Out-of-scope reminders (will NOT be done in this plan)

These are intentionally deferred:

- **Pre-existing type errors revealed by `jsconfig.json`** — captured as a baseline count, not fixed.
- **Pyright `basic` → `strict` ratchet** — once basic is clean, separate task.
- **Real test coverage** — only canaries exist; actual tests get written when bugs appear (per "reproduce-as-test" doctrine).
- **Production observability (Sentry, sourcemaps, error boundaries)** — that's the `production-observability` playbook, applies before user-facing deploy.
- **CI / pre-commit hooks** — dev-time only per rule 7.
- **Component refactoring beyond the log/catch sweep** — deliberate restraint.
