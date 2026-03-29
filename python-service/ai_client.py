import io
from openai import OpenAI
from config import OPENAI_API_KEY

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"


def _whisper_call(wav_bytes: bytes, language: str | None = None) -> str:
    """Transcription API call using gpt-4o-mini-transcribe."""
    client = _get_client()
    audio_file = io.BytesIO(wav_bytes)
    audio_file.name = "audio.wav"

    kwargs = {
        "model": TRANSCRIPTION_MODEL,
        "file": audio_file,
    }
    if language:
        kwargs["language"] = language

    response = client.audio.transcriptions.create(**kwargs)
    return response.text.strip()


def transcribe_audio(wav_bytes: bytes, language: str | None = None) -> str:
    """Transcribe audio with automatic language verification.

    Auto-detects language via Whisper. If the result is heavily Arabic,
    retries with forced English and picks the better transcript.
    This catches Whisper misdetecting English Islamic-topic audio as Arabic.
    """
    if language:
        return _whisper_call(wav_bytes, language)

    transcript = _whisper_call(wav_bytes)
    arabic_ratio = _arabic_char_ratio(transcript)

    if arabic_ratio < 0.3:
        return transcript

    try:
        en_transcript = _whisper_call(wav_bytes, "en")
        en_arabic_ratio = _arabic_char_ratio(en_transcript)

        en_words = len(en_transcript.split())
        auto_words = len(transcript.split())

        if en_arabic_ratio < 0.15 and en_words > auto_words * 0.3:
            print(f"[Klippa] Language auto-correction: auto-detect was "
                  f"{arabic_ratio:.0%} Arabic, English retry is "
                  f"{en_arabic_ratio:.0%} Arabic — using English")
            return en_transcript
    except Exception as e:
        print(f"[Klippa] English retry failed, using auto-detect: {e}")

    return transcript


def generate_note(system_transcript: str, command_transcript: str,
                   video_title: str | None = None) -> dict:
    """
    Given a transcript of the system audio and the user's voice command,
    generate a beautifully structured Markdown note.
    Returns dict with keys: title, content, tags, source.
    """
    client = _get_client()

    video_context_line = ""
    if video_title:
        video_context_line = (
            f'\n8. The user is currently watching a video titled "{video_title}". '
            'Use this information to inform the "source" field and to provide '
            'better context for the note title.\n'
        )

    system_prompt = f"""You are Klippa, an AI note-taking assistant. Your job is to create beautiful, well-structured Markdown notes from audio transcripts.

RULES:
1. The user will provide two things:
   - SYSTEM AUDIO: A transcript of what was playing (podcast, lecture, video, etc.)
   - USER COMMAND: What the user asked you to note down

2. Based on the user's command, find the relevant portion of the system audio transcript and use the speaker's exact words. Do NOT paraphrase, reword, or summarize in your own style. Copy the relevant text from the transcript verbatim, preserving the speaker's original phrasing and word choices.

3. Format guidelines:
   - Use a clear, descriptive title (H1 is NOT needed - title is separate)
   - Use ## for main sections
   - Use > blockquotes for direct quotes, hadiths, or important statements
   - Use bullet points for key takeaways
   - Use **bold** for emphasis on important terms
   - Use *italics* for book titles, references, Arabic transliterations
   - Use LaTeX ($...$) for any mathematical formulas
   - Use code blocks for any code or technical content
   - Use tables when comparing things or presenting structured data
   - Use --- for section separators when appropriate

4. For Islamic content: include Arabic transliteration, reference the source (Sahih al-Bukhari, Sahih Muslim, etc.) when identifiable, and use respectful conventions (e.g., peace be upon him).

5. For academic/math content: use proper LaTeX notation.

6. CRITICAL: You must use the transcript's exact wording. Do not rephrase, do not write in your own style, and do not invent content. The note should read as if the speaker wrote it, not you. Use blockquote formatting (>) to present verbatim transcript excerpts.

7. Return your response as JSON with exactly these keys:
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

    import json
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw)


def _arabic_char_ratio(text: str) -> float:
    """Return the fraction of characters in text that are Arabic script."""
    if not text:
        return 0.0
    arabic = sum(1 for ch in text if '\u0600' <= ch <= '\u06FF' or '\u0750' <= ch <= '\u077F' or '\uFB50' <= ch <= '\uFDFF' or '\uFE70' <= ch <= '\uFEFF')
    return arabic / len(text)


def arabize_content(content: str) -> str:
    """
    Post-process note content: find specific Arabic/Islamic terms written in
    Latin script (transliterations) and replace them with Arabic script.
    Returns the original content unchanged if the conversion goes wrong.
    """
    client = _get_client()

    system_prompt = """You are a careful Arabic-language post-processor. You will receive a note written primarily in English. Your ONLY job is to find specific well-known Arabic or Islamic terms that have been transliterated into Latin/English letters and replace ONLY those terms with Arabic script.

CRITICAL RULES — READ CAREFULLY:

1. DO NOT TRANSLATE. The text is in English. All English words and sentences MUST stay in English. You are NOT a translator. You are only swapping individual Arabic terms.

2. ONLY convert words that are clearly well-known Arabic/Islamic terms written with English letters. Examples of terms to convert:
   - "dalil" -> "دليل"
   - "hadith" -> "حديث"
   - "Musnad" -> "مسند"
   - "Rasulullah" or "Rasulu Allah" -> "رسول الله"
   - "S.A.W." or "sallallahu alayhi wa sallam" -> "ﷺ"
   - "subhanahu wa ta'ala" -> "سبحانه وتعالى"
   - "sunnah" -> "سنة"
   - "fiqh" -> "فقه"
   - "ummah" -> "أمة"
   - "dua" -> "دعاء"
   - "salah" -> "صلاة"
   - "zakat" -> "زكاة"
   - "hajj" -> "حج"
   - "Sahih al-Bukhari" -> "صحيح البخاري"
   - "Sahih Muslim" -> "صحيح مسلم"
   - "Quran" -> "القرآن"
   - "Imam Ahmad" -> "الإمام أحمد"

3. You MUST consider context before converting any word. A word that looks Arabic might not be Arabic depending on context:
   - "manga" in the context of anime/cartoons/comics = Japanese word, DO NOT convert
   - "manga" in the context of fruit = Arabic word (مانجا), convert
   - Always look at the surrounding sentence to determine if a word is genuinely an Arabic term or belongs to another language

4. DO NOT convert these kinds of words — they must stay as-is:
   - Normal English words, even if the topic is Islamic (e.g., "prayer", "charity", "fasting", "pilgrimage", "proof", "evidence", "knowledge", "scholar", "student", "wife", "children", "money", "school")
   - English descriptions or explanations of Islamic concepts
   - Numbers, dollar amounts, or any non-Arabic content
   - Names of people when used in normal English context (e.g., "Ahmad said..." should stay English unless it's part of a hadith reference like "Musnad of Imam Ahmad")

5. The output must be the SAME text with only a few individual Arabic terms swapped. The vast majority of the text must remain unchanged. If the input is 90% English, the output must also be 90% English.

6. Preserve ALL markdown syntax exactly as-is (headings, bold, italics, blockquotes, bullet points, etc.).

7. Return ONLY the modified text. No explanations, no commentary, no wrapping."""

    input_arabic_ratio = _arabic_char_ratio(content)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        temperature=0.1,
        max_tokens=3000,
    )

    result = response.choices[0].message.content.strip()

    output_arabic_ratio = _arabic_char_ratio(result)
    arabic_increase = output_arabic_ratio - input_arabic_ratio
    if arabic_increase > 0.3:
        print(f"[Klippa] Arabize safety check failed: Arabic ratio jumped from "
              f"{input_arabic_ratio:.1%} to {output_arabic_ratio:.1%}, discarding")
        return content

    return result
