// @ts-check
/**
 * Shared canvas typedefs for the Deen Notes canvas redesign.
 *
 * Every sub-project (1, 2, 3, 5, 6) imports types from here.
 *
 * Rule: this file is additive-only. Never rename or remove a field —
 * bump `schemaVersion` in canvas state and write a migration in
 * `src/lib/canvas/migrate.js` instead. See
 * `docs/superpowers/decisions/2026-05-24-canvas-state-serialization.md`.
 *
 * This file has no runtime code; importing it has zero cost.
 */

/**
 * @typedef {{ x: number, y: number }} CanvasPosition
 */

/**
 * @typedef {{ w: number, h: number }} CanvasSize
 */

/**
 * @typedef {{ x: number, y: number, zoom: number }} CanvasViewport
 */

/**
 * @typedef {'supports' | 'contradicts' | 'see-also' | 'causes' | 'example-of' | 'free'} ConnectorKind
 *  `free` is reserved for the outer pinboard (no semantic type at v1, per spec).
 */

/**
 * @typedef {Object} TextCardData
 * @property {string} markdown - Full markdown body, rendered via the existing react-markdown pipeline.
 * @property {'ai-rewrite' | 'verbatim'} [mode] - Capture mode of origin, if dictated. Optional.
 * @property {string} [originalTranscript] - Verbatim audio transcript, kept for per-card mode-flip
 *   re-rewriting (spec: "re-opening a captured card lets the user flip its mode").
 */

/**
 * @typedef {Object} MediaCardData
 * @property {'image' | 'video' | 'audio' | 'file'} kind
 * @property {string} src - Filesystem URL under app.getPath('userData') OR remote URL.
 * @property {string} [alt] - Alt text / caption.
 * @property {string} [mimeType]
 */

/**
 * @typedef {Object} LinkCardData
 * @property {string} url
 * @property {string} [title]
 * @property {string} [description]
 * @property {string} [faviconUrl]
 * @property {string} [previewImageUrl]
 * @property {string} [fetchedAt] - ISO timestamp when the OG preview was fetched.
 */

/**
 * A draggable card inside an inner canvas (one note's contents).
 *
 * @typedef {Object} Card
 * @property {string} id - From `cardId()`.
 * @property {'text' | 'media' | 'link'} type
 * @property {CanvasPosition} position
 * @property {CanvasSize} size
 * @property {number} rotation - Degrees. 0 unless user rotates.
 * @property {string | null} frameId - Parent frame id, null if free-floating on the canvas.
 * @property {TextCardData | MediaCardData | LinkCardData} data
 */

/**
 * A labeled region that visually clusters cards. Cards with `frameId === frame.id`
 * are children — they move with the frame.
 *
 * @typedef {Object} Frame
 * @property {string} id - From `frameId()`.
 * @property {string} label
 * @property {CanvasPosition} position
 * @property {CanvasSize} size
 * @property {boolean} isAutoLooseIdeas - True for the "Loose ideas" auto-frame created by
 *   Sub-project 6 on uncertain placement. The frame is hidden from the UI when it has no
 *   children. Only one isAutoLooseIdeas frame per canvas.
 */

/**
 * A typed arrow between two cards.
 *
 * @typedef {Object} Connector
 * @property {string} id - From `connectorId()`.
 * @property {string} sourceCardId
 * @property {string} targetCardId
 * @property {ConnectorKind} kind
 * @property {string} label - Free-text label. Empty string is valid.
 */

/**
 * The full inner-canvas JSON blob stored in `notes.canvas_state`.
 *
 * @typedef {Object} InnerCanvasState
 * @property {number} schemaVersion - Current: 1. Bump on incompatible shape changes.
 * @property {Card[]} cards
 * @property {Frame[]} frames
 * @property {Connector[]} connectors
 * @property {CanvasViewport} viewport - Last-saved viewport so reopening a note feels stable.
 */

/**
 * A note represented as a card on the outer pinboard. The note's actual contents
 * live in its own `InnerCanvasState`; this is just the outer-canvas affordance.
 *
 * @typedef {Object} NoteCard
 * @property {string} id - From `noteCardId()`.
 * @property {string | number} noteId - Foreign key into the notes table.
 *   The current SQLite-backed implementation stores notes with UUID string PKs
 *   (`str(uuid.uuid4())`), so most consumers will see a string here. The union
 *   keeps the door open for the numeric-id world the serialization doc example
 *   (`docs/superpowers/decisions/2026-05-24-canvas-state-serialization.md`)
 *   imagined. JSDoc-only widening — no schema change.
 * @property {CanvasPosition} position
 * @property {CanvasSize} size
 * @property {number} rotation
 * @property {string | null} frameId - Parent outer-canvas frame, null if free.
 * @property {boolean} pinned
 * @property {string[]} tags
 * @property {boolean} archived
 */

/**
 * The full outer-canvas JSON blob stored in `outer_canvas.state` (singleton row).
 *
 * @typedef {Object} OuterCanvasState
 * @property {number} schemaVersion
 * @property {NoteCard[]} noteCards
 * @property {Frame[]} frames - Same shape as inner-canvas frames; reused intentionally.
 * @property {Connector[]} connectors - Outer connectors are `kind: 'free'` only at v1 per spec.
 * @property {CanvasViewport} viewport
 */

export {}; // ensure ES module; no runtime exports
