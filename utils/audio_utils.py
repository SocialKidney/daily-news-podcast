"""Audio processing utilities: text chunking, ffmpeg detection, stitching, and MP3 conversion."""

import os
import re
import wave
import io
import shutil
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def get_ffmpeg_path() -> Optional[str]:
    """Find a usable ffmpeg executable from imageio-ffmpeg or system PATH."""
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception as e:
        logger.debug("imageio_ffmpeg not available: %s", e)

    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg

    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"),
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p

    return None


# Configure PATH with ffmpeg before importing pydub to suppress warnings
_ffmpeg_binary = get_ffmpeg_path()
if _ffmpeg_binary:
    ffmpeg_dir = str(Path(_ffmpeg_binary).parent)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{ffmpeg_dir}{os.pathsep}{os.environ.get('PATH', '')}"

from pydub import AudioSegment

if _ffmpeg_binary:
    AudioSegment.converter = _ffmpeg_binary
    logger.info("Configured pydub converter to: %s", _ffmpeg_binary)
else:
    logger.warning("No ffmpeg executable found. MP3 export may require system ffmpeg.")


def sanitize_text_for_tts(text: str) -> str:
    """Strip markdown symbols and non-spoken stage directions from podcast scripts."""
    if not text:
        return ""

    cleaned = text

    # Remove code blocks and inline code
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    cleaned = re.sub(r"`[^`]*`", "", cleaned)

    # Remove bracketed stage directions like [Intro music], [Pause], (Host chuckles)
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(r"\([A-Za-z\s]{3,30}\)", "", cleaned)

    # Remove markdown headers (# Title, ## Section) even with leading whitespace
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)

    # Remove bold, italics, strikethrough (*, _, ~)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    cleaned = re.sub(r"~~([^~]+)~~", r"\1", cleaned)

    # Remove bullet points and blockquotes
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*>\s+", "", cleaned, flags=re.MULTILINE)

    # Replace URLs with spoken reference
    cleaned = re.sub(r"https?://\S+", "", cleaned)

    # Clean multiple consecutive spaces and newlines
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)

    return cleaned.strip()


def chunk_script_for_tts(text: str, max_words: int = 280) -> List[str]:
    """
    Split script into natural paragraph and topic chunks so that synthesis
    and audio stitching occur cleanly between stories rather than mid-thought.
    """
    clean_text = sanitize_text_for_tts(text)
    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]

    chunks: List[str] = []

    for paragraph in paragraphs:
        words = paragraph.split()
        if len(words) <= max_words:
            chunks.append(paragraph)
        else:
            # Break large paragraph at natural sentence boundaries
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            current_chunk: List[str] = []
            current_word_count = 0

            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                sentence_words = len(sentence.split())
                if current_word_count + sentence_words > max_words and current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = [sentence]
                    current_word_count = sentence_words
                else:
                    current_chunk.append(sentence)
                    current_word_count += sentence_words

            if current_chunk:
                chunks.append(" ".join(current_chunk))

    return chunks


def pcm_to_wav_bytes(
    pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2
) -> bytes:
    """Convert raw PCM audio bytes to a WAV byte buffer."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def stitch_audio_segments(
    audio_segments: List[AudioSegment], pause_ms: int = 300, fade_ms: int = 40
) -> AudioSegment:
    """
    Seamlessly stitch audio segments with smooth micro-fades and natural pause
    to eliminate digital clipping, clicks, and abrupt transitions.
    """
    if not audio_segments:
        return AudioSegment.empty()

    pause = AudioSegment.silent(duration=pause_ms)
    
    # Apply soft fade-in/fade-out to avoid pop/clicks at chunk boundaries
    processed_segments = [
        seg.fade_in(fade_ms).fade_out(fade_ms) if len(seg) > (fade_ms * 2) else seg
        for seg in audio_segments
    ]

    combined = processed_segments[0]
    for seg in processed_segments[1:]:
        combined = combined + pause + seg

    return combined


def convert_mp3_to_wav_bytes(mp3_bytes: bytes, sample_rate: int = 24000) -> bytes:
    """Convert MP3 bytes to WAV bytes using ffmpeg directly (no ffprobe needed)."""
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg executable not found for MP3 conversion.")

    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as in_f:
        in_f.write(mp3_bytes)
        in_path = in_f.name

    out_path = in_path.replace(".mp3", ".wav")

    try:
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            in_path,
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-f",
            "wav",
            out_path,
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {res.stderr.decode('utf-8', errors='ignore')}")

        with open(out_path, "rb") as out_f:
            return out_f.read()
    finally:
        for p in [in_path, out_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


def export_audio_to_mp3(
    audio: AudioSegment, output_path: Path, bitrate: str = "128k"
) -> Path:
    """
    Export an AudioSegment to MP3 using ffmpeg directly.
    Bypasses pydub's ffprobe requirement by exporting to an intermediate WAV,
    then encoding with ffmpeg.
    """
    import subprocess
    import tempfile

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = get_ffmpeg_path()

    if not ffmpeg_exe:
        # Fallback to direct pydub export
        audio.export(str(output_path), format="mp3", bitrate=bitrate)
        logger.info("Successfully exported MP3 via pydub: %s", output_path)
        return output_path

    # Intermediate WAV export using pydub's native wave writer (no external tools required)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        tmp_wav_path = tmp_wav.name

    try:
        audio.export(tmp_wav_path, format="wav")
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            tmp_wav_path,
            "-b:a",
            bitrate,
            "-ar",
            "24000",
            str(output_path),
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            logger.warning(
                "ffmpeg MP3 encoding warning: %s",
                res.stderr.decode("utf-8", errors="ignore"),
            )
            # Try pydub direct export as fallback
            audio.export(str(output_path), format="mp3", bitrate=bitrate)
        logger.info("Successfully exported MP3 with ffmpeg to: %s", output_path)
        return output_path
    finally:
        if os.path.exists(tmp_wav_path):
            try:
                os.remove(tmp_wav_path)
            except Exception:
                pass
