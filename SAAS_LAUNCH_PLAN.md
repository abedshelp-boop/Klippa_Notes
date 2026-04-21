# Deen-Notes — SaaS Launch Plan

_Draft: 2026-04-20 · Owner: Abed · Status: planning, not started_

## North star

Turn the current local-only Electron + Python prototype into a paid SaaS where:

- Users sign up with Google/Apple, download a signed Electron app, and talk to it.
- Transcription runs on **our** OpenAI credentials, paid for by **their** monthly subscription — they never enter an API key.
- Notes sync to the cloud; users can open the same library on another machine.
- The website is where they sign up, pay, and download the installer.

If in six months this doc and the code have drifted, **trust the code, update this doc**.

---

## Current state (Phase 0)

- **Capture**: Electron window + bubble + Python FastAPI at `localhost:8765`.
- **Wake word**: Porcupine (`python-service/wake_word.py`) — local.
- **Transcription**: Whisper, billed to the _user's_ OpenAI key.
- **Storage**: SQLite (`noter.db`, `klippa.db`) on the user's machine.
- **Client state** (pin / trash / user tags / renames): `localStorage` overlay in [useNoteOverlay.js](src/hooks/useNoteOverlay.js).
- **Auth**: none. **Billing**: none. **Multi-device sync**: none.

---

## Target architecture

```
┌─────────────────────────────────────────────┐          ┌──────────────────────┐
│  Electron app (user's machine)              │          │  deen-notes.app      │
│  ─ React UI (current codebase)              │          │  (Next.js on Vercel) │
│  ─ Python audio capture (wake word only)    │          │  ─ Landing / pricing │
│  ─ Uploads audio blob + auth token          │          │  ─ Signup / login    │
└──────────────────┬──────────────────────────┘          │  ─ Account dashboard │
                   │                                     │  ─ Download links    │
                   │ HTTPS (Clerk JWT)                   └──────┬───────────────┘
                   ▼                                            │
┌────────────────────────────────────────────────────────────────▼──────────────┐
│  Convex                                                                        │
│  ─ tables: users, notes, note_overlay, usage, subscription                     │
│  ─ reactive queries drive UI in both Electron and web                          │
│  ─ actions: transcribe(audio)  ← calls OpenAI with OWNER's key                 │
│  ─ actions: handle_polar_webhook, handle_clerk_webhook                         │
│  ─ http: authenticated upload endpoint                                         │
└──┬─────────────────┬─────────────────┬────────────────────────┬───────────────┘
   │                 │                 │                        │
   ▼                 ▼                 ▼                        ▼
┌─────────┐   ┌──────────────┐   ┌──────────┐          ┌─────────────────┐
│ Clerk   │   │ Polar.sh     │   │ Resend   │          │ OpenAI Whisper  │
│ (auth + │   │ (subs, MoR,  │   │ (tx      │          │ (owner's key)   │
│ OAuth)  │   │  tax, billing│   │ email)   │          │                 │
│         │   │  portal)     │   │          │          │                 │
└─────────┘   └──────────────┘   └──────────┘          └─────────────────┘
```

**Rule of thumb**: Electron captures and plays back. Convex is the source of truth. Clerk gates access. Polar gates plan limits. Website is the storefront.

---

## Stack picks

| Concern | Tool | Why this, not that |
|---|---|---|
| **DB + realtime + server fns** | **Convex** | Reactive queries = free multi-device sync. Stated default in `~/.claude/CLAUDE.md`. |
| **Auth / OAuth** | **Clerk** | User picked Clerk over Convex Auth for polish and roadmap (orgs/teams later). Clerk has first-party Convex integration. |
| **Payments** | **Polar.sh** | Merchant-of-record → they handle VAT/sales-tax/payouts. Stated default. |
| **Transactional email** | **Resend** | Clean API, React Email templates, generous free tier. |
| **Marketing + account site** | **Next.js on Vercel** | Standard; Vercel + Convex work well together; free Hobby tier. |
| **Transcription** | OpenAI Whisper API | Already integrated. Called from a Convex action with owner's key. |
| **Error tracking** | Sentry | Free tier fine for months. |
| **Product analytics** | PostHog | Self-hostable if needed; generous free tier. |
| **Installer distribution** | GitHub Releases + electron-updater | Free, reliable; switch to S3/CloudFront if traffic spikes. |

**Not picking yet**: log aggregation, status page, support tooling, CDN for audio blobs (Convex storage is fine initially).

---

## Pricing model (tentative)

Subscription-only. No BYOK. No per-minute credit packs in v1.

| Tier | Price | Transcription limit | Who it's for |
|---|---|---|---|
| **Free** | $0 | 30 min / month | Trial. 1 week history, then capped. |
| **Pro** | $12 / mo | 20 hours / month | Main target — heavy knowledge worker. |
| **Studio** | $29 / mo | Unlimited (fair-use: 80 hrs soft cap) | Journalists, interviewers, researchers. |

Annual plans at ~17% off (2 months free) later.

**Overage policy**: when a user hits the limit, new captures fail with a clear upsell card — we do **not** silently charge overages in v1.

---

## Phased migration plan

Each phase is a working app at the end. Don't combine phases.

### Phase 1 — Convex data layer (no auth yet)

**Goal**: move notes and the local overlay off SQLite / localStorage into Convex, still running as a single-user local setup.

1. `npm create convex@latest` in the project; set up `convex/` folder.
2. Schema: `notes { userId, title, content, tags, source, createdAt, updatedAt, videoUrl }`, `noteOverlay { noteId, userId, pinned, trashed, userTags, titleOverride, updatedAt }`.
3. Replace [`useNotes`](src/hooks/useNotes.js) with Convex `useQuery(api.notes.list)`. Drop the REST retry loop — Convex's reactivity handles it.
4. Replace [`useNoteOverlay`](src/hooks/useNoteOverlay.js) with Convex mutations. `localStorage` becomes a one-time migration step (read old overlay on first boot, write to Convex, delete).
5. Delete the WebSocket ([`useWebSocket`](src/hooks/useWebSocket.js)) — new notes arrive via Convex subscription.
6. Python service keeps running locally, but now it calls a Convex HTTP endpoint to upsert notes instead of writing to SQLite.

Single hardcoded `userId` for now. Backend shape is the real work here.

### Phase 2 — Clerk auth + Electron handoff

**Goal**: real users, no payments yet.

1. Add Clerk app; configure Google + Apple + magic-link providers.
2. Hook Clerk ↔ Convex per Clerk's Convex integration doc (JWT template + `ctx.auth.getUserIdentity()`).
3. **Electron auth handoff** (the tricky bit):
   - Register a custom protocol handler: `deen-notes://auth/callback`.
   - On "Sign in", Electron opens the system browser to `https://deen-notes.app/sign-in?callback=deen-notes://auth/callback`.
   - After Clerk sign-in on the web, we call `window.location.href = 'deen-notes://auth/callback?token=<clerk-session-token>'`.
   - Electron's `app.setAsDefaultProtocolClient()` + `open-url` / `second-instance` events catch it and store the token.
   - Subsequent Convex calls attach the token.
4. Migrate single-user Convex data to the first authenticated user's account (one-shot script).
5. Sign-out button in sidebar footer.

### Phase 3 — Marketing + account website

**Goal**: the place people land, pay, and get the installer.

Routes:
- `/` — landing (hero, "Say Hey Deen" demo video, 3 pricing cards).
- `/pricing` — full feature matrix.
- `/sign-in`, `/sign-up` — Clerk-hosted.
- `/account` — dashboard: plan, usage (minutes this month), download links, manage-subscription button (deep-links into Polar portal).
- `/download/mac`, `/download/windows` — signed redirects to latest release.
- `/privacy`, `/terms`, `/dpa` — legal.
- `/changelog` — optional but nice.

Stack: Next.js 15 App Router on Vercel, Tailwind + a small design system that mirrors `src/index.css` tokens (same Instrument Serif + Geist + JetBrains Mono feel).

### Phase 4 — Server-side transcription

**Goal**: kill BYOK. All Whisper calls are owner-billed.

1. Delete OpenAI key field from the Electron Settings modal ([src/components/Settings.jsx](src/components/Settings.jsx)). Keep buffer length + arabize.
2. Remove Whisper call from Python service. Python now only produces a compressed audio blob (opus, mono, 16 kHz).
3. Convex action `transcribeAudio(fileId)`:
   - Reads audio from Convex storage.
   - Calls `openai.audio.transcriptions.create({ model: 'whisper-1', ... })` with `process.env.OPENAI_API_KEY` (owner's key, set in Convex dashboard).
   - Pipes the transcript into the note-generator LLM call (also owner-billed).
   - Inserts the finished note into Convex.
4. Upload path: Electron `fetch()`s the Convex HTTP upload URL with Clerk JWT → gets a storage ID → calls the transcribe action with that ID.
5. Enforce 10-minute cap per clip on the server for v1.

### Phase 5 — Polar.sh + plan enforcement

**Goal**: billing + usage metering.

1. Polar products: Free ($0), Pro ($12/mo), Studio ($29/mo). Annual variants.
2. Webhook from Polar → Convex action → upsert `subscription { userId, tier, renewsAt, polarCustomerId, polarSubscriptionId }`.
3. `usage` table: `{ userId, yearMonth, secondsTranscribed }`. Increment inside the transcribe action.
4. Before transcription, check `usage` vs `subscription.tier` limit. If over, return a typed error — UI shows upsell card, no charge.
5. "Manage subscription" button opens `polar.customerPortalUrl(customerId)` in the system browser.
6. Dunning: Polar emails on failed payments; downgrade to Free after grace period.

### Phase 6 — Polish & distribution

**Goal**: shippable to strangers.

1. **Code signing**:
   - macOS: Apple Developer Program ($99/yr), Developer ID cert, notarize in CI.
   - Windows: EV code-signing cert ($300–400/yr) — avoids SmartScreen warnings. Standard cert is cheaper ($80–250) but triggers warnings until reputation builds.
2. **Auto-update**: `electron-updater` reading from GitHub Releases. Electron checks on boot and prompts to install on next launch.
3. **Email** (Resend):
   - Welcome email on first sign-in.
   - Receipt / invoice on each Polar charge (Polar also sends, but our branded one feels better).
   - Monthly usage digest.
4. **Observability**:
   - Sentry in Electron renderer + main + Convex functions.
   - PostHog in website + Electron (capture anonymous funnel until auth, then identify).
5. **Legal**:
   - Privacy policy (explicit: audio blobs deleted within 24h of transcription; transcripts retained; no training on user data).
   - Terms of service.
   - Cookie banner if EU traffic non-trivial.
   - DPA template for any B2B inquiries.
6. **Support**: support@deen-notes.app forwarding to Abed. In-app "Report a bug" button linking to same email with diagnostic payload attached.

### Phase 7 — Soft launch

1. Product Hunt scheduled launch.
2. Referral codes (Polar supports discount codes) — seed with 20% off for first 100 users.
3. Twitter / Reddit / Hacker News posts with the demo video.
4. Watch the first 50 signups closely. Fix the three things they all hit.

---

## Electron-specific landmines

- **Protocol handler on Windows**: must be registered per-install (MSI/NSIS postinstall step). Fragile across updates.
- **Permissions**: mic access prompts differ on macOS (TCC) and Windows. Detect and surface in onboarding.
- **Offline**: if Convex is unreachable, Electron should still record and queue uploads. Implement a local outbox table.
- **Auto-update + code signing**: if cert expires, every installed app silently fails to update. Calendar reminder annually.
- **Wake word always-on** = always-on mic = battery drain. Offer a toggle and "sleep after N minutes idle" option.

---

## Decisions locked

- **Subscription-only, owner-paid credentials.** No BYOK.
- **Auth: Clerk.** Not Convex Auth.
- **Backend: Convex.** Not Supabase, not custom.
- **Payments: Polar.sh.** Not Stripe.
- **Server-side transcription.** Client-side was ruled out because we can't bill for it.
- **No E2E encryption in v1.** It conflicts with server-side search and note generation. Revisit in v2 if users ask.
- **Bubble visuals stay as-is.** The overlay that sits on the desktop is not changing with the SaaS pivot.

## Open decisions (to resolve before Phase 1)

- **Electron vs web-only for reading notes?** Decision: keep Electron as primary, add a minimal read-only web viewer later.
- **Chrome extension pricing?** Ships as part of Pro/Studio, not priced separately.
- **Which OAuth providers at launch?** Suggest Google + Apple + email magic link. Skip GitHub (wrong audience).
- **Free tier history cap?** 7 days or 30 days? 7 drives conversions faster, 30 feels more generous. Suggest 7 and A/B.
- **Pricing in USD only or local currency?** Polar supports multi-currency; start USD, turn on after 100 paying users.

---

## Budget estimate

**Fixed annual**: ~$500/yr
- Apple Developer: $99
- Windows code-signing cert: $300 (EV) or $100 (standard)
- Domain (`deen-notes.app` or similar): $20
- Misc (email domain, legal templates): ~$80

**Fixed monthly at zero users**: ~$0
- Convex, Clerk, Polar, Resend, Vercel, Sentry, PostHog — all free tiers.

**Per paying user** (rough, at average Pro usage of 10 hrs/month):
- Whisper API: 10 hrs × 60 min × $0.006 = **$3.60**
- Note-generation LLM (sonnet, ~3k tokens/note × 40 notes): ~$0.15
- Polar + Stripe fees: ~5% of $12 = $0.60
- Convex bandwidth + storage: rounding error
- **≈ $4.35 cost per Pro user → ≈ $7.65 gross margin (~64%).**

Studio users at "unlimited" (soft 80 hrs) worst-case cost ~$29 — same as price — so Studio is a loss leader at fair-use max. Fine: few users hit the cap, and it's a positioning tool.

---

## First thing to build when work starts

Phase 1, task 1: stand up Convex, migrate the notes table. Don't bundle it with auth. Don't bundle it with transcription. One moving piece at a time.

Reference for the current data shape: [python-service/database.py](python-service/database.py), [src/hooks/useNotes.js](src/hooks/useNotes.js), [src/hooks/useNoteOverlay.js](src/hooks/useNoteOverlay.js).
