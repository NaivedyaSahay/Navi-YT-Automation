"""
voice_generator.py
------------------
Converts text to a high-quality MP3 voiceover using Microsoft Edge TTS.
Also estimates word-level timing data for caption rendering.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import edge_tts

import config

logger = logging.getLogger("voice_generator")


# ── Internal async worker ─────────────────────────────────────────────────────

async def _synthesize(
    text: str, output_path: Path, voice: str, rate: str, volume: str
) -> None:
    """Save TTS audio to output_path using edge-tts streaming."""
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
    with open(str(output_path), "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
    logger.info("Voiceover saved to: %s", output_path)


# ── Word timing estimator ─────────────────────────────────────────────────────

def _estimate_word_timings(text: str, audio_duration: float) -> list[dict]:
    """
    Estimate per-word timings by distributing audio duration proportionally
    across words based on their character length (longer words take more time).

    Returns list of {"word", "start", "end"} with times in seconds.
    """
    words = text.split()
    if not words or audio_duration <= 0:
        return []

    # Weight each word by character length (approximates speaking time)
    weights   = [max(len(w), 1) for w in words]
    total_w   = sum(weights)
    # Small silence padding at start (~0.3s) and between words (~0.05s)
    usable    = audio_duration - 0.3
    timings   = []
    cursor    = 0.3   # start after initial silence

    for word, weight in zip(words, weights):
        duration = usable * (weight / total_w)
        timings.append({
            "word":  word,
            "start": round(cursor, 3),
            "end":   round(cursor + duration, 3),
        })
        cursor += duration

    logger.info("Estimated %d word timings over %.2f s", len(timings), audio_duration)
    return timings


# ── Public API ────────────────────────────────────────────────────────────────

def generate_voiceover(
    text: str,
    output_path: Path | None = None,
    voice: str | None = None,
    rate: str | None = None,
    volume: str | None = None,
) -> tuple[Path, list[dict]]:
    """
    Convert *text* to an MP3 voiceover and return (audio_path, word_timings).

    word_timings is a list of {"word": str, "start": float, "end": float}
    where start/end are in seconds. Timings are estimated from audio duration.
    """
    output_path = Path(output_path or config.AUDIO_FILE)
    voice  = voice  or config.TTS_VOICE
    rate   = rate   or config.TTS_RATE
    volume = volume or config.TTS_VOLUME

    if not text or not text.strip():
        raise ValueError("Cannot generate voiceover for empty text.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Generating voiceover | voice=%s | rate=%s | length=%d chars",
        voice, rate, len(text),
    )

    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio  # type: ignore
                nest_asyncio.apply()
                loop.run_until_complete(_synthesize(text, output_path, voice, rate, volume))
            else:
                loop.run_until_complete(_synthesize(text, output_path, voice, rate, volume))
        except RuntimeError:
            asyncio.run(_synthesize(text, output_path, voice, rate, volume))

    except Exception as exc:
        logger.error("TTS generation failed: %s", exc)
        raise RuntimeError(f"Edge TTS error: {exc}") from exc

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"TTS produced an empty or missing file: {output_path}")

    # Get actual audio duration using mutagen or moviepy
    audio_duration = _get_audio_duration(output_path)

    logger.info(
        "Voiceover ready: %s (%.1f KB) | duration: %.2f s",
        output_path,
        output_path.stat().st_size / 1024,
        audio_duration,
    )

    word_timings = _estimate_word_timings(text, audio_duration)
    return output_path, word_timings


def _get_audio_duration(path: Path) -> float:
    """Get audio duration in seconds using moviepy."""
    try:
        from moviepy import AudioFileClip
        clip = AudioFileClip(str(path))
        dur  = clip.duration
        clip.close()
        return dur
    except Exception:
        # Rough fallback: ~150 words per minute
        return 0.0


def list_voices() -> None:
    """Print all available Edge TTS voices to stdout."""
    async def _list():
        voices = await edge_tts.list_voices()
        for v in voices:
            print(f"{v['ShortName']:40s}  {v['Locale']}  {v['Gender']}")
    asyncio.run(_list())


if __name__ == "__main__":
    path, timings = generate_voiceover("Hello! This is a test of the Edge TTS voiceover system.")
    print(f"Generated: {path} | words: {len(timings)}")
    for t in timings[:5]:
        print(f"  {t['word']:15s} {t['start']:.2f}s -> {t['end']:.2f}s")
