"""
video_composer.py
------------------
Assembles final 9:16 (1080x1920) Facebook & Instagram Reels video.
Combines:
  1. Stitched satisfying background video (kinetic sand, 3D loops, ASMR, etc.)
  2. Synthesized voiceover audio
  3. Dynamic high-contrast animated viral captions (Impact font + thick stroke)

Public API:
    output_path = compose_video(audio_path, word_timings, script_text, keywords)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    concatenate_audioclips,
    ImageClip,
    CompositeVideoClip,
)
from PIL import Image, ImageDraw, ImageFont

import config
import video_engine
from satisfying_video_manager import get_satisfying_background

logger = logging.getLogger("video_composer")

W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT  # 1080 x 1920
FPS  = config.VIDEO_FPS

def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Find available Devanagari/Hindi compatible font (Nirmala, Arial, Mangal)."""
    candidates = [
        ("C:/Windows/Fonts/Nirmala.ttc", 1 if bold else 0),
        ("C:/Windows/Fonts/nirmalab.ttf", 0),
        ("C:/Windows/Fonts/nirmala.ttf", 0),
        ("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf", 0),
        ("C:/Windows/Fonts/ariblk.ttf", 0),
        ("C:/Windows/Fonts/impact.ttf", 0),
        ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf", 0),
        ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", 0),
        ("/usr/share/fonts/truetype/fonts-deva-extra/gargi.ttf", 0),
        ("/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ]
    for item in candidates:
        p, idx = item if isinstance(item, tuple) else (item, 0)
        try:
            return ImageFont.truetype(p, size, index=idx)
        except Exception:
            continue
    return ImageFont.load_default()

def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        bbox = font.getbbox(test)
        w_px = bbox[2] - bbox[0]
        if w_px <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines

def _group_words_into_caption_chunks(
    word_timings: List[Dict[str, Any]], words_per_chunk: int = 3
) -> List[Dict[str, Any]]:
    """
    Group individual word timestamps into short, punchy 2-3 word caption phrases
    accurately synchronized with spoken words and natural speech pauses.
    """
    if not word_timings:
        return []

    chunks = []
    current_words = []

    for item in word_timings:
        current_words.append(item)
        w = str(item.get("word", "")).strip()

        # Break on punctuation or reaching target chunk size
        is_break_punct = bool(w and w[-1] in (".", "?", "!", ",", ";", ":", "-", "।"))
        if len(current_words) >= words_per_chunk or is_break_punct:
            cleaned_phrase = " ".join(
                re.sub(r"[.,?!:;—–।\-]", "", str(x.get("word", ""))).strip()
                for x in current_words
            ).strip()
            if cleaned_phrase:
                chunks.append({
                    "text": cleaned_phrase,
                    "start": current_words[0]["start"],
                    "end": current_words[-1]["end"],
                })
            current_words = []

    if current_words:
        cleaned_phrase = " ".join(
            re.sub(r"[.,?!:;—–।\-]", "", str(x.get("word", ""))).strip()
            for x in current_words
        ).strip()
        if cleaned_phrase:
            chunks.append({
                "text": cleaned_phrase,
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"],
            })

    # Only bridge tiny micro-gaps (<= 0.15s) to prevent flicker; do NOT stretch over speech pauses!
    for i in range(len(chunks) - 1):
        next_start = chunks[i + 1]["start"]
        cur_end = chunks[i]["end"]
        gap = next_start - cur_end
        if 0.0 < gap <= 0.15:
            chunks[i]["end"] = next_start

    return chunks

def _render_viral_caption_rgba(text: str) -> np.ndarray:
    """
    Renders text in viral YouTube Shorts / Reels style:
    - High-legibility Devanagari font (72px)
    - 8-direction thick black stroke outline
    - Vibrant yellow accent (#FFE620) and crisp white fill
    - Transparent RGBA canvas
    """
    cap_h = 280
    img = Image.new("RGBA", (W, cap_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if text:
        font = _get_font(72, bold=True)
        lines = _wrap_text(text, font, W - 120)
        line_h = 86
        tot_h = len(lines) * line_h
        text_y = (cap_h - tot_h) // 2

        stroke = 8  # thick black outline
        offsets = [
            (-stroke, -stroke), (0, -stroke), (stroke, -stroke),
            (-stroke, 0),                      (stroke, 0),
            (-stroke, stroke),  (0, stroke),  (stroke, stroke),
        ]

        for i, line in enumerate(lines):
            bbox = font.getbbox(line)
            x = (W - (bbox[2] - bbox[0])) // 2
            y = text_y + i * line_h

            # Draw black stroke outline
            for ox, oy in offsets:
                draw.text((x + ox, y + oy), line, font=font, fill=(0, 0, 0, 255))

            # Alternate between vivid golden yellow and pure white fill
            fill_color = (255, 230, 32, 255) if i % 2 == 0 else (255, 255, 255, 255)
            draw.text((x, y), line, font=font, fill=fill_color)

    return np.array(img)

def _prepare_bgm_clip(target_duration: float) -> AudioFileClip | None:
    """
    Loads and loops ambient background music to target_duration,
    scaling volume down to a subtle background bed (~3-4%) with smooth fades
    so the voiceover stays crisp, punchy, and prominent.
    """
    if not config.ENABLE_BGM or not config.BGM_DIR.exists():
        return None

    bgm_files = [
        f for f in config.BGM_DIR.iterdir()
        if f.suffix.lower() in (".mp3", ".wav", ".aac", ".m4a") and f.stat().st_size > 0
    ]
    if not bgm_files:
        return None

    import random
    import moviepy.audio.fx as afx
    bgm_path = random.choice(bgm_files)
    try:
        raw_bgm = AudioFileClip(str(bgm_path))
        clips = [raw_bgm]
        cur_dur = raw_bgm.duration
        while cur_dur < target_duration:
            clips.append(raw_bgm)
            cur_dur += raw_bgm.duration

        chained = concatenate_audioclips(clips) if len(clips) > 1 else raw_bgm
        bgm_vol = getattr(config, "BGM_VOLUME", 0.035)
        scaled_bgm = chained.subclipped(0, target_duration).with_volume_scaled(bgm_vol)
        try:
            scaled_bgm = scaled_bgm.with_effects([afx.AudioFadeIn(1.5), afx.AudioFadeOut(2.0)])
        except Exception:
            pass

        logger.info("Attached background music '%s' at subtle volume (%.1f%%).", bgm_path.name, bgm_vol * 100)
        return scaled_bgm
    except Exception as exc:
        logger.warning("Could not mix background music (%s). Continuing with voiceover only.", exc)
        return None


def compose_video(
    audio_path: Path,
    word_timings: List[Dict[str, Any]] = None,
    script_text: str = "",
    keywords: List[str] = None,
    image_prompts: List[str] = None,
    scene_ratios: List[float] = None,
    output_path: Path | None = None,
) -> Path:
    """
    Compose final video with satisfying visuals, audio, and dynamic captions.
    """
    output_path = Path(output_path or config.VIDEO_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Load and normalize voiceover audio to full prominence
    voice_clip = AudioFileClip(str(audio_path))
    duration = voice_clip.duration
    logger.info("Audio duration: %.2f seconds", duration)

    try:
        import moviepy.audio.fx as afx
        voice_clip = voice_clip.with_effects([afx.AudioNormalize()])
    except Exception:
        voice_clip = voice_clip.with_volume_scaled(1.3)

    # Prepare background music and layer with voiceover
    bgm_clip = _prepare_bgm_clip(duration)
    if bgm_clip:
        final_audio = CompositeAudioClip([voice_clip, bgm_clip])
    else:
        final_audio = voice_clip

    # 1. Calculate synchronized scene durations matching narrative beats
    clip_durations = None
    if scene_ratios and len(scene_ratios) >= 4:
        clip_durations = [duration * r for r in scene_ratios]
        logger.info("Synchronized scene durations to narrative beats: %s", [round(d, 2) for d in clip_durations])

    # 2. Fetch stitched visual background (100% AI mythological scenes with directional motion)
    bg_clip = get_satisfying_background(
        target_duration=duration,
        keywords=keywords,
        image_prompts=image_prompts,
        clip_durations=clip_durations,
    )

    # 3. Build caption overlay clips positioned in the lower-middle sweet spot (safe zone)
    caption_chunks = _group_words_into_caption_chunks(word_timings or [], words_per_chunk=3)
    if not caption_chunks:
        caption_chunks = [{"text": script_text[:60], "start": 0.0, "end": duration}]

    caption_clips = []
    cap_h = 280
    cap_y = int(H * 0.62)  # Lower-middle sweet spot (~1190px on 1920)

    for chunk in caption_chunks:
        c_start = max(0.0, chunk["start"])
        c_end = min(duration, chunk["end"])
        c_dur = max(0.15, c_end - c_start)

        cap_arr = _render_viral_caption_rgba(chunk["text"])
        cap_clip = (
            ImageClip(cap_arr)
            .with_position((0, cap_y))
            .with_start(c_start)
            .with_duration(c_dur)
        )
        caption_clips.append(cap_clip)

    # 4. Composite background + captions + audio
    logger.info("Compositing video background with %d synchronized caption chunks...", len(caption_clips))
    composite = CompositeVideoClip([bg_clip] + caption_clips, size=(W, H))
    final_video = composite.subclipped(0, duration).with_audio(final_audio)

    # 4. Render & write final MP4 video file via high-definition video engine
    try:
        video_engine.export_video_hd(
            clip=final_video,
            output_path=output_path,
            fps=FPS,
            codec=config.VIDEO_CODEC,
            audio_codec=config.AUDIO_CODEC,
            bitrate=config.VIDEO_BITRATE,
            audio_bitrate="192k",
            threads=4,
            preset="fast",
        )
    finally:
        try:
            voice_clip.close()
            if bgm_clip:
                bgm_clip.close()
            final_audio.close()
            final_video.close()
        except Exception:
            pass

    return output_path

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Video composer module ready.")
