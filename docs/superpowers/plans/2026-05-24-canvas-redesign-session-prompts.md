---
title: Deen Notes Canvas Redesign — Session Prompts
date: 2026-05-24
status: ready-to-launch
spec: docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
workflow: main-only (no PRs, no feature branches, no worktrees)
---

# Canvas Redesign — Session Prompts

Seven self-contained prompts. Each starts a fresh Claude Code session that handles one sub-project end-to-end (plan → implement → commit + push to main). Copy the prompt, paste it as the first message in a new session.

## Workflow

This project uses a **main-only** git workflow. Every session works directly on `main`:

```bash
git pull            # always start fresh
# ... do the work, commits stay small and focused ...
npm test            # confirm green before pushing
npm run typecheck   # confirm no new errors before pushing
git push origin main
```

No feature branches. No PRs. No worktrees. The discipline that PRs provide (review, isolation) is replaced by:

- **Local verification** before each push (tests pass, typecheck adds no new errors, app actually runs).
- **Small, descriptive commits** so `git log` is the review surface.
- **Sequential sessions** — one sub-project at a time. Parallelism creates push races and conflicts in a main-only world.

If a session breaks main, revert the offending commit on main and try again. `git revert <sha>` is the recovery tool.

## How to use

1. **Session 0 is complete** (foundation merged at tag [`canvas-foundation-v1`](https://github.com/abedshelp-boop/Klippa_Notes/releases/tag/canvas-foundation-v1)). The engine pick (React Flow), shared types, and decision docs are on main. Move to Session 1.
2. Run Sessions 1 → 2 → 3 → 4 → 5 → 6 → 7 in order. Each ends when its commits are pushed to main and tests are green.
3. Don't start the next session until the previous one's commits are on origin/main.

If you want to run two sessions concurrently (e.g. two terminals open), accept that you'll handle push-time merge conflicts by hand. Default to sequential.

---

## Session 0 · Foundation — **✓ COMPLETED 2026-05-24**

Tag: `canvas-foundation-v1` · Engine pick: **React Flow** (`@xyflow/react`).

Shipped: shared types ([src/lib/types.js](../../../src/lib/types.js)), canvas utilities ([src/lib/canvas/](../../../src/lib/canvas/)), decision docs ([docs/superpowers/decisions/](../decisions/)), spike POCs ([experiments/canvas-engine-spike/](../../../experiments/canvas-engine-spike/)).

The original prompt used a PR-based workflow before Abed pulled it back to main-only. The actual code outcome is identical to what a main-only flow would have produced.

---

## Session 1 · Inner Canvas Foundation

```text
You are implementing Sub-project 1 of the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
Foundation decisions and shared types (already on main, tag canvas-foundation-v1):
  docs/superpowers/decisions/2026-05-24-canvas-engine-choice.md
  src/lib/types.js
  src/lib/canvas/*.js

This project uses a main-only git workflow. Work directly on main. Do NOT create a branch, do NOT open a PR, do NOT use a worktree. The design and shared abstractions are settled — do NOT re-brainstorm them.

YOUR JOB FOR THIS SESSION (Sub-project 1 — Inner Canvas Foundation):
Replace the current `NoteView` document-style editor with an inner canvas that holds ONE text-card primitive. After this ships, opening a note shows that note's markdown content inside a single draggable text card on a canvas. No frames, no media cards, no connectors, no link cards — those come in Sub-project 2.

Setup:
1. `git pull origin main` — start from the latest.
2. Invoke `dev-toolkit` to confirm the dev setup is healthy.
3. Query `context7` for `@xyflow/react` current docs.
4. `npm install @xyflow/react` (the engine wasn't installed in Session 0 — that was deferred to this session).

In scope:
- New component `src/components/InnerCanvas.jsx` using React Flow.
- New component `src/components/cards/TextCard.jsx` that renders/edits markdown using the EXISTING `react-markdown` + remark/rehype pipeline from `NoteView.jsx`. Preserve mermaid + chart + KaTeX support exactly.
- Replace `NoteView` usage in `App.jsx` with `InnerCanvas`.
- Lossless migration: write the migration logic in `src/lib/canvas/migrate.js` so every existing note becomes a single TextCard at position (0,0) on its inner canvas. Run it once on first launch behind a `deen.migrate.canvas.v1` localStorage flag (follow the pattern already in `App.jsx`).
- Schema change: add `canvas_state` JSON column to the notes table in the Python service's SQLite migration. Backward-compatible default (null → render fallback).
- Tests: per-card render, drag, edit-commit round trip, migration idempotency.

Out of scope (DO NOT touch — other sub-projects own these):
- Frames, MediaCard, Connector, LinkCard, @mention chips → Sub-project 2
- The `Home` view / `Sidebar` → Sub-project 3
- Dictation flow / model swaps → Sub-project 4
- Voice routing → Sub-project 5
- Structure-aware placement → Sub-project 6

Files you may touch:
- Create: `src/components/InnerCanvas.jsx`, `src/components/cards/TextCard.jsx`, related test files
- Modify: `src/App.jsx` (swap NoteView import), `src/lib/canvas/migrate.js` (fill in)
- Modify with caution (other sub-projects also touch): `src/index.css` (add canvas styles, NAMESPACE all new classes with `.ic-` prefix to avoid conflicts)
- Modify: `python-service/` SQLite schema migration

Workflow:
- Invoke `writing-plans` to produce a detailed, bite-sized task list.
- Execute via `executing-plans` (sub-agent flow doesn't suit main-only — stay inline).
- Use `test-driven-development` per task.
- Commit per task with a descriptive message.
- Run `verification-before-completion` before declaring done.
- `git push origin main` once verification passes.

Post back: a one-paragraph summary of what landed + the commit range (e.g. `abc1234..def5678`).
```

---

## Session 2 · Inner Canvas Primitives (run after Session 1 pushes)

```text
You are implementing Sub-project 2 of the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
Foundation:
  src/lib/types.js, src/lib/canvas/*.js
Inner canvas with TextCard already shipped in Sub-project 1 (on main).

This project uses a main-only git workflow. Work directly on main. No branches, no PRs, no worktrees.

YOUR JOB (Sub-project 2 — Inner Canvas Primitives):
Add the remaining inner-canvas primitives on top of the existing canvas: Frames, MediaCards (images/videos/files), typed Connectors, LinkCards (auto-fetched URL bookmarks), and cross-note @mention chips inside TextCards. After this ships, the inner canvas is the full rich workspace described in the spec.

Setup:
1. `git pull origin main`.
2. Invoke `dev-toolkit`. Query `context7` for React Flow custom-node + custom-edge docs.

In scope:
- `src/components/canvas/Frame.jsx` — labeled rectangle that visually clusters cards; cards inside move with the frame. Use React Flow's native grouping (`type: 'group'` + `parentId` + `extent: 'parent'`).
- `src/components/cards/MediaCard.jsx` — image/video/file/audio. Drag-and-drop import. Use Electron's file APIs for local files; embed by path under `app.getPath('userData')`.
- `src/components/canvas/Connector.jsx` — typed arrow between cards. Types: `supports`, `contradicts`, `see also`, `causes`, `example of`, plus a free-text label. Render as labelled arrow via React Flow custom edge.
- `src/components/cards/LinkCard.jsx` — paste a URL → auto-fetches title/favicon/description/preview. Use a small Python service endpoint `/link-preview` (Open Graph parser).
- `@mention` autocomplete inside TextCard: typing `@` opens a popover of note titles; selecting one inserts a chip that renders as a clickable link in display mode.
- Schema additions: extend `canvas_state` shape to include `frames[]`, `connectors[]`, with all four card types under `cards[]`. Update `src/lib/types.js` additively (never rename or remove fields).
- Tests for each primitive (render, drag, edit, persistence round-trip).

Out of scope:
- Outer pinboard (Sub-project 3)
- Voice routing / dictation / AI (Sub-projects 4, 5, 6)

Workflow: writing-plans → execute (TDD per task) → verification-before-completion → commits pushed to main. Post back the commit range.
```

---

## Session 3 · Outer Pinboard (run after Session 2 pushes — or after Session 1 if you're OK with NoteCardOnCanvas not reusing the latest Frame component)

```text
You are implementing Sub-project 3 of the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
Foundation:
  src/lib/types.js, src/lib/canvas/*.js

This project uses a main-only git workflow. Work directly on main. No branches, no PRs, no worktrees.

YOUR JOB (Sub-project 3 — Outer Pinboard):
Replace the current `Home` view's grid of note cards with an outer canvas — a draggable, zoomable pinboard where each note is a card and users can draw free-form connection lines between them. Existing groups become outer-canvas frames.

Setup:
1. `git pull origin main`.
2. Invoke `dev-toolkit`. Query `context7` for React Flow.

In scope:
- New component `src/components/OuterCanvas.jsx` using the same engine as the inner canvas.
- New `src/components/cards/NoteCardOnCanvas.jsx` — shows note title, last-edited, small preview snippet, pin/tag indicators. (Inner-canvas thumbnail rendering is OUT — defer per spec.)
- Free-form connection lines between note cards (untyped at outer level per spec).
- Frame primitive on the outer canvas to represent groups — REUSE Sub-project 2's `src/components/canvas/Frame.jsx` if it's on main; otherwise create a minimal local Frame and a future session will unify.
- Replace `Home` usage in `App.jsx` with `OuterCanvas`.
- Migration: each existing group becomes an outer-canvas frame. Notes laid out in a default grid inside their group's frame. Ungrouped notes go to the canvas floor. Behind a `deen.migrate.outer-canvas.v1` flag.
- Schema: new `outer_canvas` row (singleton) with JSON state.
- Filters (pinned, tags, archive) become overlays on the canvas, NOT separate views. Keep them in the existing Sidebar but make them toggle layer-visibility on the canvas.
- Tests: render, drag, line draw, migration.

Out of scope:
- Inner canvas changes (Sub-project 1, 2)
- Voice / dictation / AI
- In-canvas text search (spec defers it)

Files you may touch:
- Create: `src/components/OuterCanvas.jsx`, `src/components/cards/NoteCardOnCanvas.jsx`, tests
- Modify: `src/App.jsx` (swap Home import), `src/components/Sidebar.jsx` (filters become layer toggles)
- Delete only after the new path is live and tested: `src/components/Home.jsx`, `src/components/NoteCard.jsx`, `src/components/GroupTree.jsx`, `src/components/MoveToGroupModal.jsx`
- CSS: prefix new classes with `.oc-` to stay in your namespace
- Modify: `python-service/` add `outer_canvas` table

Workflow: writing-plans → execute (TDD) → verification-before-completion → push to main. Post back the commit range.
```

---

## Session 4 · Dictation Collapse + Model Swaps (independent — can run any time after Session 0)

```text
You are implementing Sub-project 4 of the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md

This project uses a main-only git workflow. Work directly on main. No branches, no PRs, no worktrees.

YOUR JOB (Sub-project 4 — Dictation Collapse + Model Swaps):
Remove the two-mode dictation picker (Verbatim / AI Rewrite). Make AI Rewrite the default and ONLY visible mode. Demote verbatim to a modifier reachable via the voice phrase "quote:" / "verbatim:" or the `Shift+Ctrl+Space` hotkey. Add sacred-content preservation rules to the rewrite prompt. Swap transcription from current OpenAI Whisper to Deepgram Nova-3 (streaming). Add Kokoro TTS for 1-second hear-back confirmations after captures.

Setup:
1. `git pull origin main`.
2. Invoke `dev-toolkit`. Query `context7` for: Deepgram Nova-3 API, Kokoro TTS Python package, current Anthropic Claude pricing for the rewrite model.

In scope (renderer side):
- Remove the Verbatim / AI Rewrite picker from `src/components/NoteView.jsx` dictation-panel. (If `NoteView.jsx` has already been replaced by `InnerCanvas` + `TextCard` from Session 1, do the equivalent removal in those files. Coordinate by reading the latest main before starting.)
- Add `Shift+Ctrl+Space` push-to-talk hotkey for verbatim mode (existing `Ctrl+Space` stays as AI rewrite).
- On capture success, trigger a 1-second TTS confirmation ("Saved to <note name>") via a new IPC channel to the Python service.

In scope (Python service side):
- Replace current transcription call with Deepgram Nova-3 streaming. Keep self-hosted `faster-whisper` as automatic fallback when offline or Deepgram unreachable.
- Update AI rewrite prompt with sacred-content rules: preserve verbatim quoted strings (`"..."`), code-like identifiers (camelCase, snake_case, dotted), proper nouns, brand names, numbers + units, URLs.
- Add Kokoro TTS endpoint `/tts/say?text=...` that returns WAV. Use a warm friendly voice from Kokoro's options.
- Add a `mode=verbatim|rewrite` query param on `/transcribe-push-to-talk` controlled by the hotkey.

Out of scope:
- Voice routing grammar (Sub-project 5)
- Structure-aware placement (Sub-project 6)
- Canvas UI changes

Files you may touch:
- Create: `src/lib/dictation-modifiers.js`, `python-service/tts_kokoro.py`, tests
- Modify: `src/components/NoteView.jsx` OR Session-1's replacement (whichever is on main), `electron/preload.js` (TTS IPC), `python-service/main.py` (Deepgram + Kokoro + sacred-content prompt)
- Configuration: `.env` for new `DEEPGRAM_API_KEY` (document in README — DO NOT commit secret)

Workflow: writing-plans → execute (TDD where possible, manual verification for audio paths) → verification-before-completion (trigger a real capture and confirm hear-back fires) → push to main. Post back the commit range.
```

---

## Session 5 · Voice Routing v1 (independent — can run any time after Session 0)

```text
You are implementing Sub-project 5 of the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md (section: Voice capture)

This project uses a main-only git workflow. Work directly on main. No branches, no PRs, no worktrees.

YOUR JOB (Sub-project 5 — Voice Routing v1):
Implement the 4-pattern voice grammar that decides WHERE a capture lands. Hands-free is the priority — every edge case must be resolvable by voice alone, no clicking. Create the Quick Inbox note. Redesign the desktop bubble per spec (context-aware default + pinboard-snapshot picker for desk mode).

Setup:
1. `git pull origin main`.
2. Invoke `dev-toolkit`. Query `context7` for current Anthropic Claude Haiku 4.5 API + local embedding library options (recommend `@xenova/transformers` in renderer or `sentence-transformers` in Python).

In scope:
- 4-pattern voice grammar in the Python service's capture handler:
  - `"Hey Deen, [content]"` → Quick Inbox
  - `"Hey Deen, in <name>, [content]"` → fuzzy-match note title
  - `"Hey Deen, new note about <topic>, [content]"` → create new note
  - `"Hey Deen, continue, [content]"` → most-recently-captured note within last 30 min
- Routing tiered: local embedding+fuzzy first, fallback to Haiku 4.5 for ambiguous cases (multi-match, low-confidence mishears).
- Voice-only disambiguation: when ambiguous or no match, the app speaks back a question and listens for yes/no/named answer. Build the listen-for-response loop.
- Quick Inbox creation: a special note (pinned, hidden in archive view, never deletable) created on first launch if it doesn't exist.
- Bubble redesign:
  - Context-aware default: if Deen Notes is foreground with a note open, route there silently.
  - Picker (desk mode only): pinboard snapshot — mini view of notes — for click selection. Sticky "Quick Inbox" target at top.
  - Bubble itself: minimal, ambient, hover-reveal (consistent with Abed's preference).
- Spoken hear-back: after every successful capture, app calls Sub-project 4's `/tts/say?text=Saved to <note>` if available (graceful no-op if Sub-project 4 hasn't landed yet).

Out of scope:
- Structure-aware placement (Sub-project 6 — this sub-project just ROUTES to a note, doesn't place into a frame)
- Canvas UI changes
- The dictation modifier hotkeys (Sub-project 4)

Files you may touch:
- Create: `python-service/voice_routing.py`, `python-service/quick_inbox.py`, tests
- Modify: `python-service/main.py` (route capture through new router), `electron/main.js` + `electron/bubble.html` + `electron/picker.html` (bubble + picker redesign), `electron/picker-preload.js`
- Modify: `src/App.jsx` (handle "Quick Inbox" specially in sidebar)
- CSS for bubble: prefix `.bubble-` to stay in namespace

Workflow: writing-plans → execute (TDD on routing logic; manual verification on bubble UX) → verification-before-completion (run all 4 voice patterns end-to-end) → push to main. Post back the commit range.
```

---

## Session 6 · Structure-Aware Placement (run after Sessions 1, 2, 5 are on main)

```text
You are implementing Sub-project 6 of the Deen Notes canvas redesign — the killer feature. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md (section: Structure-aware placement)

Prerequisites that MUST be on main before starting:
- Sub-project 1 (Inner Canvas Foundation)
- Sub-project 2 (Inner Canvas Primitives, especially Frames)
- Sub-project 5 (Voice Routing v1, so we know WHICH note to place into)

This project uses a main-only git workflow. Work directly on main. No branches, no PRs, no worktrees.

YOUR JOB (Sub-project 6 — Structure-Aware Placement):
When the user dictates into an open inner canvas, don't just append text — read the canvas (frames, cards, connectors), classify the utterance, format it as a clean card, place it in the most-fitting frame, and optionally draw a typed connector to related cards. Show a non-blocking toast for confirm/undo. Fall back to a "Loose ideas" auto-frame when the model isn't confident.

Setup:
1. `git pull origin main`.
2. Invoke `dev-toolkit`. Query `context7` for current Anthropic Claude Sonnet 4.5+ API + pricing + best-practice prompt patterns.

In scope:
- New service module `python-service/structure_placement.py` — given a canvas state + a transcribed utterance, returns `{ card: {...}, target_frame_id, connectors: [...] }`.
- Claude Sonnet 4.5+ integration with a carefully designed system prompt + JSON-schema-constrained output.
- Canvas serialization: a compact JSON representation that fits Sonnet's context cheaply. For canvases with >200 cards, pre-summarize via a cheaper model (Haiku) first.
- "Loose ideas" auto-frame: created on first uncertain placement; not shown until it has contents.
- Toast UI in `src/components/InnerCanvas.jsx`: "Placed in <frame> · <connector type if any>. Move / Undo." Non-blocking, auto-dismisses in 6s.
- Undo: snapshot canvas state before placement; restore on click.
- Sacred-content preservation rules carry over from Sub-project 4's prompt — share the prompt fragment.
- Floating-card fallback when canvas has zero frames (just drop near cursor / top-left).
- Tests: deterministic unit tests with mocked Sonnet responses for the formatting/classification logic; end-to-end manual verification on a real canvas.

Out of scope:
- Auto-creating new frames (deferred per spec — `option C`)
- Preview-before-place ghost mode (deferred per spec — `option D`)
- DeepSeek/cheaper-model A/B test (deferred per spec)

Files you may touch:
- Create: `python-service/structure_placement.py`, `python-service/canvas_serializer.py`, tests, `src/components/canvas/PlacementToast.jsx`
- Modify: `python-service/main.py` (wire structure-placement into the capture pipeline when target note is "open"), `src/components/InnerCanvas.jsx` (show toast + handle undo), `src/hooks/useWebSocket.js` (new event type for placement results)

Workflow: writing-plans → execute (TDD on the placement logic with mocked Sonnet; manual verification of the full flow on a real canvas with frames) → verification-before-completion (success criteria from spec: ≥80% correct frame placement on canvases with ≥3 frames) → push to main. Post back the commit range.
```

---

## Session 7 · Integration & End-to-End Verification (final, run after all others)

```text
You are doing final integration for the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md

All six sub-projects have been pushed to main:
- 0 Foundation, 1 Inner Canvas Foundation, 2 Inner Canvas Primitives,
- 3 Outer Pinboard, 4 Dictation+Models, 5 Voice Routing, 6 Structure-Aware Placement

This project uses a main-only git workflow. Work directly on main. No branches, no PRs, no worktrees.

YOUR JOB (Session 7 — Integration):
Verify the whole system works end-to-end as a coherent product. Find and fix the seams where the sequential sub-projects don't quite line up. Verify the spec's success criteria.

Setup:
1. `git pull origin main`.
2. Invoke `dev-toolkit`. Confirm the dev setup is healthy.
3. Invoke `prod-observability` — this is the pre-release pass. Sentry installed with sourcemaps + PII scrubbing, top-level error boundary in place, fake errors triggered in renderer + Python to verify they land in the dashboard.
4. Query `context7` for current best practices on Electron production hardening.

Integration checklist (write a doc `docs/superpowers/verification/2026-MM-DD-canvas-redesign-e2e.md` and walk through each item, fix anything broken):

A. **Visual consistency across canvases.**
- Outer pinboard and inner canvas share the same engine and look like siblings, not different apps.
- CSS class prefixes from sub-projects don't collide.
- Sidebar filters work as layer toggles on the outer canvas AND don't break inner canvas navigation.

B. **Voice flow end-to-end.**
- All 4 voice patterns work hands-free with no clicks.
- "Hey Deen, in <name>" → routes correctly → structure-aware placement runs → toast appears → audio hear-back fires.
- Verbatim modifier (`Shift+Ctrl+Space` and `"verbatim:"` phrase) bypasses AI rewrite but still routes correctly.
- Quick Inbox catches captures with no destination.

C. **Migration correctness.**
- Take a snapshot of an existing user's `notes.db` BEFORE the redesigned build runs.
- Run the redesigned build, let all migrations execute.
- Verify: zero markdown content lost, every old note opens, every old group is now an outer-canvas frame, pin/tag/archive state preserved.

D. **AI model integration.**
- Deepgram Nova-3 transcription works; faster-whisper fallback triggers when Deepgram is unreachable.
- Voice routing uses local embeddings; Haiku only fires on ambiguity.
- Sonnet 4.5+ placement returns valid JSON consistently; falls back to "Loose ideas" frame on low confidence.
- Kokoro TTS plays the 1-second confirmation reliably.

E. **Spec success criteria** (from `docs/superpowers/specs/2026-05-24-canvas-redesign-design.md`):
- App launches in under 2 seconds.
- Inner canvas renders smoothly with 100+ cards on a modest laptop.
- Voice routing hits correct note ≥90% hands-free.
- Structure-aware placement hits right frame ≥80% on canvases with ≥3 frames.

F. **Production hardening (per `prod-observability` skill).**
- Sentry installed in both renderer and Python service with PII scrubbing.
- Top-level error boundary in React wrapping `App`.
- Fake errors triggered in renderer and Python — verified appearing in Sentry dashboard.
- README updated with launch notes for users + env var requirements.

G. **Build the installer** and verify it installs+launches on a clean Windows VM.

Run `verification-before-completion` before declaring done. Write the verification doc with checkbox-by-checkbox status. Push all integration fixes to main. Post back the commit range + the verification-doc link.
```

---

## Coordination notes for Abed

- **CSS namespace prefixes:** Sub-project 1 uses `.ic-`, Sub-project 3 uses `.oc-`, Sub-project 5 uses `.bubble-`. Sub-projects 2, 4, 6 inherit from the namespaces they extend.
- **`src/lib/types.js`:** any sub-project that extends a type must do it **additively**. Never rename a field. Never remove a field without bumping `schemaVersion` and writing a migration in `src/lib/canvas/migrate.js`.
- **Shared files at conflict risk:** `src/App.jsx`, `package.json`, `python-service/main.py`. Pull main fresh before editing any of these; commit small + descriptive.
- **If a session blocks on missing work** (e.g. Sub-project 5 wanting Sub-project 4's TTS endpoint): use the graceful no-op pattern noted in the prompts. Don't block — wire a fallback and add a TODO.
- **Recovery from a bad push:** `git revert <sha> && git push`. Don't try to force-push main.
