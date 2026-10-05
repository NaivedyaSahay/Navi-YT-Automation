"""
voice_generator.py
------------------
Converts text scripts into natural voiceovers using Microsoft Edge TTS (edge-tts).
Extracts precise word-level timing data for synced dynamic caption rendering.

Public API:
    audio_path, word_timings = generate_voiceover(text="...", output_path=None)
    # Returns (Path to mp3, list of {"word": str, "start": float, "end": float})
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Tuple, List, Dict, Any

import edge_tts

import config

logger = logging.getLogger("voice_generator")


def _master_vocal_audio(raw_audio_path: Path) -> None:
    """
    Applies broadcast studio vocal mastering via FFmpeg:
      1. Low-end chest warmth EQ (130Hz +2.8dB)
      2. Vocal clarity & presence EQ (3.4kHz +2.0dB)
      3. Studio dynamic compressor to level volume peaks and valleys
      4. High-fidelity 44.1kHz stereo upsampling
    """
    temp_path = raw_audio_path.with_name(raw_audio_path.stem + "_raw_temp.mp3")
    try:
        if raw_audio_path.exists():
            raw_audio_path.rename(temp_path)
            af_filters = (
                "equalizer=f=130:width_type=o:w=1.2:g=2.8,"
                "equalizer=f=3400:width_type=o:w=1:g=2.0,"
                "acompressor=threshold=-16dB:ratio=3.5:attack=5:release=50,"
                "volume=1.15"
            )
            cmd = [
                "ffmpeg", "-y", "-i", str(temp_path),
                "-af", af_filters,
                "-ar", "44100",
                str(raw_audio_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and raw_audio_path.exists() and raw_audio_path.stat().st_size > 0:
                logger.info("Applied studio vocal mastering to voiceover audio.")
                temp_path.unlink(missing_ok=True)
            else:
                logger.warning("FFmpeg vocal mastering failed, retaining raw audio: %s", res.stderr)
                if temp_path.exists():
                    temp_path.rename(raw_audio_path)
    except Exception as exc:
        logger.warning("Vocal mastering exception (%s), retaining raw audio.", exc)
        if temp_path.exists() and not raw_audio_path.exists():
            temp_path.rename(raw_audio_path)


async def _synthesize_async(
    text: str, output_path: Path, voice: str, rate: str, pitch: str, volume: str
) -> List[Dict[str, Any]]:
    """Synthesize audio and collect word timing boundaries from edge_tts."""
    communicate = edge_tts.Communicate(
        text,
        voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
        boundary="WordBoundary",
    )
    submaker = edge_tts.SubMaker()
    word_timings = []

    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # Save word timing: start offset & duration in seconds
                w_text = chunk["text"]
                start_sec = chunk["offset"] / 10_000_000.0   # 100ns units to sec
                dur_sec   = chunk["duration"] / 10_000_000.0
                end_sec   = start_sec + dur_sec
                word_timings.append({
                    "word": w_text,
                    "start": round(start_sec, 3),
                    "end": round(end_sec, 3),
                })
            elif chunk["type"] == "sentence":
                submaker.feed(chunk)

    return word_timings


def _calculate_proportional_word_timings(text: str, audio_path: Path) -> List[Dict[str, Any]]:
    """Allocate duration proportionally by word character length."""
    words = text.split()
    if not words:
        return []

    actual_duration = None
    try:
        from moviepy import AudioFileClip
        with AudioFileClip(str(audio_path)) as ac:
            actual_duration = ac.duration
    except Exception:
        actual_duration = max(2.0, len(words) * 0.35)

    dur = actual_duration or (len(words) * 0.35)
    weights = [max(1, len(w)) for w in words]
    total_w = sum(weights)
    cur_time = 0.0
    timings = []
    for w, weight in zip(words, weights):
        w_dur = (weight / total_w) * dur
        timings.append({
            "word": w,
            "start": round(cur_time, 3),
            "end": round(cur_time + w_dur, 3),
        })
        cur_time += w_dur
    return timings


def _synthesize_sarvam(
    text: str,
    output_path: Path,
    speaker: str | None = None,
    pace: float = 0.95
) -> List[Dict[str, Any]]:
    """
    Synthesize authentic Indian storytelling speech using Sarvam AI (bulbul:v3).
    """
    import base64
    import requests

    speaker = speaker or config.SARVAM_SPEAKER
    logger.info("Generating voiceover via Sarvam AI [model=%s, speaker=%s, pace=%.2f]...",
                config.SARVAM_MODEL, speaker, pace)

    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": config.SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "model": config.SARVAM_MODEL,
        "speaker": speaker,
        "language_code": "hi-IN",
        "output_audio_codec": "mp3",
        "pace": pace
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=45)
    resp.raise_for_status()
    data = resp.json()

    audios = data.get("audios", [])
    if not audios:
        raise RuntimeError(f"Sarvam AI returned no audio payload: {data}")

    audio_bytes = base64.b64decode(audios[0])
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    # Calculate proportional word timings
    return _calculate_proportional_word_timings(text, output_path)


def _synthesize_gtts(text: str, output_path: Path) -> List[Dict[str, Any]]:
    """
    Synthesize speech using Google Translate Voice (gTTS) with Hindi (lang='hi').
    100% free, zero configuration, no API key required.
    """
    from gtts import gTTS
    logger.info("Generating voiceover via Google Translate Voice (gTTS [lang='hi'])...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(str(output_path))
    return _calculate_proportional_word_timings(text, output_path)


def _clean_tts_script(text: str) -> str:
    """Pre-processes Hindi text to ensure 100% natural, clear pronunciation for TTS."""
    import re
    # Remove markdown formatting like **bold** or *italic*
    cleaned = re.sub(r"\*+", "", text)
    # Replace em-dashes or en-dashes with natural pauses/commas
    cleaned = cleaned.replace("—", ", ").replace("–", ", ").replace("-", " ")
    # Replace multiple dots or ellipses with single comma/pause
    cleaned = re.sub(r"\.{2,}", ", ", cleaned)
    # Remove stage directions or brackets [Scene 1] etc.
    cleaned = re.sub(r"\[.*?\]|\(.*?\)", "", cleaned)
    # Remove quotes, backticks, or unusual symbols
    cleaned = re.sub(r"[\"\'`“”‘’~_#@^]", "", cleaned)
    # Normalize multiple whitespace and commas
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def generate_voiceover(
    text: str,
    output_path: Path | None = None,
    voice: str | None = None,
    rate: str | None = None,
    pitch: str | None = None,
    volume: str | None = None,
) -> Tuple[Path, List[Dict[str, Any]]]:
    """
    Generate voiceover MP3 and return (audio_path, word_timings).
    Primary: Sarvam AI (authentic Indian storytelling)
    1st Fallback: gTTS (Google Translate Voice - lang='hi')
    2nd Fallback: Edge-TTS (Microsoft Neural Voice)
    """
    # Clean text to ensure clear pronunciation and natural rhythm
    clean_text = _clean_tts_script(text)
    output_path = Path(output_path or config.AUDIO_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    word_timings: List[Dict[str, Any]] = []
    used_provider: str | None = None

    # 1. Primary: Edge-TTS when accurate WordBoundary timestamps are needed (default)
    # Edge-TTS provides native millisecond word timestamps directly from neural synthesizer
    if config.TTS_PROVIDER in ("edge-tts", "auto"):
        v = voice or config.TTS_VOICE
        r = rate or config.TTS_RATE
        p = pitch or config.TTS_PITCH
        vol = volume or config.TTS_VOLUME

        # Auto-detect Devanagari/Hindi script and ensure Hindi voice
        if any("\u0900" <= ch <= "\u097f" for ch in text) and v.startswith("en-"):
            logger.warning(
                "Detected Hindi Devanagari script with English voice '%s'. Automatically using 'hi-IN-SwaraNeural'.",
                v,
            )
            v = "hi-IN-SwaraNeural"

        logger.info("Generating voiceover via Edge-TTS [voice=%s, rate=%s, pitch=%s] with exact WordBoundary timestamps...", v, r, p)

        try:
            word_timings = asyncio.run(_synthesize_async(clean_text, output_path, v, r, p, vol))
            used_provider = "edge-tts"
            logger.info("Edge-TTS voiceover complete (%d exact word timestamps captured).", len(word_timings))
        except Exception as exc:
            logger.warning("Edge-TTS failed (%s). Falling back to Sarvam AI...", exc)

    # 2. Sarvam AI (if explicitly set or as fallback)
    if not used_provider and (config.TTS_PROVIDER == "sarvam" or config.SARVAM_API_KEY):
        if config.SARVAM_API_KEY:
            try:
                word_timings = _synthesize_sarvam(clean_text, output_path)
                used_provider = "sarvam"
            except Exception as exc:
                logger.warning("Sarvam AI synthesis failed (%s). Falling back to gTTS...", exc)

    # 3. Emergency Fallback: gTTS
    if not used_provider:
        logger.info("Attempting emergency gTTS fallback...")
        try:
            word_timings = _synthesize_gtts(clean_text, output_path)
            used_provider = "gtts"
        except Exception as gexc:
            logger.error("All TTS synthesis engines failed: %s", gexc)
            raise RuntimeError(f"All TTS engines failed: {gexc}") from gexc

    if not word_timings:
        word_timings = _calculate_proportional_word_timings(clean_text, output_path)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Generated audio file missing or empty: {output_path}")

    # Apply studio vocal mastering (warmth EQ, presence boost, dynamic compression)
    _master_vocal_audio(output_path)

    logger.info("Voiceover ready: %s (%.1f KB, %d word timestamps)",
                output_path, output_path.stat().st_size / 1024, len(word_timings))

    return output_path, word_timings


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path, timings = generate_voiceover("This is a test of the satisfying video voice generator.")
    print(f"Generated: {path}, Timings count: {len(timings)}")
