"""
AI client for Deen-Notes.

- Transcription: smart-routed between AssemblyAI Universal-3 Pro (for English
  audio — keeps Islamic-vocabulary Keyterms Prompting + speaker diarization)
  and OpenAI gpt-4o-mini-transcribe (for Arabic and other non-English content,
  since Universal-3 Pro only supports EN/ES/DE/FR/PT/IT). A short whisper-1
  probe on the system audio picks the engine.
- Note generation: OpenAI GPT-4o-mini with the Deen-Notes system prompt.
"""
import io
import json
import os

import assemblyai as aai
import soundfile as sf
from assemblyai import AssemblyAIError
from openai import APIError as OpenAIAPIError
from openai import OpenAI

from collections import Counter

from config import (
    ASSEMBLYAI_API_KEY,
    LANGUAGE_PROBE_DURATION_SEC,
    LANGUAGE_PROBE_OFFSETS_SEC,
    OPENAI_API_KEY,
    SMART_ROUTING_ENABLED,
)
from debug import debug
from keyterms import get_keyterms


# ─── Client handles ──────────────────────────────────────────────────────────

_openai_client: OpenAI | None = None
_aai_configured_key: str | None = None


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _ensure_aai_configured() -> bool:
    """Configure the AssemblyAI SDK with the current key. Returns True if
    an AssemblyAI key is available and the SDK is ready."""
    global _aai_configured_key
    if not ASSEMBLYAI_API_KEY:
        return False
    if _aai_configured_key != ASSEMBLYAI_API_KEY:
        aai.settings.api_key = ASSEMBLYAI_API_KEY
        _aai_configured_key = ASSEMBLYAI_API_KEY
    return True


# ─── Transcription ───────────────────────────────────────────────────────────

# Universal-3 Pro supports up to 1000 keyterms. If universal-2 is included in
# the fallback list, the keyterm cap drops to 200 — so we use universal-3-pro
# alone and rely on the OpenAI fallback path below if it's unavailable.
AAI_SPEECH_MODELS = ["universal-3-pro"]
OPENAI_FALLBACK_MODEL = "gpt-4o-mini-transcribe"


def _aai_transcribe(wav_bytes: bytes, with_speakers: bool) -> str:
    """Transcribe via AssemblyAI Universal-3 Pro with Keyterms Prompting.
    If with_speakers=True, enables diarization and returns a speaker-labeled
    transcript ('[Speaker A]: ...' per utterance) so the LLM can attribute
    question vs. answer correctly.
    """
    config = aai.TranscriptionConfig(
        speech_models=AAI_SPEECH_MODELS,
        keyterms_prompt=get_keyterms(),
        language_code="en",
        punctuate=True,
        format_text=True,
        speaker_labels=with_speakers,
    )

    audio = io.BytesIO(wav_bytes)
    audio.name = "audio.wav"  # SDK uses the filename hint for content-type

    transcript = aai.Transcriber(config=config).transcribe(audio)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI transcription failed: {transcript.error}")

    if with_speakers and transcript.utterances:
        return "\n".join(
            f"[Speaker {u.speaker}]: {u.text}" for u in transcript.utterances
        ).strip()

    return (transcript.text or "").strip()


def _openai_transcribe(wav_bytes: bytes) -> str:
    """Transcribe via OpenAI gpt-4o-mini-transcribe. Handles all languages
    (including Arabic) natively, so it's used both as the AssemblyAI fallback
    and as the primary path for non-English system audio.

    The `prompt=` arg is a belt-and-suspenders defense: VAD upstream is
    supposed to strip silence before the audio ever reaches Whisper, but if
    any quiet tail slips through, this instruction reduces the chance of
    Whisper filling it with hallucinated training-data phrases ("And the
    one who believed said...", "Subscribe to my channel", etc.).
    """
    client = _get_openai()
    audio_file = io.BytesIO(wav_bytes)
    audio_file.name = "audio.wav"
    response = client.audio.transcriptions.create(
        model=OPENAI_FALLBACK_MODEL,
        file=audio_file,
        prompt=(
            "Transcribe only the words actually spoken in the audio. "
            "If there is no speech, return an empty string. "
            "Do not add filler, religious phrases, or sign-off text."
        ),
    )
    return response.text.strip()


# ─── Language probe ──────────────────────────────────────────────────────────

# Whisper sometimes returns full language names ("english"), sometimes ISO
# codes ("en"). Normalize common Whisper outputs; anything unmapped falls
# through as-is via .get(raw, raw).
_LANG_NAME_TO_CODE = {
    "english": "en",
    "arabic": "ar",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "italian": "it",
    "portuguese": "pt",
}


def _wav_sample(wav_bytes: bytes, offset_sec: float, duration_sec: float) -> bytes:
    """Return a WAV slice [offset_sec, offset_sec + duration_sec] re-encoded
    as PCM_16. Falls back to the full clip if the offset runs past the end."""
    data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    start = int(offset_sec * sr)
    end = min(len(data), start + int(duration_sec * sr))
    if start >= len(data):
        start, end = 0, len(data)
    buf = io.BytesIO()
    sf.write(buf, data[start:end], sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _wav_duration_sec(wav_bytes: bytes) -> float:
    info = sf.info(io.BytesIO(wav_bytes))
    return info.frames / info.samplerate


def _probe_one(wav_bytes: bytes, offset_sec: float) -> str | None:
    """Run a single whisper-1 probe at the given offset. Returns the detected
    ISO-639-1 code or None if the probe failed."""
    try:
        sample = _wav_sample(wav_bytes, offset_sec, LANGUAGE_PROBE_DURATION_SEC)
        f = io.BytesIO(sample)
        f.name = "probe.wav"
        resp = _get_openai().audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
        )
        raw = (getattr(resp, "language", "") or "").lower().strip()
        return _LANG_NAME_TO_CODE.get(raw, raw) or None
    except (OSError, RuntimeError, ValueError, OpenAIAPIError) as e:
        debug.warn(
            "Deen",
            "language probe failed",
            {"offset_sec": offset_sec, "err": str(e)},
        )
        return None


def _detect_language(wav_bytes: bytes) -> str | None:
    """Probe the audio at multiple windows via OpenAI whisper-1 and return the
    majority-voted ISO-639-1 code ("en", "ar", ...), or None if every probe
    failed. A single-window probe can misclassify prosody-heavy audio — Quran
    recitation with sustained vowels gets labeled "en", which then routes to
    AssemblyAI (locked to English) and produces phonetic gibberish.

    Short-clip guard: if the (VAD-trimmed) audio is shorter than one probe
    window, all three configured offsets dedupe to 0.0 and the majority-vote
    degenerates to a single sample. Skip the multi-offset dance and just
    probe the whole clip once — same info, fewer API calls.
    """
    total_sec = _wav_duration_sec(wav_bytes)

    if total_sec < LANGUAGE_PROBE_DURATION_SEC:
        code = _probe_one(wav_bytes, 0.0)
        if code:
            debug.log(
                "Deen",
                "language probe (short-clip)",
                {"total_sec": total_sec, "code": code},
            )
        return code

    seen: set[float] = set()
    results: list[str] = []

    for offset in LANGUAGE_PROBE_OFFSETS_SEC:
        # _wav_sample falls back to offset=0 for out-of-range offsets — dedupe
        # those so we don't waste API calls on identical windows.
        effective = offset if offset < total_sec else 0.0
        if effective in seen:
            continue
        seen.add(effective)

        code = _probe_one(wav_bytes, offset)
        if code:
            results.append(code)

    if not results:
        return None

    winner, _ = Counter(results).most_common(1)[0]
    debug.log(
        "Deen",
        "language probe votes",
        {"votes": results, "winner": winner},
    )
    return winner


def transcribe_audio(wav_bytes: bytes, with_speakers: bool = False) -> str:
    """Transcribe audio with smart engine selection.

    - Command audio (`with_speakers=False`): always OpenAI Whisper — short,
      single-speaker, handles any language including Arabic.
    - System audio (`with_speakers=True`): multi-window whisper-1 probe. Only
      route to AssemblyAI when the probe is CONFIDENT the audio is English;
      fall back to OpenAI Whisper for anything else (non-English, ambiguous,
      or probe failure). AssemblyAI is locked to `language_code="en"`, so
      routing non-English audio there produces phonetic gibberish — safer
      default is Whisper, which handles every language natively.
      Set SMART_ROUTING_ENABLED=false to skip probing and force AssemblyAI.
    """
    if not with_speakers:
        return _openai_transcribe(wav_bytes)

    if not _ensure_aai_configured():
        debug.warn("Deen", "ASSEMBLYAI_API_KEY missing, using OpenAI fallback")
        return _openai_transcribe(wav_bytes)

    if SMART_ROUTING_ENABLED:
        lang = _detect_language(wav_bytes)
        use_assemblyai = (lang == "en")
        if use_assemblyai:
            debug.log("Deen", "language probe: 'en' — routing to AssemblyAI")
        else:
            debug.log(
                "Deen",
                "language probe — routing to OpenAI Whisper",
                {"lang": lang},
            )
    else:
        # Smart routing off: preserve legacy force-AAI behavior as an escape hatch.
        use_assemblyai = True

    if use_assemblyai:
        try:
            return _aai_transcribe(wav_bytes, with_speakers=with_speakers)
        except (OSError, RuntimeError, ValueError, AssemblyAIError) as e:
            debug.warn(
                "Deen",
                "AssemblyAI transcribe failed, falling back to OpenAI",
                e,
            )

    return _openai_transcribe(wav_bytes)


# ─── Note generation ─────────────────────────────────────────────────────────

def translate_command_to_english(text: str) -> str | None:
    """Translate a short 'Hey Deen' voice-assistant instruction to English
    via gpt-4o-mini. Intended for commands that arrive in Arabic or any
    non-English language — the main `generate_note` model then receives
    both the original and this translation so the instruction is always
    interpretable as an instruction, not echoed back as transcript text.

    Returns the English translation on success, or None on failure. On
    None, the caller should still pass the original command through with
    a "translation unavailable" note; the main prompt has a rule for
    interpreting foreign-language commands directly as a fallback.
    """
    if not text or not text.strip():
        return None
    try:
        client = _get_openai()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You translate short voice-assistant instructions to "
                    "English. The input is a user's spoken command to a "
                    "note-taking app, typically one short sentence, often "
                    "in Arabic. Output ONLY the English translation as a "
                    "single imperative sentence — no quotes, no commentary, "
                    "no prefix, no explanation. Preserve the imperative tone."
                )},
                {"role": "user", "content": text.strip()},
            ],
            temperature=0.0,
            max_tokens=200,
        )
        out = (resp.choices[0].message.content or "").strip()
        return out or None
    except (OSError, RuntimeError, ValueError, OpenAIAPIError) as e:
        debug.warn("Deen", "command translation failed", e)
        return None


def generate_note(system_transcript: str, command_transcript: str,
                   command_lang: str = "en",
                   command_transcript_en: str | None = None,
                   target_language: str = "auto",
                   target_language_label: str = "Global") -> dict:
    """
    Given a transcript of the system audio and the user's voice command,
    generate a beautifully structured Markdown note.

    command_lang / command_transcript_en: when the user's "Hey Deen"
    instruction arrives in a non-English language, the caller should detect
    the language and pass a pre-translated English version. Both originals
    and translations are shown to the model so the instruction is always
    interpretable regardless of language.

    target_language / target_language_label: the user's app-wide output-
    language preference. "auto" preserves the system-audio-dominance rule
    (Rule 8 in the system prompt). Any other value appends an OUTPUT
    LANGUAGE OVERRIDE directive that supersedes Rule 8 while leaving the
    Quran-preservation rule (Rule 9) intact.

    Returns dict with keys: title, content, tags, source.
    """
    client = _get_openai()

    system_prompt = """You are Deen-Notes, an AI note-taking assistant. Your job is to create beautiful, well-structured Markdown notes from audio transcripts.

RULES:
1. INPUTS — the user provides two things:
   - SYSTEM AUDIO: a transcript of what was playing (podcast, lecture, video). Roughly the last 5 minutes, may contain multiple turns of conversation including questions and answers.
   - USER COMMAND: what the user asked you to note down.

2. COMMAND LANGUAGE:
   - The USER COMMAND may arrive in any language (English, Arabic, mixed). Interpret it as an instruction regardless of language.
   - The command's language does NOT determine the note's output language — Rule 8 (dominant language of SYSTEM AUDIO) governs output language.
   - If an English translation is provided alongside the original command, treat the translation as the authoritative interpretation of the user's intent; the original is present only for preservation.

3. FOLLOW THE COMMAND LITERALLY — NEGATIVE CONSTRAINT (critical):
   - Find the relevant portion(s) of the SYSTEM AUDIO TRANSCRIPT based on the command.
   - When the command asks for ONLY a specific part (e.g. "only the question", "only the answer about X", "just his point on Y"), the note MUST contain EXACTLY that part and nothing else. Do NOT include setup sentences. Do NOT include adjacent context. Do NOT continue into follow-on topics that merely seem related.
   - Err toward omission — if a sentence isn't directly part of what the user asked for, leave it out.

4. HONESTY — never fabricate to fill a slot:
   - If the command asks for content that is NOT present in the captured transcript (e.g. asks for "the answer" but no answer was given in the captured window, or asks about a topic the speaker didn't cover), state this plainly in the note's default language — for example: "_No answer recorded in this audio window._"
   - Do NOT invent content. Do NOT insert bracketed placeholder strings of any kind. Do NOT paste generic filler. If the transcript doesn't contain what was asked, say so truthfully.

5. FORMATTING & POLISH — default is polished prose:
   - DEFAULT MODE (polished): lightly clean filler words ("um", "uh", "you know", "like"), false starts, restarts, and verbal tics. Collapse spoken repetitions. Add proper punctuation and paragraph breaks for readability. Preserve meaning 1:1 — NEVER summarize, NEVER invent, NEVER add content the speaker didn't say.
   - Direct quotes inside `>` blockquotes stay STRICTLY VERBATIM — no cleanup inside blockquotes. Blockquote is the "speaker's exact words" escape hatch inside an otherwise polished note.
   - VERBATIM MODE OVERRIDE: if the USER COMMAND (or its English translation) contains any of these trigger words/phrases, switch the ENTIRE note to strict verbatim (no polish anywhere, preserve every filler and restart): `quote`, `quoted`, `exact words`, `exactly what`, `verbatim`, `word-for-word`, `word for word`, `literally`, `literal`, or their Arabic equivalents `حرفياً`, `بالحرف`, `نصاً`, `اقتبس`.
   - Islamic / scholarly content (Quran, hadith) is ALWAYS verbatim per Rule 9, regardless of polish mode.

6. SPEAKER ATTRIBUTION — command-driven:
   - The SYSTEM AUDIO transcript may contain speaker labels like `[Speaker A]:` and `[Speaker B]:` from diarization.
   - Read the USER COMMAND literally and let it decide which speaker(s) to capture. Questioner if the user asks about the question; responder if the user asks about the answer; both if the user asks about the exchange.
   - Do NOT include the speaker labels themselves in the final note content — they are metadata for you, not the reader.
   - Fallback ONLY when the command is non-directional (e.g. "take note of what was just said"): capture the most recent substantive utterance on the topic.

7. COMPLETENESS:
   - Capture the FULL relevant statement. Don't truncate a long answer just because it's long.
   - If the relevant statement appears to start mid-sentence at the beginning of the transcript, prefix the quote with `[…] `.
   - If the statement is cut off at the end of the transcript, suffix the quote with ` […]`.

8. OUTPUT LANGUAGE — CRITICAL:
   - Detect the DOMINANT language of the SYSTEM AUDIO TRANSCRIPT. That language becomes the note's default language. Write the title, section headings, bullet points, and body in that dominant language.
   - ENGLISH-DOMINANT videos (English mixed with sprinkled Arabic terms): write the note in English. Common Arabic / Islamic terms embedded in the speech — e.g. hadith, sunnah, sufi, deobandi, wahhabi, maslaha, shia, sunni, ummah, madhhab, hanbali, athari, ash'ari, maturidi, insha'Allah, sallallahu alayhi wa sallam, subhanahu wa ta'ala, imam names, book references like Sahih al-Bukhari / Musnad — must be TRANSLITERATED into Latin script and **bolded**. Do NOT switch to Arabic script for these in-flow terms.
   - ARABIC-DOMINANT videos (mostly Arabic): write the note in natural Arabic script. No transliteration. Sprinkled English words stay in English.

9. QUOTES AND RECITATIONS — preserve original language, do NOT translate or transliterate:
   - If the speaker QUOTES someone (scholar, imam, poem, saying) in a language DIFFERENT from the note's default language, preserve that quote in its ORIGINAL language and script, wrapped in "double quotation marks". Example: in an English-dominant note, an Arabic quote from an imam stays as "قال الإمام أحمد: ...".
   - QURAN — EXACT-COPY RULE (no exceptions):
     • The SYSTEM AUDIO TRANSCRIPT may already contain passages in the form `<arabic-text-with-tashkil> (Surah Name, X:Y)` or `<...> (Surah Name, X:Y-Z)`. These are PRE-VERIFIED against the official Uthmani corpus. Copy each one VERBATIM into the note — every letter, every diacritic, every bracket, and the reference — exactly as given. Do NOT re-spell, re-transliterate, swap hamza/alif/yaa variants, add/remove tashkil, or "correct" anything.
     • If the speaker recites the Quran but the transcript does NOT already contain a verified `<...> (Surah ..., X:Y)` block, OMIT the recitation entirely. Do NOT write Arabic Quran text from memory. Do NOT insert any placeholder text of any kind (no brackets, no "unverified" tags, no filler). Simply skip the recitation; if omitting would leave the note too empty, briefly state in the note's default language that the speaker recited Quran.
   - Hadith quoted verbatim from an Arabic source follows the same rule as other Arabic quotes: preserve inside "quotation marks", optionally followed by source reference (e.g. **Sahih al-Bukhari**).

10. FORMAT GUIDELINES:
    - Clear descriptive title (H1 is NOT needed — title is a separate field)
    - `##` for main sections
    - `>` blockquotes for direct quotes from the speaker
    - Bullet points for key takeaways
    - **Bold** for transliterated Arabic terms (in English notes) and key emphasis
    - *Italics* sparingly — for English book titles or non-Arabic references
    - LaTeX `$...$` (or `$$...$$` for display) for math formulas
    - Code blocks for code or technical content
    - Tables when comparing things
    - `---` for section separators when appropriate
    - RICH RENDERING (use when content fits — never force a chart when prose is clearer):
      • ` ```mermaid ` fenced blocks for flowcharts, sequence diagrams, mind maps, gantt charts, class diagrams. Keep diagrams small (≤12 nodes) so they render legibly in a desktop note. Avoid `click` handlers / HTML labels (default securityLevel='strict' strips them).
      • ` ```chart ` fenced blocks (JSON) for numeric data with 3+ datapoints. Locked spec shape:
        `{"type":"line"|"bar"|"pie"|"area","title"?:"...","data":[{"name":"Jan","revenue":100,...},...],"series":[{"key":"revenue","label":"Revenue","color":"#fbbf24"},...],"xAxis":"name"}`
        Use hex colors. xAxis defaults to "name". One JSON object per code fence.
      • Inline `<svg viewBox="0 0 W H">...</svg>` for custom small diagrams that don't fit Mermaid's grammar (labeled anatomy, custom layouts, sketches). KEEP UNDER ~4KB. NO `<script>`, NO `<foreignObject>`, NO `on*` event attributes (those get stripped by sanitizer). Use SVG attribute style only (e.g. `stroke="#fff"`), not CSS `style="..."`.

11. Return your response as JSON with exactly these keys:
    - "title": a concise, descriptive title for the note
    - "content": the full Markdown content of the note
    - "tags": an array of 2-5 relevant tags (lowercase, no spaces)
    - "source": a brief description of the source type (e.g., "Podcast", "Lecture", "Islamic Khutba", "Math Lesson")

Return ONLY valid JSON, no markdown code fences around it."""

    # OUTPUT LANGUAGE OVERRIDE — appended only when the user has picked a
    # specific language in the picker. "auto" preserves Rule 8 unchanged so
    # behavior matches what shipped before the language-selection feature.
    # The override deliberately repeats Rule 9's Quran-preservation clause
    # so a careless reader of just this block still gets it right.
    if target_language and target_language.lower() != "auto":
        lang = target_language_label
        language_directive = (
            f"\n\nOUTPUT LANGUAGE OVERRIDE (supersedes Rule 8):\n"
            f"- Write the entire note (title, headings, body, bullets) in {lang}.\n"
            f"- Translate any non-{lang} transcribed content into {lang} so the "
            f"final note reads as a single coherent {lang} document.\n"
            f"- EXCEPTIONS that stay in their original language/script even in a {lang} note:\n"
            f"  1. Proper nouns and place names.\n"
            f"  2. Technical terms with no widely-used {lang} equivalent.\n"
            f"  3. Quranic Arabic verses — Rule 9's EXACT-COPY RULE still applies. "
            f"Reproduce any pre-verified `<...> (Surah ..., X:Y)` block byte-for-byte "
            f"in Arabic script with its reference. Do NOT translate the verse itself.\n"
            f"- If the USER COMMAND is in a different language than {lang}, still produce "
            f"the note in {lang}."
        )
        system_prompt = system_prompt + language_directive

    if command_lang == "en" or not command_transcript_en:
        if command_lang == "en":
            command_block = f"USER COMMAND:\n{command_transcript}"
        else:
            command_block = (
                f"USER COMMAND (original, {command_lang}; "
                f"translation unavailable — interpret directly):\n"
                f"{command_transcript}"
            )
    else:
        command_block = (
            f"USER COMMAND (original, {command_lang}):\n{command_transcript}\n\n"
            f"USER COMMAND (English translation of the instruction; "
            f"authoritative for interpretation):\n{command_transcript_en}"
        )

    user_message = f"""SYSTEM AUDIO TRANSCRIPT:
{system_transcript}

{command_block}"""

    # Step-1 evidence-gathering diagnostic. Enable by setting
    # DEEN_DEBUG_PROMPT=1 in the environment before launching the service.
    # Dumps EXACTLY what GPT-4.1 receives + returns, so we can see whether a
    # bad note came from a bad input transcript or from model hallucination.
    if os.getenv("DEEN_DEBUG_PROMPT"):
        # Double-gated: DEEN_DEBUG_PROMPT toggles this block on/off; the
        # outer debug.log() additionally requires DEEN_DEV=1 so packaged
        # builds with DEEN_DEBUG_PROMPT alone still won't see anything
        # unless dev-mode is also set.
        debug.log("ai_client.generate_note", "━━━━━━━ LLM CALL (generate_note) ━━━━━━━")
        debug.log(
            "ai_client.generate_note",
            f"target_language={target_language!r} label={target_language_label!r}",
        )
        debug.log("ai_client.generate_note", f"command_lang={command_lang!r}")
        debug.log(
            "ai_client.generate_note",
            f"command_transcript_en={command_transcript_en!r}",
        )
        debug.log("ai_client.generate_note", "── SYSTEM PROMPT ──")
        debug.log("ai_client.generate_note", system_prompt)
        debug.log("ai_client.generate_note", "── USER MESSAGE ──")
        debug.log("ai_client.generate_note", user_message)
        debug.log("ai_client.generate_note", "━━━━━━━ END LLM INPUT ━━━━━━━")

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()

    if os.getenv("DEEN_DEBUG_PROMPT"):
        # Double-gated: DEEN_DEBUG_PROMPT toggles this block on/off; the
        # outer debug.log() additionally requires DEEN_DEV=1 so packaged
        # builds with DEEN_DEBUG_PROMPT alone still won't see anything
        # unless dev-mode is also set.
        debug.log("ai_client.generate_note", "── LLM RAW RESPONSE ──")
        debug.log("ai_client.generate_note", raw)
        debug.log("ai_client.generate_note", "━━━━━━━ END LLM OUTPUT ━━━━━━━")
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(raw)

    # Post-parse sanity guard. The prompt tells the model to omit
    # unverifiable Quran recitations with no placeholder, but if a stray
    # "[Quranic recitation …]" / "transcription unverified" leaks through
    # AND no verified Quran reference `(Surah …)` is present in the same
    # note, strip the offending lines before returning. Belt-and-suspenders
    # for the exact bug Abed reported in the examples.
    content = result.get("content", "") or ""
    if (("[Quranic recitation" in content or "transcription unverified" in content)
            and "(Surah " not in content):
        lines = content.splitlines()
        filtered = [
            ln for ln in lines
            if "[Quranic recitation" not in ln
            and "transcription unverified" not in ln
        ]
        result["content"] = "\n".join(filtered).strip()

    return result


# ─── Push-to-talk dictation helpers (Phase 6) ────────────────────────────────


_VERBATIM_SYSTEM_PROMPT = """You are polishing a single-speaker dictation \
transcript for a note-taking app. The speaker held a hotkey and dictated \
into their microphone; what arrives is a raw transcript with filler words, \
self-corrections, and weak punctuation.

YOUR JOB: produce a cleaned markdown version that preserves every meaningful \
word the speaker said, while applying aggressive cosmetic cleanup.

DO:
- Strip filler words: "um", "uh", "you know", "like" (when used as filler), \
"I mean", "sort of", "kind of" (when used as filler), and equivalents in other \
languages ("يعني", "اه", "هَيك", etc.).
- Collapse self-corrections to the corrected version. Example: "I want to — \
actually, I want three things" becomes "I want three things."
- Add full punctuation, paragraph breaks, and capitalization. Sentences should \
read like edited prose, not a stream of transcribed speech.
- Apply natural markdown structure when the content fits:
  * If the speaker enumerates ("first ... second ... third"), render as a \
numbered or bulleted list.
  * If the speaker shifts topic, add a markdown heading (## Topic).
  * If the speaker quotes something verbatim, render as a > blockquote.
  * If the speaker dictates code, wrap in ``` fences.
- Render markdown tables when comparisons are dictated.
- Use $...$ inline math or $$...$$ display math when formulas are dictated.
- If the speaker dictates a flow/process/timeline/relationship that fits a \
diagram, you MAY emit a ```mermaid fenced block (flowchart TD / sequenceDiagram \
/ mindmap / gantt). Use sparingly — only when it clarifies more than prose.
- If the speaker dictates numeric data with 3+ datapoints (e.g. "Q1 was 100, \
Q2 was 140, Q3 was 200"), you MAY emit a ```chart fenced block. Spec shape: \
`{"type":"line"|"bar"|"pie"|"area","data":[{"name":"Q1","value":100},...],\
"series":[{"key":"value","label":"Value","color":"#fbbf24"}],"xAxis":"name"}`.
- For custom small diagrams that don't fit Mermaid, you MAY use inline \
`<svg viewBox="0 0 W H">...</svg>`. Keep under 4KB. No `<script>`, no \
`<foreignObject>`, no `on*` attributes — those get sanitized away.

DO NOT:
- Summarize, paraphrase, or replace the speaker's wording with your own. \
Every meaningful idea the speaker stated must remain.
- Invent content the speaker didn't say.
- Add commentary, opening, or closing lines ("Here is the polished text:" — no).
- Wrap the whole output in code fences.

LANGUAGE: Detect the dominant language of the dictation and write the cleaned \
note in that language. If the speaker explicitly switches languages, follow them.

OUTPUT: ONLY the cleaned markdown. No preamble. No metadata. No JSON wrapper."""


_REWRITE_SYSTEM_PROMPT = """You are a thoughtful editor who restructures a \
spoken dictation into a polished note for a note-taking app. The speaker held \
a hotkey and dictated into their microphone; what arrives is a raw transcript.

YOUR JOB: produce a markdown note that explains the speaker's ideas BETTER \
than they did, while staying true to their intent. Summarize the meandering \
parts, expand the unclear parts with helpful context, add structure, and \
elevate the prose.

DO:
- Restructure aggressively. Add headings (##), bullet lists, numbered lists, \
markdown tables, and blockquotes wherever they aid clarity.
- Where the speaker hinted at a concept but didn't fully explain it, add a \
short clarifying sentence. Mark such additions sparingly — most content \
should still be theirs.
- Pull out direct quotes the speaker emphasized into > blockquotes.
- Strip all filler and false starts.
- Use $...$ inline math or $$...$$ display math when formulas appear.
- Use markdown tables when the speaker compared multiple items.
- Use ``` code fences for code snippets the speaker dictated.
- RICH RENDERING — lean into these when they'd genuinely help the reader:
  • ```mermaid fenced blocks for flows, sequences, mind maps, gantt charts \
when the speaker described a process / hierarchy / timeline. Keep diagrams \
small (≤12 nodes) and avoid `click` handlers (sanitizer strips them).
  • ```chart fenced blocks for numeric data with 3+ datapoints. Spec: \
`{"type":"line"|"bar"|"pie"|"area","title"?:"...","data":[...],\
"series":[{"key":"...","label":"...","color":"#hex"}],"xAxis":"name"}`. \
One JSON object per fence. Use hex colors.
  • Inline `<svg viewBox="0 0 W H">...</svg>` for custom small diagrams. \
Keep under 4KB. NO `<script>`, NO `<foreignObject>`, NO `on*` attributes \
(sanitizer drops them). Use SVG attributes (`stroke="#fff"`), not CSS `style`.

DO NOT:
- Add factual claims the speaker didn't state and you can't verify.
- Hallucinate citations, statistics, or quotes.
- Add commentary, opening, or closing lines ("Here is the polished version:" — no).
- Wrap the whole output in code fences.

LANGUAGE: Detect the dominant language of the dictation and write the note in \
that language. If the speaker explicitly switches languages, follow them.

OUTPUT: ONLY the polished markdown. No preamble. No metadata. No JSON wrapper."""


def _dictation_user_message(text: str, target_language: str | None,
                            target_language_label: str | None) -> str:
    parts = [f"DICTATION TRANSCRIPT:\n{text.strip()}"]
    if target_language and target_language != "auto" and target_language_label:
        parts.append(
            f"\nOUTPUT LANGUAGE OVERRIDE: write the note in "
            f"{target_language_label} ({target_language}). This overrides the "
            "default rule of following the dictation's language."
        )
    return "\n".join(parts)


def polish_verbatim_aggressive(text: str, target_language: str | None = None,
                               target_language_label: str | None = None) -> str:
    """Aggressive verbatim cleanup of a dictation transcript.

    Filler stripped, punctuation added, self-corrections collapsed, natural
    markdown structure applied — but every meaningful word the speaker said
    is preserved. Returns the cleaned markdown body as a plain string.
    """
    text = (text or "").strip()
    if not text:
        return ""
    client = _get_openai()
    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": _VERBATIM_SYSTEM_PROMPT},
            {"role": "user", "content": _dictation_user_message(
                text, target_language, target_language_label
            )},
        ],
        temperature=0.1,
        max_tokens=2000,
    )
    out = resp.choices[0].message.content.strip()
    if out.startswith("```"):
        # Strip an accidental outer code-fence — the prompt forbids it but
        # belt-and-suspenders.
        out = out.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return out


def rewrite_dictation(text: str, target_language: str | None = None,
                      target_language_label: str | None = None) -> str:
    """AI-rewrite a dictation transcript: summarize, restructure, explain
    better, add helpful structure. Returns markdown."""
    text = (text or "").strip()
    if not text:
        return ""
    client = _get_openai()
    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": _dictation_user_message(
                text, target_language, target_language_label
            )},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    out = resp.choices[0].message.content.strip()
    if out.startswith("```"):
        out = out.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return out
