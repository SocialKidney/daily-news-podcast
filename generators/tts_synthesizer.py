"""Audio synthesis module using Gemini Speech Generation with chunking and MP3 stitching."""

import os
import io
import base64
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from pydub import AudioSegment

from config import config
from utils.audio_utils import (
    chunk_script_for_tts,
    pcm_to_wav_bytes,
    stitch_audio_segments,
    export_audio_to_mp3,
)

logger = logging.getLogger(__name__)


class TTSSynthesizer:
    """Synthesizes conversational scripts into high-quality MP3 podcast audio."""

    def __init__(self, api_key: str = "", voice_name: str = ""):
        self.api_key = api_key or config.gemini_api_key
        self.voice_name = voice_name or getattr(config, "default_voice_name", getattr(config, "voice_name", "Kore"))
        self.client = None
        if self.api_key:
            try:
                from google import genai

                self.client = genai.Client(api_key=self.api_key)
                logger.info(
                    "Initialized GenAI client for TTS with voice '%s'", self.voice_name
                )
            except Exception as e:
                logger.warning("Could not initialize GenAI client for TTS: %s", e)

    def synthesize_script_to_mp3(
        self,
        script_text: str,
        output_path: Optional[Path] = None,
        date_str: str = "",
    ) -> Path:
        """
        Chunk the script, synthesize each chunk, stitch them seamlessly,
        and export to a final MP3 podcast file.
        """
        if not output_path:
            datestamp = date_str or datetime.now().strftime("%Y%m%d")
            output_path = config.output_dir / f"podcast_{datestamp}.mp3"

        # If edge-tts engine is selected (default), synthesize with Edge Neural TTS
        if config.tts_engine in ("edge", "edgetts"):
            try:
                return self._synthesize_script_edge(script_text, output_path)
            except Exception as e:
                logger.warning("edge-tts failed (%s). Falling back to chunked synthesis.", e)

        # Split script into manageable natural speech chunks
        chunks = chunk_script_for_tts(script_text, max_words=250)
        logger.info(
            "Script segmented into %d chunks for speech synthesis.", len(chunks)
        )

        audio_segments: List[AudioSegment] = []

        # Determine preferred engine
        use_gemini = (
            config.tts_engine == "gemini" and self.client is not None and self.api_key
        )

        for i, chunk in enumerate(chunks, 1):
            logger.info(
                "Synthesizing chunk %d/%d (%d words)...",
                i,
                len(chunks),
                len(chunk.split()),
            )

            segment: Optional[AudioSegment] = None
            if use_gemini:
                try:
                    segment = self._synthesize_chunk_gemini(chunk)
                except Exception as e:
                    logger.warning(
                        "Gemini TTS failed on chunk %d (%s). Falling back to gTTS.",
                        i,
                        e,
                    )
                    segment = self._synthesize_chunk_gtts(chunk)
            else:
                segment = self._synthesize_chunk_gtts(chunk)

            if segment:
                audio_segments.append(segment)

        if not audio_segments:
            raise RuntimeError("Failed to synthesize any audio segments.")

        logger.info("Stitching %d audio segments together...", len(audio_segments))
        final_audio = stitch_audio_segments(audio_segments, pause_ms=350)

        # Export to MP3
        final_mp3 = export_audio_to_mp3(
            final_audio, output_path, bitrate="128k"
        )
        logger.info(
            "Podcast successfully synthesized: %s (Duration: %.1f seconds)",
            final_mp3,
            len(final_audio) / 1000.0,
        )
        return final_mp3

    def _synthesize_chunk_gemini(self, text_chunk: str) -> AudioSegment:
        """Synthesize text chunk via Gemini TTS Preview API."""
        prompt = f"Say naturally and engagingly: {text_chunk}"
        tts_models = ["gemini-2.5-flash-preview-tts", "gemini-3.1-flash-tts-preview"]
        last_error = None

        for model_name in tts_models:
            try:
                interaction = self.client.interactions.create(
                    model=model_name,
                    input=prompt,
                    response_format={"type": "audio"},
                    generation_config={
                        "speech_config": [{"voice": self.voice_name}]
                    },
                )
                if interaction.output_audio and interaction.output_audio.data:
                    pcm_bytes = base64.b64decode(interaction.output_audio.data)
                    wav_bytes = pcm_to_wav_bytes(
                        pcm_bytes, sample_rate=24000, channels=1, sample_width=2
                    )
                    return AudioSegment.from_file(io.BytesIO(wav_bytes), format="wav")
            except Exception as e:
                last_error = e
                logger.debug("TTS model %s failed: %s", model_name, e)

        raise RuntimeError(f"All Gemini TTS models failed: {last_error}")

    def _synthesize_chunk_gtts(self, text_chunk: str) -> AudioSegment:
        """Synthesize text chunk using gTTS and convert via ffmpeg without requiring ffprobe."""
        from gtts import gTTS
        from utils.audio_utils import convert_mp3_to_wav_bytes

        # Use Canadian English accent if possible (tld='ca')
        tts = gTTS(text=text_chunk, lang="en", tld="ca", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        mp3_bytes = buf.getvalue()

        # Convert MP3 to WAV using ffmpeg directly (bypasses ffprobe requirement)
        wav_bytes = convert_mp3_to_wav_bytes(mp3_bytes, sample_rate=24000)
        return AudioSegment.from_file(io.BytesIO(wav_bytes), format="wav")

    def _resolve_edge_voice(self, voice_name: str) -> str:
        """Map generic or Gemini voice names to premium Edge Neural voices."""
        mapping = {
            "kore": "en-CA-LiamNeural",
            "puck": "en-US-ChristopherNeural",
            "aoede": "en-US-AriaNeural",
            "liam": "en-CA-LiamNeural",
            "clara": "en-CA-ClaraNeural",
            "christopher": "en-US-ChristopherNeural",
            "brian": "en-US-BrianNeural",
            "aria": "en-US-AriaNeural",
            "ava": "en-US-AvaNeural",
        }
        name_lower = voice_name.lower().strip()
        if "neural" in name_lower:
            return voice_name
        return mapping.get(name_lower, "en-CA-LiamNeural")

    def _synthesize_script_edge(self, script_text: str, output_path: Path) -> Path:
        """Synthesize conversational script using high-definition Microsoft Edge Neural TTS."""
        import asyncio
        import edge_tts

        voice = self._resolve_edge_voice(self.voice_name)
        logger.info(
            "Synthesizing full script (%d words) via edge-tts with voice '%s'...",
            len(script_text.split()),
            voice,
        )

        async def _run():
            tts = edge_tts.Communicate(script_text, voice=voice)
            await tts.save(str(output_path))

        asyncio.run(_run())

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"edge-tts failed to produce file at {output_path}")

        filesize_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(
            "Podcast audio successfully synthesized via edge-tts: %s (Size: %.2f MB)",
            output_path,
            filesize_mb,
        )
        return output_path
