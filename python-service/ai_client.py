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

import assemblyai as aai
import soundfile as sf
from openai import OpenAI

from collections import Counter

from config import (
    ASSEMBLYAI_API_KEY,
    LANGUAGE_PROBE_DURATION_SEC,
    LANGUAGE_PROBE_OFFSETS_SEC,
    OPENAI_API_KEY,
    SMART_ROUTING_ENABLED,
)
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
    except Exception as e:
        print(f"[Deen] Language probe @ {offset_sec}s failed: {e}")
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
            print(f"[Deen] Language probe (short-clip, {total_sec:.1f}s): '{code}'")
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
    print(f"[Deen] Language probe votes: {results} → '{winner}'")
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
        print("[Deen] ASSEMBLYAI_API_KEY missing, using OpenAI fallback")
        return _openai_transcribe(wav_bytes)

    if SMART_ROUTING_ENABLED:
        lang = _detect_language(wav_bytes)
        use_assemblyai = (lang == "en")
        if use_assemblyai:
            print("[Deen] Language probe: 'en' — routing to AssemblyAI")
        else:
            print(
                f"[Deen] Language probe: '{lang or 'unknown'}' — routing to OpenAI Whisper"
            )
    else:
        # Smart routing off: preserve legacy force-AAI behavior as an escape hatch.
        use_assemblyai = True

    if use_assemblyai:
        try:
            return _aai_transcribe(wav_bytes, with_speakers=with_speakers)
        except Exception as e:
            print(f"[Deen] AssemblyAI transcribe failed, falling back to OpenAI: {e}")

    return _openai_transcribe(wav_bytes)


# ─── Note generation ─────────────────────────────────────────────────────────

def generate_note(system_transcript: str, command_transcript: str,
                   video_title: str | None = None) -> dict:
    """
    Given a transcript of the system audio and the user's voice command,
    generate a beautifully structured Markdown note.
    Returns dict with keys: title, content, tags, source.
    """
    client = _get_openai()

    video_context_line = ""
    if video_title:
        video_context_line = (
            f'\n10. The user is currently watching a video titled "{video_title}". '
            'Use this information to inform the "source" field and to provide '
            'better context for the note title.\n'
        )

    system_prompt = f"""You are Deen-Notes, an AI note-taking assistant. Your job is to create beautiful, well-structured Markdown notes from audio transcripts.

RULES:
1. The user will provide two things:
   - SYSTEM AUDIO: A transcript of what was playing (podcast, lecture, video, etc.). This is roughly the last 5 minutes of audio, so it may contain multiple turns of conversation, including questions and answers.
   - USER COMMAND: What the user asked you to note down.

2. Based on the user's command, find the relevant portion of the system audio transcript and use the speaker's exact words. Do NOT paraphrase, reword, or summarize in your own style. Copy the relevant text from the transcript verbatim, preserving the speaker's original phrasing and word choices.

3. SPEAKER ATTRIBUTION — be purely command-driven:
   - The SYSTEM AUDIO transcript may contain speaker labels like `[Speaker A]:` and `[Speaker B]:` from diarization.
   - Read the USER COMMAND literally and let it decide which speaker to capture. If the user asks about the question or the questioner, capture the questioner. If the user asks about the answer or the responder, capture the responder. If the user asks about both sides or the exchange as a whole, capture both. Do NOT assume the user meant the "main speaker" or the person talking longer — follow what they actually asked for.
   - DO NOT include the speaker labels themselves in the final note content — they are metadata for you, not the reader.
   - Fallback ONLY when the USER COMMAND gives no indication of which speaker (e.g. a bare "take note of what was just said"): capture the most recent substantive utterance on the topic, without preferring any speaker role over another.

4. COMPLETENESS:
   - Capture the FULL relevant statement. Don't truncate the response just because it's long — include every relevant sentence.
   - If the relevant statement appears to start mid-sentence at the beginning of the transcript (i.e. the speaker was already talking before the buffer began), prefix the quote with `[…] ` to indicate that.
   - If the relevant statement appears to be cut off at the end of the transcript (i.e. the speaker was still talking when the user triggered the note), suffix the quote with ` […]` to indicate that.

5. LANGUAGE OF THE NOTE — CRITICAL:
   - Detect the DOMINANT language of the SYSTEM AUDIO TRANSCRIPT (i.e. which language the speaker is mostly using). That dominant language becomes the note's default language. Write the title, section headings, bullet points, and body text in that dominant language.
   - ENGLISH-DOMINANT videos (English mixed with sprinkled Arabic terms): Write the note in English. Common Arabic / Islamic terms that are embedded in the speech — e.g. hadith, sunnah, sufi, deobandi, wahhabi, maslaha, shia, sunni, ummah, madhhab, hanbali, athari, ash'ari, maturidi, insha'Allah, sallallahu alayhi wa sallam, subhanahu wa ta'ala, names of imams, book references like Sahih al-Bukhari / Musnad — must be TRANSLITERATED into English letters (Latin script) and **bolded**. Do NOT switch to Arabic script for these in-flow terms.
   - ARABIC-DOMINANT videos (mostly spoken in Arabic): Write the note in natural Arabic script. No transliteration — use Arabic as it is normally written. Sprinkled English words stay in English.

6. QUOTES AND RECITATIONS — preserve the original language, do NOT translate or transliterate:
   - If the speaker QUOTES someone (a scholar, an imam, a poem, a famous saying) in a language DIFFERENT from the note's default language, preserve that quote in its ORIGINAL language and script, wrapped in "double quotation marks". Example: in an English-dominant note, an Arabic quote from an imam stays as "قال الإمام أحمد: ...". Do NOT translate or transliterate such quotes.
   - QURAN — EXACT-COPY RULE (no exceptions):
     • The SYSTEM AUDIO TRANSCRIPT may already contain passages in the form `<arabic-text-with-tashkil> (Surah Name, X:Y)` or `<...> (Surah Name, X:Y-Z)`. These are PRE-VERIFIED against the official Uthmani corpus by the transcription pipeline before you see them. When they appear, copy each one VERBATIM into the note — every letter, every diacritic, every bracket, and the reference — exactly as given. Do NOT re-spell, re-transliterate, swap hamza/alif/yaa variants, add or remove tashkil, or "correct" anything. Any character-level change corrupts the Quran, which is unacceptable.
     • If the speaker recites the Quran but the transcript does NOT already contain a `<...> (Surah ..., X:Y)` block for that recitation, it means the pipeline couldn't verify it. In that case, DO NOT write Arabic Quran text from memory — instead, omit the recitation or write "[Quranic recitation — transcription unverified]" in place of it. Better to omit than to quote the Quran inaccurately.
   - Hadith quoted verbatim from an Arabic source follows the same rule as other Arabic quotes: preserve the Arabic inside "quotation marks", then optionally follow with the source reference (e.g. **Sahih al-Bukhari**).

7. Format guidelines:
   - Use a clear, descriptive title (H1 is NOT needed — title is separate)
   - Use ## for main sections
   - Use > blockquotes for direct quotes from the speaker
   - Use bullet points for key takeaways
   - Use **bold** for transliterated Arabic terms (in English notes) and other key emphasis
   - Use *italics* sparingly — for English book titles or non-Arabic references
   - Use LaTeX ($...$) for any mathematical formulas
   - Use code blocks for any code or technical content
   - Use tables when comparing things
   - Use --- for section separators when appropriate

8. CRITICAL: You must use the transcript's exact wording. Do not rephrase, do not write in your own style, and do not invent content. The note should read as if the speaker wrote it, not you. Use blockquote formatting (>) to present verbatim transcript excerpts.

9. Return your response as JSON with exactly these keys:
   - "title": A concise, descriptive title for the note
   - "content": The full Markdown content of the note
   - "tags": An array of 2-5 relevant tags (lowercase, no spaces)
   - "source": A brief description of the source type (e.g., "Podcast", "Lecture", "Islamic Khutba", "Math Lesson")
{video_context_line}
Return ONLY valid JSON, no markdown code fences around it."""

    user_message = f"""SYSTEM AUDIO TRANSCRIPT:
{system_transcript}

USER COMMAND:
{command_transcript}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw)
