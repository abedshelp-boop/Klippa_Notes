# Future Features

This document tracks planned improvements for the Note Taker app.

## ~~1. Headphone detection + adaptive behavior~~ (DONE)
- ~~The app should auto-detect whether you are using headphones and adjust behavior accordingly.~~
- ~~Expected adjustments might include volume, audio output mode, or microphone/listening profile (exact behavior TBD).~~
- **Implemented:** The WASAPI loopback capture now automatically follows the default output device. Every ~3 seconds it checks if the default output changed (e.g. headphones plugged in) and seamlessly switches the loopback stream to the new device.


## ~~2. Arabic transliteration-to-script conversion~~ (DONE)
- ~~When Whisper transcribes Arabic words spoken in audio, it writes them in Latin/English letters (e.g., "dalil", "hadith", "Rasulullah").~~
- ~~A post-processing step should detect these transliterated Arabic words and convert them to Arabic script (e.g., "dalil" -> "دليل").~~
- **Implemented:** A dedicated GPT post-processing step runs after note generation (when enabled). Toggleable via Settings > Arabic Script Conversion.

## 3. Export notes as nice-looking text
- The app should allow exporting your notes as clean, good-looking plain text suitable for posting or sharing on other platforms.
- Export should preserve the visual structure as much as possible (for example: headings, paragraphs, and bullet points).
- Output format target: a formatted `.txt` export and/or copy-to-clipboard in the same "nice text" style.

## 4. Code signing for public distribution
- Before releasing the app publicly, the Electron executable must be code-signed with a valid certificate.
- Without signing, Windows SmartScreen and Firewall will warn users or block features, making the app look untrustworthy.
- Requires purchasing a code-signing certificate (e.g., from DigiCert, Sectigo, or similar CA) and integrating it into the build/packaging pipeline (e.g., via electron-builder's `win.certificateFile` option).

## 5. Video-aware note tracking (auto-detect video switches)
- **Goal:** The app should automatically detect which video the user is watching and manage per-video note documents. If the user asks to note something, the note goes into the doc for the *current* video. If the video changes, a new doc is created for the new video.
- **How it works:**
  - Monitor the active window title at regular intervals (browsers display the video title in the tab/window title bar — e.g., "Video Title - YouTube - Google Chrome").
  - Parse out the video title from the window title string.
  - When the detected title changes, the app knows the user switched videos.
  - Maintain a mapping of video titles to their note documents. If a doc already exists for a video, resume appending to it; otherwise, create a new one.
- **Implementation approach:**
  - Use a native module or PowerShell/Win32 API call (e.g., `GetForegroundWindow` + `GetWindowText`) to poll the active window title every few seconds.
  - Strip browser/player suffixes to extract the clean video title.
  - Store the mapping (video title → note file path) in a local JSON index so docs persist across sessions.
- **Edge cases to handle:** Multiple tabs with videos, renamed/retitled videos, non-browser video players (VLC, mpv), and the user switching to a non-video window (should retain the last known video context).

## 6. Speaker diarization (distinguish between speakers)
- **Goal:** When two or more speakers are talking in the audio, the app should identify and label them separately (e.g., "Speaker 1:", "Speaker 2:") in both live notes and transcriptions.
- **How it works:**
  - This is called **speaker diarization** — the process of determining "who spoke when" in an audio stream.
  - Combine Whisper's transcription output with a diarization model that segments audio by speaker identity.
- **Implementation approach:**
  - **Option A — WhisperX:** An open-source pipeline that extends Whisper with forced alignment and speaker diarization (uses pyannote-audio under the hood). Produces word-level timestamps with speaker labels.
  - **Option B — pyannote-audio standalone:** Run pyannote's diarization pipeline on the audio to get speaker segments, then align those segments with Whisper's transcript timestamps.
  - **Option C — OpenAI API future support:** Monitor OpenAI's API for native diarization support, which may simplify integration.
- **Notes:**
  - pyannote-audio requires a Hugging Face access token (free) and agreement to their model license.
  - Diarization identifies *different* speakers but doesn't know their *names* — labels are generic (Speaker 1, Speaker 2) unless the user manually assigns names.
  - Accuracy is best with clear audio, distinct voices, and minimal cross-talk.
  - For live/streaming use, diarization adds latency; consider processing in chunks or applying it as a post-processing step.

## 7. Full video transcription with speaker labels (from link or upload)
- **Goal:** A dedicated button/page in the app where the user can paste a video URL (YouTube, etc.) or upload a video file, and the app produces a full transcription with speaker labels — ready for import into video editors like CapCut.
- **How it works:**
  - **Step 1 — Obtain audio:** For URLs, download the video using `yt-dlp` and extract the audio track. For uploaded files, extract audio using `ffmpeg`.
  - **Step 2 — Transcribe:** Run the audio through Whisper to get a timestamped transcript.
  - **Step 3 — Diarize:** Run speaker diarization (see Feature #6) to label each segment by speaker.
  - **Step 4 — Merge & export:** Combine the transcript with speaker labels and export in a standard subtitle format (SRT or VTT) with speaker prefixes.
- **Output format example (SRT with speaker tags):**
  ```
  1
  00:00:01,000 --> 00:00:04,500
  [Speaker 1]: Welcome to today's lecture on machine learning.

  2
  00:00:05,000 --> 00:00:08,200
  [Speaker 2]: Thanks for having me. Let's dive in.
  ```
- **Implementation approach:**
  - Bundle `yt-dlp` and `ffmpeg` with the app (or require them as dependencies).
  - Provide a simple UI: a text input for URL, a file picker for uploads, a "Transcribe" button, and a progress indicator.
  - Processing can be done locally (heavier on resources) or via a backend/cloud worker for longer videos.
  - Export options: `.srt`, `.vtt`, `.txt` (plain text with speaker labels), and copy-to-clipboard.
- **CapCut compatibility:** CapCut supports SRT import natively. Speaker-labeled SRT files will import cleanly, with each subtitle block attributed to the correct speaker. The user can then style speakers differently in the editor.
