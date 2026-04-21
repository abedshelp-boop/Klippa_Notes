import asyncio
from functools import partial
from datetime import datetime, timezone

from resampler import audio_to_wav_bytes
from ai_client import transcribe_audio, generate_note
from database import create_note, find_note_by_video_url, append_to_note
from config import (
    PENDING_DIR,
    SAMPLE_RATE,
    SLICE_DURATION_SEC,
    TRANSCRIPT_MAX_WORDS_PER_SEC,
)
from media_control import resume_media
from quran_lookup import enrich_quran_in_transcript
from vad import extract_speech


async def process_note(system_audio, command_audio, broadcast_fn,
                       media_was_paused=False, video_info=None):
    """
    Full pipeline: audio -> VAD trim -> transcription -> note generation -> save.
    Runs blocking AI calls in a thread pool.
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
            print("[Deen] VAD found no speech — aborting note instead of "
                  "transcribing silence.")
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
            except Exception as e:
                print(f"[Deen] Command transcription failed, using default: {e}")

        # Always dump the full transcript to disk for post-hoc debugging.
        # Prior version only printed the first 100 chars to stdout, which
        # made triaging hallucinations impossible after the fact.
        _save_transcript_log(timestamp, command_transcript, system_transcript,
                             speech_duration_sec, video_info)

        # Hallucination heuristic: real speech tops out around 3-4 words/sec.
        # A transcript dramatically denser than its own speech duration is
        # the fingerprint of Whisper inventing content. Don't block — flag
        # the audio for review and keep going.
        word_count = len(system_transcript.split())
        wps = word_count / speech_duration_sec if speech_duration_sec > 0 else 0.0
        if wps > TRANSCRIPT_MAX_WORDS_PER_SEC:
            print(f"[Deen] ⚠ Suspicious word rate: {word_count} words in "
                  f"{speech_duration_sec:.1f}s of speech ({wps:.2f} wps > "
                  f"{TRANSCRIPT_MAX_WORDS_PER_SEC}). Saving audio for review.")
            _save_pending(
                orig_system_audio, command_audio,
                f"Suspicious word rate {wps:.2f} wps "
                f"(> {TRANSCRIPT_MAX_WORDS_PER_SEC}) — possible hallucination",
                suffix="_suspicious",
            )

        print(f"[Deen] System transcript ({len(system_transcript)} chars, "
              f"{word_count} words, {wps:.2f} wps): "
              f"{system_transcript[:100]}...")
        print(f"[Deen] Command: {command_transcript}")

        video_title = video_info["title"] if video_info else None
        video_url = video_info["url"] if video_info else ""

        if video_title:
            print(f"[Deen] Video context: {video_title}")

        note_data = await loop.run_in_executor(
            None, partial(generate_note, system_transcript, command_transcript,
                          video_title=video_title)
        )

        existing_note = await find_note_by_video_url(video_url) if video_url else None

        if existing_note:
            updated = await append_to_note(
                existing_note["id"], note_data.get("content", system_transcript)
            )
            await broadcast_fn({"type": "note_updated", "note": updated})
            print(f"[Deen] Appended to existing note: {existing_note['title']}")
        else:
            note = await create_note(
                title=note_data.get("title", "Untitled Note"),
                content=note_data.get("content", system_transcript),
                tags=note_data.get("tags", []),
                source=note_data.get("source", ""),
                video_url=video_url,
            )
            await broadcast_fn({"type": "note", "note": note})
            print(f"[Deen] Note created: {note['title']}")

    except Exception as e:
        print(f"[Deen] Error processing note: {e}")
        _save_pending(orig_system_audio, command_audio, str(e))

    finally:
        if media_was_paused:
            resume_media()
        await broadcast_fn({"type": "status", "status": "listening"})


def _save_transcript_log(timestamp, command_transcript, system_transcript,
                          speech_duration_sec, video_info):
    """Always-on transcript dump for post-hoc hallucination triage. One small
    text file per note; no rotation yet (add later if disk pressure appears)."""
    try:
        path = PENDING_DIR / f"{timestamp}_transcript.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"timestamp: {timestamp}\n")
            f.write(f"speech_duration_sec: {speech_duration_sec:.2f}\n")
            if video_info:
                f.write(f"video_title: {video_info.get('title', '')}\n")
                f.write(f"video_url: {video_info.get('url', '')}\n")
            f.write("\n=== USER COMMAND ===\n")
            f.write((command_transcript or "") + "\n")
            f.write("\n=== SYSTEM TRANSCRIPT ===\n")
            f.write((system_transcript or "") + "\n")
    except Exception as e:
        print(f"[Deen] Failed to save transcript log: {e}")


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

        print(f"[Deen] Saved pending note to {PENDING_DIR / stamp}*")
    except Exception as save_err:
        print(f"[Deen] Failed to save pending: {save_err}")
