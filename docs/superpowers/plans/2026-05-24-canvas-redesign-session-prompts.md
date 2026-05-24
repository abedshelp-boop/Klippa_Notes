---
title: Deen Notes Canvas Redesign — Session Prompts
date: 2026-05-24
status: ready-to-launch
spec: docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
---

# Canvas Redesign — Session Prompts

Seven self-contained prompts. Each starts a fresh Claude Code session that handles one sub-project end-to-end (plan → implement → PR). Copy the prompt, paste it as the first message in a new session.

## How to use

1. **Run Session 0 first, alone, to completion.** It locks the shared decisions every other session depends on. Don't skip this.
2. **Once Session 0 merges to main**, launch Sessions 1, 3, 4, 5 in parallel (four terminals / four sessions, your choice).
3. **Once Session 1 merges**, launch Session 2.
4. **Once Sessions 1, 2, 5 all merge**, launch Session 6.
5. **Finally, launch Session 7** for cross-cutting integration verification.

Each session creates its own git worktree (so your main checkout stays clean), works on its own branch, and opens a PR at the end. Review and merge before launching the next wave.

---

## Session 0 · Foundation (MUST run first, alone)

```text
You are starting work on the Deen Notes canvas redesign. The full design spec is at:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md

Read it in full before doing anything else. The spec is already approved — do NOT invoke the brainstorming skill to re-design anything; the design is settled.

YOUR JOB FOR THIS SESSION:
Lay the foundation that six follow-on sessions will build on in parallel. You are NOT implementing any sub-project. You are nailing down the shared cross-cutting decisions and producing a small "foundation PR" with shared abstractions.

Mandatory pre-work:
1. Invoke the `dev-toolkit` skill and verify the dev-time setup is in place. Fix anything missing before writing code.
2. Query the `context7` MCP for current docs/pricing/availability of:
   - React Flow (`@xyflow/react`) and tldraw — the two canvas engine candidates
   - Deepgram Nova-3 API
   - Anthropic Claude Sonnet 4.5+ and Haiku 4.5 (or current equivalents)
   - Kokoro TTS (Python package + voice options)
   - Fish Audio (for comparison only — already ruled out unless context7 shows something dramatically new)

Decisions you must lock in this session (record in `docs/superpowers/decisions/`):
1. **Canvas engine.** React Flow vs tldraw. Spike a 30-line POC for each (just a draggable card on a canvas), pick one, document why.
2. **Data model schemas** (JSDoc types in `src/lib/types.js`):
   - `Card` (text/media/link variants), `Frame`, `Connector`, `InnerCanvasState`, `OuterCanvasState`, `NoteCard` (note as outer-canvas card)
   - Make sure every field every sub-project needs is on the type
3. **Canvas state serialization shape** — single JSON column on notes table for inner-canvas state, single JSON column on a new `outer_canvas` table for outer state. Define the exact shape.
4. **Worktree convention.** Each sub-project branches from this Foundation merge commit. Branch naming: `canvas/<n>-<short-name>` (e.g. `canvas/1-inner-foundation`).
5. **Shared utility files** to create now so sub-projects can import them:
   - `src/lib/types.js` — JSDoc typedefs
   - `src/lib/canvas/ids.js` — id generation (e.g. `cardId()`, `frameId()`)
   - `src/lib/canvas/validators.js` — schema guards
   - `src/lib/canvas/migrate.js` — placeholder for migration logic (sub-project 1 fills it)

Deliverables for this session:
- One PR titled "foundation: canvas redesign — shared types + engine choice"
- Engine POC files committed under `experiments/canvas-engine-spike/` (so the loser is preserved for record)
- A short `docs/superpowers/decisions/2026-05-24-canvas-engine-choice.md` explaining the pick
- `src/lib/types.js`, `src/lib/canvas/*.js` skeletons
- A tag `canvas-foundation-v1` on the merge commit so other sessions can branch from a known point
- All tests passing (your project canary + any new ones)

Invoke `writing-plans` to write the detailed implementation plan for the above, then execute it. End with `verification-before-completion` before claiming done. Do NOT invoke `prod-observability` — this is dev work, not a user-facing deploy.

When you finish, post back: the engine choice, the tag name, and the PR URL.
```

---

## Session 1 · Inner Canvas Foundation (Wave 1, parallel-safe)

```text
You are implementing Sub-project 1 of the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
Foundation decisions and shared types:
  docs/superpowers/decisions/2026-05-24-canvas-engine-choice.md
  src/lib/types.js
  src/lib/canvas/*.js

The Foundation PR has already merged to main. The design and the shared abstractions are settled — do NOT re-brainstorm them.

YOUR JOB FOR THIS SESSION (Sub-project 1 — Inner Canvas Foundation):
Replace the current `NoteView` document-style editor with an inner canvas that holds ONE text-card primitive. After this ships, opening a note shows that note's markdown content inside a single draggable text card on a canvas. No frames, no media cards, no connectors, no link cards — those come in Sub-project 2.

Setup:
1. Create a git worktree off the `canvas-foundation-v1` tag, branch named `canvas/1-inner-foundation`. Use the `using-git-worktrees` skill.
2. Invoke `dev-toolkit` to confirm the dev setup is in place in the worktree.
3. Query `context7` for the chosen canvas engine's current docs (whichever the foundation picked).

In scope:
- New component `src/components/InnerCanvas.jsx` using the chosen engine.
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
- Execute via `subagent-driven-development` OR `executing-plans` (your call).
- Use `test-driven-development` per task.
- Run `verification-before-completion` before declaring done.

Deliverable: one PR titled "feat(canvas): inner canvas foundation with text card primitive". Existing notes must still be openable, editable, savable, and identical-looking after migration. Post back the PR URL.
```

---

## Session 2 · Inner Canvas Primitives (Wave 2, after Session 1 merges)

```text
You are implementing Sub-project 2 of the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
Foundation:
  src/lib/types.js, src/lib/canvas/*.js
Inner canvas with TextCard already shipped in Sub-project 1 (merged to main).

YOUR JOB (Sub-project 2 — Inner Canvas Primitives):
Add the remaining inner-canvas primitives on top of the existing canvas: Frames, MediaCards (images/videos/files), typed Connectors, LinkCards (auto-fetched URL bookmarks), and cross-note @mention chips inside TextCards. After this ships, the inner canvas is the full rich workspace described in the spec.

Setup:
1. Worktree off latest main, branch `canvas/2-inner-primitives`.
2. Invoke `dev-toolkit`. Query `context7` for canvas engine docs as needed.

In scope:
- `src/components/canvas/Frame.jsx` — labeled rectangle that visually clusters cards; cards inside move with the frame.
- `src/components/cards/MediaCard.jsx` — image/video/file/audio. Drag-and-drop import. Use Electron's file APIs for local files; embed by path under `app.getPath('userData')`.
- `src/components/canvas/Connector.jsx` — typed arrow between cards. Types: `supports`, `contradicts`, `see also`, `causes`, `example of`, plus a free-text label. Render as labelled arrow.
- `src/components/cards/LinkCard.jsx` — paste a URL → auto-fetches title/favicon/description/preview. Use a small Python service endpoint `/link-preview` (Open Graph parser).
- `@mention` autocomplete inside TextCard: typing `@` opens a popover of note titles; selecting one inserts a chip that renders as a clickable link in display mode.
- Schema additions: extend `canvas_state` shape to include `frames[]`, `connectors[]`, with all four card types under `cards[]`.
- Tests for each primitive (render, drag, edit, persistence round-trip).

Out of scope:
- Outer pinboard (Sub-project 3)
- Voice routing / dictation / AI (Sub-projects 4, 5, 6)

Files you may touch:
- Create: `src/components/canvas/Frame.jsx`, `src/components/canvas/Connector.jsx`, `src/components/cards/MediaCard.jsx`, `src/components/cards/LinkCard.jsx`, related tests
- Modify: `src/components/InnerCanvas.jsx` (register new node/edge types), `src/lib/types.js` (extend types — coordinate with foundation)
- Modify: `python-service/` add `/link-preview` endpoint
- CSS: prefix new classes with `.ic-` to stay in your namespace

Workflow: writing-plans → execute (TDD per task) → verification-before-completion → PR titled "feat(canvas): frames, media, connectors, link cards, @mentions". Post PR URL when done.
```

---

## Session 3 · Outer Pinboard (Wave 1, parallel-safe)

```text
You are implementing Sub-project 3 of the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
Foundation:
  src/lib/types.js, src/lib/canvas/*.js

YOUR JOB (Sub-project 3 — Outer Pinboard):
Replace the current `Home` view's grid of note cards with an outer canvas — a draggable, zoomable pinboard where each note is a card and users can draw free-form connection lines between them. Existing groups become outer-canvas frames.

Setup:
1. Worktree off `canvas-foundation-v1`, branch `canvas/3-outer-pinboard`. Parallel-safe with Sessions 1, 4, 5.
2. Invoke `dev-toolkit`. Query `context7` for the chosen canvas engine.

In scope:
- New component `src/components/OuterCanvas.jsx` using the same engine as the inner canvas.
- New `src/components/cards/NoteCardOnCanvas.jsx` — shows note title, last-edited, small preview snippet, pin/tag indicators. (Inner-canvas thumbnail rendering is OUT — defer per spec.)
- Free-form connection lines between note cards (untyped at outer level per spec).
- Frame primitive on the outer canvas to represent groups — REUSE Sub-project 2's Frame component if it's merged; otherwise create a minimal `OuterFrame.jsx` and Sub-project 2 will unify them later. Coordinate by reading `src/components/canvas/Frame.jsx` if it exists at branch time.
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
- Delete/archive: `src/components/Home.jsx`, `src/components/NoteCard.jsx`, `src/components/GroupTree.jsx`, `src/components/MoveToGroupModal.jsx` (remove only after PR is approved and replaced)
- CSS: prefix new classes with `.oc-` to stay in your namespace
- Modify: `python-service/` add `outer_canvas` table

Workflow: writing-plans → execute (TDD) → verification-before-completion → PR titled "feat(canvas): outer pinboard replaces home grid". Post PR URL.
```

---

## Session 4 · Dictation Collapse + Model Swaps (Wave 1, parallel-safe)

```text
You are implementing Sub-project 4 of the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md

YOUR JOB (Sub-project 4 — Dictation Collapse + Model Swaps):
Remove the two-mode dictation picker (Verbatim / AI Rewrite). Make AI Rewrite the default and ONLY visible mode. Demote verbatim to a modifier reachable via the voice phrase "quote:" / "verbatim:" or the `Shift+Ctrl+Space` hotkey. Add sacred-content preservation rules to the rewrite prompt. Swap transcription from current OpenAI Whisper to Deepgram Nova-3 (streaming). Add Kokoro TTS for 1-second hear-back confirmations after captures.

Setup:
1. Worktree off `canvas-foundation-v1`, branch `canvas/4-dictation-models`. Parallel-safe with Sessions 1, 3, 5.
2. Invoke `dev-toolkit`. Query `context7` for: Deepgram Nova-3 API, Kokoro TTS Python package, current OpenAI/Anthropic pricing for the rewrite model.

In scope (renderer side):
- Remove the Verbatim / AI Rewrite picker from `src/components/NoteView.jsx` dictation-panel. (NoteView still exists at the time this sub-project runs in parallel with Sub-project 1 — coordinate: if NoteView is gone by integration time, the equivalent UI is in InnerCanvas/TextCard. Wrap your changes in a helper module imported by both, so integration is trivial.)
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
- Modify: `src/components/NoteView.jsx` (dictation panel — remove picker), `electron/preload.js` (TTS IPC), `python-service/main.py` (Deepgram + Kokoro + sacred-content prompt)
- Configuration: `.env` for new `DEEPGRAM_API_KEY` (document in README — DO NOT commit secret)

Workflow: writing-plans → execute (TDD where possible, manual verification for audio paths) → verification-before-completion (trigger a real capture and confirm hear-back fires) → PR titled "feat(dictation): collapse modes + deepgram streaming + kokoro tts". Post PR URL.
```

---

## Session 5 · Voice Routing v1 (Wave 1, parallel-safe)

```text
You are implementing Sub-project 5 of the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md (section: Voice capture)

YOUR JOB (Sub-project 5 — Voice Routing v1):
Implement the 4-pattern voice grammar that decides WHERE a capture lands. Hands-free is the priority — every edge case must be resolvable by voice alone, no clicking. Create the Quick Inbox note. Redesign the desktop bubble per spec (context-aware default + pinboard-snapshot picker for desk mode).

Setup:
1. Worktree off `canvas-foundation-v1`, branch `canvas/5-voice-routing`. Parallel-safe with Sessions 1, 3, 4.
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
- Spoken hear-back: after every successful capture, app calls Sub-project 4's `/tts/say?text=Saved to <note>` if available (graceful no-op if Sub-project 4 hasn't merged yet).

Out of scope:
- Structure-aware placement (Sub-project 6 — this sub-project just ROUTES to a note, doesn't place into a frame)
- Canvas UI changes
- The dictation modifier hotkeys (Sub-project 4)

Files you may touch:
- Create: `python-service/voice_routing.py`, `python-service/quick_inbox.py`, tests
- Modify: `python-service/main.py` (route capture through new router), `electron/main.js` + `electron/bubble.html` + `electron/picker.html` (bubble + picker redesign), `electron/picker-preload.js`
- Modify: `src/App.jsx` (handle "Quick Inbox" specially in sidebar)
- CSS for bubble: prefix `.bubble-` to stay in namespace

Workflow: writing-plans → execute (TDD on routing logic; manual verification on bubble UX) → verification-before-completion (run all 4 voice patterns end-to-end) → PR titled "feat(voice): 4-pattern routing + quick inbox + bubble redesign". Post PR URL.
```

---

## Session 6 · Structure-Aware Placement (Wave 3, after Sessions 1, 2, 5 merge)

```text
You are implementing Sub-project 6 of the Deen Notes canvas redesign — the killer feature. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md (section: Structure-aware placement)

Prerequisites that MUST be merged to main before starting:
- Sub-project 1 (Inner Canvas Foundation)
- Sub-project 2 (Inner Canvas Primitives, especially Frames)
- Sub-project 5 (Voice Routing v1, so we know WHICH note to place into)

YOUR JOB (Sub-project 6 — Structure-Aware Placement):
When the user dictates into an open inner canvas, don't just append text — read the canvas (frames, cards, connectors), classify the utterance, format it as a clean card, place it in the most-fitting frame, and optionally draw a typed connector to related cards. Show a non-blocking toast for confirm/undo. Fall back to a "Loose ideas" auto-frame when the model isn't confident.

Setup:
1. Worktree off latest main, branch `canvas/6-structure-aware-placement`.
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

Workflow: writing-plans → execute (TDD on the placement logic with mocked Sonnet; manual verification of the full flow on a real canvas with frames) → verification-before-completion (success criteria from spec: ≥80% correct frame placement on canvases with ≥3 frames) → PR titled "feat(ai): structure-aware capture placement with toast + undo". Post PR URL.
```

---

## Session 7 · Integration & End-to-End Verification (final, alone)

```text
You are doing final integration for the Deen Notes canvas redesign. Full design spec:
  docs/superpowers/specs/2026-05-24-canvas-redesign-design.md

All six sub-projects have been merged to main:
- 0 Foundation, 1 Inner Canvas Foundation, 2 Inner Canvas Primitives,
- 3 Outer Pinboard, 4 Dictation+Models, 5 Voice Routing, 6 Structure-Aware Placement

YOUR JOB (Session 7 — Integration):
Verify the whole system works end-to-end as a coherent product. Find and fix the seams where the parallel sub-projects don't quite line up. Verify the spec's success criteria.

Setup:
1. Worktree off latest main, branch `canvas/7-integration`.
2. Invoke `dev-toolkit`. Confirm the dev setup is healthy on integrated main.
3. Invoke `prod-observability` — this is the final pre-release pass. Sentry installed with sourcemaps + PII scrubbing, top-level error boundary in place, fake errors triggered in renderer + Python to verify they land in the dashboard.
4. Query `context7` for current best practices on Electron production hardening.

Integration checklist (write a doc `docs/superpowers/verification/2026-MM-DD-canvas-redesign-e2e.md` and walk through each item, fix anything broken):

A. **Visual consistency across canvases.**
- Outer pinboard and inner canvas share the same engine and look like siblings, not different apps.
- CSS class prefixes from parallel sub-projects don't collide.
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
- Convex dashboard reviewed if backend touches Convex (this project doesn't, but confirm).
- README updated with launch notes for users + env var requirements.

G. **Build the installer** and verify it installs+launches on a clean Windows VM.

Run `verification-before-completion` before declaring done. Write the verification doc with checkbox-by-checkbox status. PR titled "chore: canvas redesign integration + e2e verification + production hardening". Post PR URL with the verification-doc link.
```

---

## Coordination notes for Abed

- **CSS namespace prefixes:** Sub-project 1 uses `.ic-`, Sub-project 3 uses `.oc-`, Sub-project 5 uses `.bubble-`. Sub-projects 2, 4, 6 inherit from the namespaces they extend. This is the lightest-weight collision avoidance for parallel CSS work.
- **`src/lib/types.js`:** any sub-project that needs to extend a type must edit in its own branch; integration session unifies. Keep extensions additive (no field renames).
- **Shared files at risk of conflicts:** `src/App.jsx`, `package.json`, `python-service/main.py`. Review the diffs carefully before merging each PR.
- **If a sub-project blocks on missing work** (e.g. Sub-project 5 wanting Sub-project 4's TTS endpoint): use the graceful no-op pattern noted in the prompts. Don't block.
- **Don't merge two Wave 1 PRs the same day without testing them together.** Spin up the integration branch locally, merge both, run the app, confirm no breakage, then push each individually.
- **You can launch fewer than 4 Wave 1 sessions if reviewing 4 simultaneously is too much.** The dependency graph still works with 2 at a time (e.g. 1+4, then 3+5).
