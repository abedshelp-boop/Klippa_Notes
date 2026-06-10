import asyncio
from functools import partial
from datetime import datetime, timezone

from openai import APIError as OpenAIAPIError

from resampler import audio_to_wav_bytes
from ai_client import transcribe_audio, generate_note, translate_command_to_english
from database import create_note, get_note, append_to_note
import target as target_state
from config import (
    PENDING_DIR,
    SAMPLE_RATE,
    SLICE_DURATION_SEC,
    TRANSCRIPT_MAX_WORDS_PER_SEC,
)
from debug import debug
from media_control import resume_media
from quran_lookup import enrich_quran_in_transcript
from vad import extract_speech


async def process_note(system_audio, command_audio, broadcast_fn,
                       media_was_paused=False, target=None,
                       language=None, routing_decision=None,
                       quick_inbox_id=None):
    """
    Full pipeline: audio -> VAD trim -> transcription -> note generation -> save.
    Runs blocking AI calls in a thread pool.

    target: snapshot of the routing target at capture time:
      {"note_id": str | None, "create_new_pending": bool}
      - note_id set     -> append to that existing note
      - create_new_pending=True -> create new note, then pin target to it
      - both falsy      -> create a new note per capture (default)

    language: snapshot of the output-language preference at capture time:
      {"code": str, "label": str, "emoji": str}
      - code == "auto" preserves Rule 8 (audio-dominant) in the LLM prompt.
      - any other code appends an OUTPUT LANGUAGE OVERRIDE that forces the
        note into that language while leaving Quran preservation intact.
      None == treat as "auto" (back-compat for any caller that doesn't pass it).
    """
    loop = asyncio.get_event_loop()

    await broadcast_fn({"type": "status", "status": "processing"})

    orig_system_audio = system_audio  # preserved for _save_pending on failures
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    try:
        # VAD trim — concatenate only detected speech, drop silence/noise.
        # This is what kills the "Whisper hallucinates Quran translations"
        # class of bug: with no silence in the input, Whisper has nothing
        # to fill with training-data phrases. See vad.py for detail.
        system_audio = await loop.run_in_executor(
            None,
            partial(extract_speech, system_audio, SAMPLE_RATE,
                    max_speech_sec=SLICE_DURATION_SEC),
        )

        if len(system_audio) == 0:
            debug.warn(
                "Deen",
                "VAD found no speech — aborting note",
            )
            _save_pending(
                orig_system_audio, command_audio,
                "VAD detected no speech in captured audio",
                suffix="_no_speech",
            )
            await broadcast_fn({"type": "status", "status": "listening"})
            return

        speech_duration_sec = len(system_audio) / SAMPLE_RATE
        system_wav = audio_to_wav_bytes(system_audio)

        # System audio: enable diarization so the LLM can tell questioner
        # from responder when attributing quotes.
        system_transcript = await loop.run_in_executor(
            None, partial(transcribe_audio, system_wav, with_speakers=True)
        )

        # Pre-verify any Quranic recitation against the bundled Uthmani
        # corpus before the LLM sees the transcript. Whisper + LLM alone
        # produce plausible-looking Arabic that's theologically wrong —
        # this step replaces matched passages with byte-exact canonical
        # text and ayah references so the LLM only has to pass them through.
        system_transcript = await loop.run_in_executor(
            None, enrich_quran_in_transcript, system_transcript
        )

        command_transcript = "Take note of what was just said."
        if command_audio is not None and len(command_audio) > 0:
            try:
                command_wav = audio_to_wav_bytes(command_audio)
                # Command is single-speaker, short — no diarization needed.
                command_transcript = await loop.run_in_executor(
                    None, partial(transcribe_audio, command_wav, with_speakers=False)
                )
            except (OSError, RuntimeError, ValueError, OpenAIAPIError) as e:
                debug.warn(
                    "Deen",
                    "command transcription failed, using default",
                    e,
                )

        # Detect command language. Cheap Arabic-block check — covers the
        # main non-English case Deen-Notes sees. Any other language falls
        # through as "en" for now; add more branches here if needed.
        command_lang = (
            "ar"
            if any("\u0600" <= ch <= "\u06ff" for ch in command_transcript)
            else "en"
        )
        # Pre-translate non-English commands to English so the main LLM
        # isn't handed an Arabic instruction inside a primarily-English
        # prompt (the failure mode was the model treating the Arabic as
        # transcript to echo instead of an instruction to interpret).
        command_transcript_en = None
        if command_lang != "en":
            command_transcript_en = await loop.run_in_executor(
                None, translate_command_to_english, command_transcript
            )
            if command_transcript_en:
                debug.log(
                    "Deen",
                    f"command translated ({command_lang}→en)",
                    command_transcript_en,
                )

        # Always dump the full transcript to disk for post-hoc debugging.
        # Prior version only printed the first 100 chars to stdout, which
        # made triaging hallucinations impossible after the fact. Includes
        # command language + translation so triage can distinguish "LLM
        # ignored the command" from "command mis-transcribed/-translated".
        _save_transcript_log(timestamp, command_transcript, system_transcript,
                             speech_duration_sec,
                             command_lang=command_lang,
                             command_transcript_en=command_transcript_en)

        # Hallucination heuristic: real speech tops out around 3-4 words/sec.
        # A transcript dramatically denser than its own speech duration is
        # the fingerprint of Whisper inventing content. Don't block — flag
        # the audio for review and keep going.
        word_count = len(system_transcript.split())
        wps = word_count / speech_duration_sec if speech_duration_sec > 0 else 0.0
        if wps > TRANSCRIPT_MAX_WORDS_PER_SEC:
            debug.warn(
                "Deen",
                "suspicious word rate (possible hallucination)",
                {
                    "word_count": word_count,
                    "speech_sec": speech_duration_sec,
                    "wps": wps,
                    "threshold_wps": TRANSCRIPT_MAX_WORDS_PER_SEC,
                },
            )
            _save_pending(
                orig_system_audio, command_audio,
                f"Suspicious word rate {wps:.2f} wps "
                f"(> {TRANSCRIPT_MAX_WORDS_PER_SEC}) — possible hallucination",
                suffix="_suspicious",
            )

        debug.log(
            "Deen",
            "system transcript",
            {
                "chars": len(system_transcript),
                "words": word_count,
                "wps": wps,
                "preview": system_transcript[:100],
            },
        )
        debug.log("Deen", "command", command_transcript)

        target_language = (language or {}).get("code", "auto") or "auto"
        target_language_label = (language or {}).get("label", "Global") or "Global"
        debug.log(
            "Deen",
            "target output language",
            {"label": target_language_label, "code": target_language},
        )

        note_data = await loop.run_in_executor(
            None, partial(generate_note, system_transcript, command_transcript,
                          command_lang=command_lang,
                          command_transcript_en=command_transcript_en,
                          target_language=target_language,
                          target_language_label=target_language_label)
        )

        # End-to-end triage trail: append the LLM's note content to the
        # same log file, so one file shows what the user said → what the
        # LLM received → what it produced.
        _append_note_content_to_log(timestamp, note_data.get("content", ""))

        # Routing precedence:
        # 1. voice_routing.RoutingDecision (when a command transcript was
        #    parseable) wins outright. This is the new voice-grammar path.
        # 2. target_state pinned note (legacy picker pin) — preserves the
        #    pre-voice-grammar behavior for users who set a pin via the bubble.
        # 3. context_state foreground-open-note default for plain captures.
        # 4. Quick Inbox.
        import context_state
        import quick_inbox as qi_mod
        import tts_client

        existing_note = None
        target_was_stale = False
        proposed_title = None
        create_new = False
        body_content = note_data.get("content", system_transcript)

        if routing_decision is not None:
            if routing_decision.kind == "existing" and routing_decision.note_id:
                existing_note = await get_note(routing_decision.note_id)
                if existing_note is None:
                    target_was_stale = True
                    # Stale routing target — fall through to Quick Inbox.
                    inbox = await qi_mod.ensure_quick_inbox()
                    existing_note = inbox
            elif routing_decision.kind == "create_new":
                create_new = True
                proposed_title = routing_decision.proposed_title
        else:
            # Legacy path (no voice routing decision was provided — likely the
            # /trigger keyboard shortcut firing with no command transcript).
            if target and target.get("note_id"):
                existing_note = await get_note(target["note_id"])
                if existing_note is None:
                    target_was_stale = True
            elif target and target.get("create_new_pending"):
                create_new = True
            else:
                ctx = context_state.get_context()
                if ctx.get("foreground") and ctx.get("open_note_id"):
                    existing_note = await get_note(ctx["open_note_id"])
                if existing_note is None:
                    inbox = await qi_mod.ensure_quick_inbox()
                    existing_note = inbox

        if existing_note:
            updated = await append_to_note(existing_note["id"], body_content)
            await broadcast_fn({"type": "note_updated", "note": updated})
            debug.log("Deen", "appended to existing note", existing_note["title"])
            context_state.set_last_capture(existing_note["id"])
            tts_client.say(f"Saved to {existing_note['title']}")
        else:
            title_to_use = proposed_title or note_data.get("title", "Untitled Note")
            note = await create_note(
                title=title_to_use,
                content=body_content,
                tags=note_data.get("tags", []),
                source=note_data.get("source", ""),
            )
            await broadcast_fn({"type": "note", "note": note})
            debug.log("Deen", "note created", note["title"])
            context_state.set_last_capture(note["id"])
            tts_client.say(f"Saved to {note['title']}")

            if (target and target.get("create_new_pending")) or create_new:
                target_state.set_target(note["id"])
                await broadcast_fn({
                    "type": "target",
                    "note_id": note["id"],
                    "create_new_pending": False,
                    "title": note["title"],
                })
            elif target_was_stale:
                target_state.clear_target()
                await broadcast_fn({
                    "type": "target",
                    "note_id": None,
                    "create_new_pending": False,
                    "title": None,
                })

    except Exception as e:
        # Pipeline crosses many subsystems (Whisper/AssemblyAI/LLM/DB/disk)
        # each with its own exception taxonomy. Per Abed's decision: log
        # loudly, save audio for retry, then re-raise so the caller sees
        # the error (no deliberate swallow). The previous bare-except
        # swallowed every failure silently.
        debug.error("note_generator", "pipeline failed", e)
        _save_pending(orig_system_audio, command_audio, str(e))
        raise

    finally:
        if media_was_paused:
            resume_media()
        await broadcast_fn({"type": "status", "status": "listening"})


def _save_transcript_log(timestamp, command_transcript, system_transcript,
                          speech_duration_sec,
                          command_lang="en", command_transcript_en=None):
    """Always-on transcript dump for post-hoc hallucination triage. One small
    text file per note; no rotation yet (add later if disk pressure appears).

    command_lang / command_transcript_en: recorded alongside the original so
    bug triage can distinguish "LLM ignored a correctly-transcribed command"
    from "command was mis-transcribed or mis-translated before the LLM saw
    it" — the three Arabic-command bug classes look identical on the surface.
    """
    try:
        path = PENDING_DIR / f"{timestamp}_transcript.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"timestamp: {timestamp}\n")
            f.write(f"speech_duration_sec: {speech_duration_sec:.2f}\n")
            f.write("\n=== USER COMMAND ===\n")
            f.write(f"language: {command_lang}\n")
            f.write((command_transcript or "") + "\n")
            if command_transcript_en:
                f.write("\n=== USER COMMAND (English translation) ===\n")
                f.write(command_transcript_en + "\n")
            f.write("\n=== SYSTEM TRANSCRIPT ===\n")
            f.write((system_transcript or "") + "\n")
    except (OSError, ValueError) as e:
        debug.warn("Deen", "failed to save transcript log", e)


def _append_note_content_to_log(timestamp, note_content):
    """Append the final LLM-generated note body to the transcript log so one
    file shows: what the user said → what the LLM received → what it
    produced. Silent on failure — this is diagnostic, not critical path."""
    try:
        path = PENDING_DIR / f"{timestamp}_transcript.txt"
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n=== LLM OUTPUT (content) ===\n")
            f.write((note_content or "") + "\n")
    except (OSError, ValueError) as e:
        debug.warn("Deen", "failed to append note content to log", e)


def _save_pending(system_audio, command_audio, error_msg, suffix=""):
    """Save audio clips to pending/ for later retry or manual review.

    suffix: appended to the timestamp to distinguish routine failures
    (`""`) from explicit categories (`"_no_speech"`, `"_suspicious"`)
    so they're grep-able on disk.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + suffix
    try:
        sys_path = PENDING_DIR / f"{stamp}_system.wav"
        err_path = PENDING_DIR / f"{stamp}_error.txt"

        with open(sys_path, "wb") as f:
            f.write(audio_to_wav_bytes(system_audio))

        if command_audio is not None and len(command_audio) > 0:
            cmd_path = PENDING_DIR / f"{stamp}_command.wav"
            with open(cmd_path, "wb") as f:
                f.write(audio_to_wav_bytes(command_audio))

        with open(err_path, "w", encoding="utf-8") as f:
            f.write(error_msg)

        debug.log("Deen", "saved pending note", str(PENDING_DIR / stamp))
    except OSError as save_err:
        debug.error("Deen", "failed to save pending", save_err)
