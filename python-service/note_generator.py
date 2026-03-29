import asyncio
from functools import partial
from datetime import datetime, timezone

from resampler import audio_to_wav_bytes
from ai_client import transcribe_audio, generate_note, arabize_content
from database import create_note, find_note_by_video_url, append_to_note
import config
from config import PENDING_DIR
from media_control import resume_media


async def process_note(system_audio, command_audio, broadcast_fn,
                       media_was_paused=False, video_info=None):
    """
    Full pipeline: audio -> transcription -> note generation -> save.
    Runs blocking AI calls in a thread pool.
    """
    loop = asyncio.get_event_loop()

    await broadcast_fn({"type": "status", "status": "processing"})

    try:
        system_wav = audio_to_wav_bytes(system_audio)

        system_transcript = await loop.run_in_executor(
            None, transcribe_audio, system_wav
        )

        command_transcript = "Take note of what was just said."
        if command_audio is not None and len(command_audio) > 0:
            try:
                command_wav = audio_to_wav_bytes(command_audio)
                command_transcript = await loop.run_in_executor(
                    None, transcribe_audio, command_wav
                )
            except Exception as e:
                print(f"[Klippa] Command transcription failed, using default: {e}")

        print(f"[Klippa] System transcript ({len(system_transcript)} chars): "
              f"{system_transcript[:100]}...")
        print(f"[Klippa] Command: {command_transcript}")

        video_title = video_info["title"] if video_info else None
        video_url = video_info["url"] if video_info else ""

        if video_title:
            print(f"[Klippa] Video context: {video_title}")

        note_data = await loop.run_in_executor(
            None, partial(generate_note, system_transcript, command_transcript,
                          video_title=video_title)
        )

        if config.ARABIZE_ENABLED:
            try:
                note_data["content"] = await loop.run_in_executor(
                    None, arabize_content, note_data["content"]
                )
                print("[Klippa] Arabic script conversion applied")
            except Exception as e:
                print(f"[Klippa] Arabize step failed, using original: {e}")

        existing_note = await find_note_by_video_url(video_url) if video_url else None

        if existing_note:
            updated = await append_to_note(
                existing_note["id"], note_data.get("content", system_transcript)
            )
            await broadcast_fn({"type": "note_updated", "note": updated})
            print(f"[Klippa] Appended to existing note: {existing_note['title']}")
        else:
            note = await create_note(
                title=note_data.get("title", "Untitled Note"),
                content=note_data.get("content", system_transcript),
                tags=note_data.get("tags", []),
                source=note_data.get("source", ""),
                video_url=video_url,
            )
            await broadcast_fn({"type": "note", "note": note})
            print(f"[Klippa] Note created: {note['title']}")

    except Exception as e:
        print(f"[Klippa] Error processing note: {e}")
        _save_pending(system_audio, command_audio, str(e))

    finally:
        if media_was_paused:
            resume_media()
        await broadcast_fn({"type": "status", "status": "listening"})


def _save_pending(system_audio, command_audio, error_msg):
    """Save audio clips to pending/ for later retry when offline."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    try:
        sys_path = PENDING_DIR / f"{timestamp}_system.wav"
        err_path = PENDING_DIR / f"{timestamp}_error.txt"

        with open(sys_path, "wb") as f:
            f.write(audio_to_wav_bytes(system_audio))

        if command_audio is not None and len(command_audio) > 0:
            cmd_path = PENDING_DIR / f"{timestamp}_command.wav"
            with open(cmd_path, "wb") as f:
                f.write(audio_to_wav_bytes(command_audio))

        with open(err_path, "w", encoding="utf-8") as f:
            f.write(error_msg)

        print(f"[Klippa] Saved pending note to {PENDING_DIR / timestamp}*")
    except Exception as save_err:
        print(f"[Klippa] Failed to save pending: {save_err}")
