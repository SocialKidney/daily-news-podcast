"""Unit tests for audio processing, chunking, sanitization, and ffmpeg."""

import wave
import io
import pytest
from utils.audio_utils import (
    sanitize_text_for_tts,
    chunk_script_for_tts,
    pcm_to_wav_bytes,
    get_ffmpeg_path,
)


def test_sanitize_text_for_tts():
    raw_script = """
    # Episode 42: Morning Update
    **Good morning**, listeners! [Upbeat Theme Music Fades]
    Today we look at *crucial* news in Edmonton. (Host chuckles)
    - First item: Transit delays
    - Second item: Budget talks
    For more info check https://cbc.ca/news right now.
    """
    cleaned = sanitize_text_for_tts(raw_script)

    # Asserts that markdown and cues are stripped
    assert "# Episode" not in cleaned
    assert "[Upbeat Theme Music Fades]" not in cleaned
    assert "(Host chuckles)" not in cleaned
    assert "**Good morning**" not in cleaned
    assert "Good morning, listeners!" in cleaned
    assert "https://cbc.ca/news" not in cleaned
    assert "*crucial*" not in cleaned


def test_chunk_script_for_tts():
    # Construct a script with 600 words
    sentences = [
        f"Sentence number {i} provides essential context for the daily morning briefing."
        for i in range(60)
    ]
    script = " ".join(sentences)

    chunks = chunk_script_for_tts(script, max_words=100)
    assert len(chunks) > 1

    # Ensure no chunk exceeds significantly past the max_words
    for chunk in chunks:
        words = chunk.split()
        assert len(words) <= 120
        # Ensure it ends with punctuation
        assert chunk[-1] in ".!?"


def test_pcm_to_wav_bytes():
    # 1 second of silence at 24000Hz, 16-bit (2 bytes per sample), mono (1 channel)
    pcm_dummy = b"\x00" * 48000
    wav_bytes = pcm_to_wav_bytes(pcm_dummy, sample_rate=24000, channels=1, sample_width=2)

    assert wav_bytes.startswith(b"RIFF")
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() == 24000


def test_ffmpeg_detection():
    ffmpeg_exe = get_ffmpeg_path()
    assert ffmpeg_exe is not None
    assert "ffmpeg" in ffmpeg_exe.lower()
