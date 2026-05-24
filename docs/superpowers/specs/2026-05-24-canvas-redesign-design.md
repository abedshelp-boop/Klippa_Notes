---
title: Deen Notes — Canvas Redesign
date: 2026-05-24
status: approved-design
applies_to: Deen Notes (Electron + Vite + React 19 + Python FastAPI service)
references:
  - docs/superpowers/specs/2026-05-20-dev-toolkit-design.md
  - .superpowers/brainstorm/3150-1779617672/content/ (visual companion mockups)
---

# Deen Notes — Canvas Redesign

## Why this exists

Deen Notes today is a voice-activated note-taking app whose viewer/editor surface looks and feels like Google Docs — a single linear markdown column inside each note. Abed dislikes that shape. He wants a spatial, grid-like editing surface in the spirit of Miro, but designed *for* notes (not whiteboarding).

This spec captures the redesign brainstormed on 2026-05-24. It changes the product surface from "list of markdown documents" to **nested canvases**: a draggable pinboard of notes at the top level, and a structured canvas of cards inside each note. It also evolves the voice capture (`Hey Deen`) from "transcribe-into-a-doc" to a structure-aware placement system that reads the open canvas as context and drops new cards in the right place automatically.

The voice-driven capture flow is preserved and made more central. Notes-as-documents is replaced. The data already in the app is migrated forward.

## The shift in one sentence

**From:** sidebar list of notes → open one → linear markdown document with one big textarea.
**To:** outer pinboard canvas (notes are cards, drag and connect them) → open one → inner canvas of structured cards inside frames, drag/connect them too.

## Architecture: nested canvases

Two levels of spatial freedom, with consistent interaction model:

### Outer canvas (replaces today's `Home`)

- The home view IS a draggable, infinite, zoomable pinboard.
- Each note is a card on this canvas. Cards have variable size; users drag, resize, and arrange freely. Snap-to-grid available but optional.
- **Connection lines between cards** are first-class. Free-form (no required semantic type at v1 — typed connectors land at the inner-canvas level where they matter more).
- Card surface shows: title, last-edited timestamp, small preview snippet, pinned/tagged indicators. Optionally: a small thumbnail of the inner canvas (defer to v1.1 if expensive to render).
- Click a card → opens its inner canvas (full-screen transition or pane-swap; pick during writing-plans).
- **Frames** (see inner-canvas section) are also valid on the outer canvas — used to cluster related note-cards. This is how today's groups migrate forward (one group → one outer-canvas frame).
- Existing filters (pinned, tags, archive) remain available as overlays on the canvas, not as separate views. (Net-new in-canvas text search is out of scope for v1 — see deferred list.)

### Inner canvas (replaces today's `NoteView`)

A canvas with four primitive types, chosen for note-taking focus (no freehand shapes, no whiteboarding tools):

1. **Text cards** — draggable containers holding **full markdown**: headings, lists, code blocks (syntax highlighted), math (KaTeX), tables, mermaid diagrams, charts, embedded images. Existing rendering pipeline (`react-markdown` + `remark-gfm` + `remark-math` + `rehype-katex` + `rehype-highlight` + `rehype-sanitize` + the custom `code` override for mermaid/chart fences) is preserved verbatim inside each card.
2. **Frames** — labeled regions that visually cluster cards. Cards inside a frame move with it. Frames give the canvas its "structure" and are what the AI reads to make placement decisions.
3. **Media items** — images, videos, audio clips, files. First-class cards with their own type, not embedded inside text cards (so they can be sized/dragged independently).
4. **Typed connectors** — arrows between cards that can carry semantics: `supports`, `contradicts`, `see also`, `causes`, `example of`, plus a free-text label. Used by the AI for structure-aware placement decisions.

Additional card types:

- **Link cards** — paste a URL, get an auto-fetched card with favicon, title, description, preview thumbnail. (Like Notion bookmark blocks.)
- **Cross-note links** — `@mention` another note inside any text card → renders as a clickable chip that opens that note's canvas.

Card rotation: supported (the user explicitly asked for it).

## Voice capture: "Hey Deen" flow

This is the killer feature and gets the most attention in this spec.

### Voice routing grammar

Four spoken patterns cover all cases. None require touching a mouse or keyboard — critical for the driving/cooking use cases this app exists for.

| User says | What happens |
|---|---|
| `"Hey Deen, [content]"` | Routes to **Quick Inbox** (always-there special note, no structure, parking lot). |
| `"Hey Deen, in Sapiens, [content]"` | Fuzzy-matches "Sapiens" against note titles → routes there. |
| `"Hey Deen, new note about cooking eggs, [content]"` | Creates new note titled "Cooking eggs" → routes there. |
| `"Hey Deen, continue, [content]"` | Routes to most-recently-captured-into note (last 30 min window). |

### Edge cases (all handled by voice — never falls back to a click)

- **Ambiguous match** (two notes match) → app speaks back: *"Sapiens chapter 1 or chapter 2?"* — user answers by voice.
- **Mispronunciation / mishearing** → matching uses phonetic + semantic similarity, not just string match. Borderline confidence → confirms: *"Did you mean Sapiens?"* — yes/no by voice.
- **No match** → *"No note called Sapiens — create one? Yes or no."*
- **Hear-back** — every successful capture gets a 1-second spoken confirmation: *"Saved to Sapiens"* — so the user knows without looking.

### Structure-aware placement (the magic)

When the user dictates *into an open canvas with existing structure*, the AI doesn't just append text — it reads the canvas and places the new card intelligently:

1. **Transcribe** the audio.
2. **Read canvas structure** — passes the frames, cards (titles + content), and connectors to the placement model as JSON context.
3. **Classify** the utterance against the existing structure (e.g. "this is a counterpoint to claim X in frame Y").
4. **Format** the card as clean markdown (turn rambling prose into bullet points, label citations, preserve code/numbers/quotes verbatim — see verbatim rules below).
5. **Place** the card inside the most-fitting frame and **draw a typed connector** to related cards where confident.
6. **Toast** a non-blocking confirmation: *"Placed in Key Ideas — contradicts 'Compute drives most gains.' Move / Undo."* Plus the 1-second audio confirmation.

**Confidence fallback (Q3-b from brainstorm):** when the AI is not confident about placement, the card goes into a **"Loose ideas"** auto-frame that appears on the canvas only when it has contents. User drags the card into a real frame later (or it stays where it is — no nag).

**No structure yet?** If the inner canvas has no frames (fresh note), the AI just drops the card as a floating card at a sensible position (cursor location if known, otherwise top-left below existing cards). No forced structure.

### Dictation modes — collapsed

Today there are two top-level modes the user picks every time: *Verbatim* and *AI Rewrite*. This was friction.

**New model: AI Rewrite is the default and the only top-level mode.** Verbatim is demoted to a modifier:

- **Voice modifier:** `"Hey Deen, quote: ..."` or `"Hey Deen, verbatim: ..."` — preserves wording exactly within an otherwise rewritten note.
- **Hotkey modifier (push-to-talk):** `Ctrl+Space` = AI rewrite, `Shift+Ctrl+Space` = verbatim.
- **Per-card mode toggle:** re-opening a captured card lets the user flip its mode (regenerate from the original audio).

**Sacred content** (always preserved verbatim by the rewriter, even in AI Rewrite mode):

- Quoted strings (anything inside `"..."` or after the word "quote:")
- Code blocks (anything that looks like code — identifiers, syntax)
- Proper nouns, brand names, numbers, units
- URLs

### The desktop bubble — redesigned

Today: bubble → click → flat file-picker list. The picker is unusable hands-free and breaks the whole point.

**New bubble behavior:**

1. **Context-aware default.** Deen Notes window is foreground with a canvas open? `Hey Deen` routes straight there, no picker.
2. **Picker is for desk mode only.** When the user explicitly clicks the bubble (not voice), it pops a **pinboard snapshot** — a mini version of the home canvas — for visual recognition + click selection. Plus a sticky "Quick Inbox" target at the top.
3. **Voice routing handles hands-free entirely.** No picker UI is ever shown during a voice capture.
4. **Bubble stays minimal and hover-reveal.** (Consistent with Abed's stated preference: floating bubble small, ambient, no persistent labels.)

### Quick Inbox — the killer fallback

A permanent, always-there note titled "Quick Inbox." No structure. Voice captures with no clear destination land here. Captures while driving/cooking pile up here without thought.

Later (at the desk), the AI can suggest: *"These 7 inbox cards look like they belong in your 'Recipes' note — move them?"* One click sorts a week of driving captures. This pattern lets the user defer all routing decisions to a moment when their hands are free.

## AI model stack

Four jobs, four model choices. Global rule: **quality where the user notices, cheap where they don't.**

| Job | Model | Why |
|---|---|---|
| **Transcription** | **Deepgram Nova-3** (streaming, ~$0.0043/min) | Real-world noise (car, kitchen), streaming so words appear as spoken, accent-resilient. |
| **Transcription fallback** | Whisper large-v3, self-hosted via `faster-whisper` | Offline mode (no internet while driving in a tunnel). Already aligned with existing Python service architecture. |
| **Voice routing** | Local embedding similarity → Claude Haiku 4.5 for ambiguity | 95% of "in Sapiens" matches are unambiguous and resolvable locally with no API call. Haiku 4.5 (~$0.0001/call) handles the disambiguation cases. |
| **Structure-aware placement** | **Claude Sonnet 4.5+** (~$0.005/call) | The judgment moment. Wrong placement = user stops trusting the feature = feature fails. Anthropic Sonnet is most reliably calibrated for nuanced "does this go in frame X or Y" decisions. |
| **TTS confirmations** | **Kokoro TTS** (Apache 2.0, ~250 MB, runs local on CPU) | Free, offline, pleasant, sub-second latency. Fits the existing Python service architecture. |

Estimated cost: ~$0.005–0.010 per capture; ~100 captures/day = ~$15–30/month at heavy usage. DeepSeek V3.1 swap on the placement tier could cut ~70% if A/B testing shows acceptable quality — defer that experiment to post-launch.

**Verification step before integration:** query `context7` MCP for current pricing and availability of all four models — pricing in this doc is a mid-2026 estimate and the model landscape moves fast.

## Migration from current app

Existing notes are stored as a single `content` field (markdown text) in SQLite, with optional `group_id`, plus an overlay layer in localStorage for pinned/trashed/userTags/titleOverride.

**Migration approach (one-time, on first launch of the redesigned app):**

1. **Each existing note becomes an inner canvas with one large text card** containing the full original markdown content, positioned at the top-left of the canvas. Lossless — no rewriting, no AI parsing. User can split it manually into frames/cards later, or never; either is fine.
2. **Each existing group becomes a frame on the outer pinboard canvas.** Notes are laid out inside their group's frame in a default grid. Ungrouped notes go to the canvas floor outside any frame.
3. **Quick Inbox is created** if it doesn't exist.
4. **Overlay state (pinned, tags, archive) carries over** as card-level metadata on the outer canvas (pinned cards float to the top of the visual layout; tags become filter chips; archived cards live in an Archive overlay).

**Opt-in "structurize" pass (post-launch, not v1):** offer to re-parse a single existing note with the placement model — split it into frames and cards based on its existing headings. Runs on user request per-note, not globally.

## What stays from the current app

- **Hey Deen wake-word** detection (Python service, already working).
- **`Ctrl+Shift+D` capture hotkey.**
- **Push-to-talk** (`Ctrl+Space` for AI rewrite, `Shift+Ctrl+Space` for verbatim).
- **Markdown rendering pipeline** (now lives inside each text card; the heavy lifting in `NoteView.jsx` moves into a `TextCard` component).
- **Mermaid + chart + KaTeX support** — preserved inside text cards.
- **Tags, pinning, archive** — semantics preserved, surface changes to fit the canvas model.
- **Settings, sanitization schema, window chrome.**

## What goes from the current app

- **`Home` grid view** — replaced by the outer canvas.
- **`NoteView` single-textarea editor** — replaced by the inner canvas.
- **The flat file-picker bubble flow** — replaced by voice routing + pinboard-snapshot picker.
- **The two-mode dictation picker** — replaced by single-mode-with-modifiers.
- **`GroupTree` / `MoveToGroupModal`** — groups become frames on the outer canvas; modals become drag-and-drop.

## Out of scope (deferred to v1.1 or beyond)

Explicitly NOT in v1 — flagged here so we don't accidentally pull them in:

- Toolbar specifics inside the canvas (what buttons, where, hotkeys for each tool).
- In-canvas search (Cmd+F → highlight matching cards across frames).
- Export (canvas → PDF, canvas → markdown, canvas → image).
- Multi-device sync.
- Mobile app.
- Offline mode beyond the offline-TTS guarantee.
- "Scale up" structure-aware placement (option C from brainstorm) — AI proposing new frames or rearranging existing cards. v1 only places into existing frames.
- "Preview before place" mode (option D from brainstorm) — ghost preview the user can confirm. Defer; the toast + undo pattern should be sufficient.
- DeepSeek/cheaper-model A/B test on the placement tier.
- The inner-canvas thumbnail on outer-canvas cards (visual recognition aid) — defer if expensive.
- Auto-cleanup AI suggestions for Quick Inbox ("these 7 look like Recipes notes — move?").

## Open technical decisions (resolve during writing-plans)

These are real choices that need a call but are detailed enough to live in the implementation plan, not the design spec:

- **Canvas rendering engine.** Likely candidates: `tldraw` (polished UX, whiteboard-flavored, ~MIT) or `React Flow` / `@xyflow/react` (graph-focused, lighter, MIT). React Flow is probably the better fit for the "cards + frames + connectors, no freehand" constraint — verify during writing-plans.
- **Storage layer.** Current architecture is SQLite-local + Python service. User-global preference (CLAUDE.md) is Convex for new projects, but this is an existing local-first desktop app. v1 recommendation: **keep current SQLite + Python architecture** — the redesign is product-surface, not storage-layer. Schema evolves (notes get `canvas_state` JSON; new tables for `frames`, `connectors`, `cards`). Convex sync is a separate decision worth its own brainstorm.
- **How the AI receives canvas context.** Pass the canvas as a flat JSON snapshot (frames, cards, connectors) on every placement call. Token cost is bounded by canvas size; large canvases (>200 cards) may need a "summarize first" pre-pass.
- **Card content storage.** Each text card stores its markdown content + position/size/rotation. Per-card history? Defer.
- **Connection-line semantics on the outer pinboard.** v1 = free-form lines, no types. Inner canvas connectors are typed (`supports`, `contradicts`, etc.). Revisit if user wants types at outer level later.

## Success criteria

The redesign is working if:

1. Abed prefers using Deen Notes over Notion / Google Docs for personal notes within the first week of having it.
2. Voice capture while driving (hands-free) routes to the correct note ≥90% of the time without intervention.
3. Structure-aware placement lands the card in the right frame on the first try ≥80% of the time on canvases with ≥3 frames. (Toast + undo handles the rest.)
4. Existing notes migrate losslessly with zero markdown content lost.
5. The redesigned app launches in under 2 seconds (same target as today) and the inner canvas renders smoothly with 100+ cards on a modest laptop.

## What's left to brainstorm later (not v1 blockers)

These are real follow-ups that came up but weren't core to the architecture:

- Toolbar design inside the canvas — what tools, what hotkeys, what's always-visible vs. command-palette.
- Canvas search — full-text across all notes' cards, including jumping to the right card on the right canvas.
- Export formats — markdown round-trip, PDF for sharing, image for screenshots.
- Multi-device sync — Convex migration if/when desired.
- Mobile capture — a minimal mobile app that's just "Hey Deen → adds to Quick Inbox," no canvas editing.
