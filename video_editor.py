"""
video_editor.py
---------------
Assembles the final 9:16 (1080x1920) YouTube Shorts video.

Priority:
  1. Pexels stock footage (PEXELS_API_KEY) + caption overlay
  2. Pixabay stock footage (PIXABAY_API_KEY) + caption overlay
  3. Gradient background + large text + caption overlay
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path
from typing import Optional

import numpy as np
import requests
from moviepy import (
    AudioFileClip,
    ColorClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
)
from PIL import Image, ImageDraw, ImageFont

import config

logger = logging.getLogger("video_editor")

W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT   # 1080 x 1920
FPS  = config.VIDEO_FPS

# ── Colour palettes (top_rgb, bottom_rgb) ─────────────────────────────────────
PALETTES = [
    ((15, 10,  55), (75,  20, 115)),
    ((10, 35,  80), (20,  85, 155)),
    ((50,  8,   8), (120, 35,  18)),
    ((10, 40,  10), (25, 105,  55)),
    ((55, 15,  75), (20,  60, 140)),
    ((70, 30,   5), (130, 75,  10)),
    ((12, 45,  55), (20, 110, 110)),
    ((40,  5,  55), (90,  15,  90)),
]


# ── Font helpers ──────────────────────────────────────────────────────────────

def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    # Impact is the #1 viral Shorts font — punchy and easy to read
    candidates = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/ariblk.ttf",   # Arial Black
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/verdanab.ttf" if bold else "C:/Windows/Fonts/verdana.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if font.getbbox(test)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ── Caption / text grouping ───────────────────────────────────────────────────

def _group_captions(word_timings: list[dict], words_per_chunk: int = 5) -> list[dict]:
    if not word_timings:
        return []
    chunks = []
    for i in range(0, len(word_timings), words_per_chunk):
        group = word_timings[i: i + words_per_chunk]
        chunks.append({
            "text":  " ".join(w["word"] for w in group),
            "words": group,
            "start": group[0]["start"],
            "end":   group[-1]["end"],
        })
    return chunks


def _split_script_sections(script: str, n: int) -> list[str]:
    sentences = [s.strip() for s in script.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if not sentences:
        return [script]
    size = max(1, len(sentences) // max(n, 1))
    sections = []
    for i in range(0, len(sentences), size):
        sections.append(". ".join(sentences[i: i + size]) + ".")
    return sections[:n] if len(sections) >= n else sections


# ── Frame renderers ───────────────────────────────────────────────────────────

def _draw_text_with_shadow(draw, xy, text, font, fill=(255, 255, 255), offset=3, shadow=(0, 0, 0, 200)):
    draw.text((xy[0] + offset, xy[1] + offset), text, font=font, fill=shadow)
    draw.text(xy, text, font=font, fill=fill)


def _render_gradient_frame(palette: tuple, section_text: str, caption_text: str) -> np.ndarray:
    """Full gradient frame with section text and caption."""
    top_col, bot_col = palette
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=(
            int(top_col[0] * (1 - t) + bot_col[0] * t),
            int(top_col[1] * (1 - t) + bot_col[1] * t),
            int(top_col[2] * (1 - t) + bot_col[2] * t),
        ))

    # Section text in center
    if section_text:
        font  = _get_font(54, bold=True)
        lines = _wrap_text(section_text, font, int(W * 0.82))
        line_h = 68
        start_y = H // 2 - (len(lines) * line_h) // 2 - 80
        for i, line in enumerate(lines):
            bbox = font.getbbox(line)
            x = (W - (bbox[2] - bbox[0])) // 2
            _draw_text_with_shadow(draw, (x, start_y + i * line_h), line, font)

    # Caption bar at bottom
    if caption_text:
        _draw_caption_on(img, caption_text)

    return np.array(img)


def _draw_caption_on(img: Image.Image, caption_text: str) -> None:
    """Draw a caption bar at the bottom of a PIL image (in-place)."""
    bar_h = 190
    bar_y = H - bar_h - 55
    draw  = ImageDraw.Draw(img, "RGBA")
    draw.rounded_rectangle([30, bar_y, W - 30, bar_y + bar_h], radius=22, fill=(0, 0, 0, 200))

    font   = _get_font(62, bold=True)
    lines  = _wrap_text(caption_text.upper(), font, W - 100)
    line_h = 76
    text_y = bar_y + (bar_h - len(lines) * line_h) // 2
    draw2  = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        x    = (W - (bbox[2] - bbox[0])) // 2
        y    = text_y + i * line_h
        draw2.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 220))
        draw2.text((x, y), line, font=font, fill=(255, 230, 50))


def _render_caption_bar_rgba(caption_text: str) -> np.ndarray:
    """
    Render caption as viral-Shorts style:
    - Impact font, large size
    - White text with thick black stroke (8-direction shadow)
    - Transparent background (no dark box)
    Returns RGBA numpy array (cap_h x W x 4).
    """
    cap_h  = 280          # tall enough for 2 lines
    img    = Image.new("RGBA", (W, cap_h), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)

    if caption_text:
        font   = _get_font(82, bold=True)     # Impact at 82px
        lines  = _wrap_text(caption_text.upper(), font, W - 80)
        line_h = 95
        tot_h  = len(lines) * line_h
        text_y = (cap_h - tot_h) // 2

        stroke = 7   # stroke thickness in pixels
        offsets = [
            (-stroke, -stroke), (0, -stroke), (stroke, -stroke),
            (-stroke, 0),                      (stroke, 0),
            (-stroke,  stroke), (0,  stroke), (stroke,  stroke),
        ]

        for i, line in enumerate(lines):
            bbox = font.getbbox(line)
            x    = (W - (bbox[2] - bbox[0])) // 2
            y    = text_y + i * line_h

            # Draw black stroke (8 directions)
            for ox, oy in offsets:
                draw.text((x + ox, y + oy), line, font=font, fill=(0, 0, 0, 255))

            # Draw white fill on top
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

    return np.array(img)


# ── Stock footage helpers ─────────────────────────────────────────────────────

def _download_pexels_clip(url: str, dest: Path, headers: dict) -> bool:
    """Download a single Pexels video file. Returns True on success."""
    try:
        dl = requests.get(url, headers=headers, stream=True, timeout=60)
        dl.raise_for_status()
        with open(str(dest), "wb") as f:
            for chunk in dl.iter_content(chunk_size=1024 * 64):
                f.write(chunk)
        return dest.stat().st_size > 10_000   # at least 10 KB = real video
    except Exception as exc:
        logger.debug("Clip download failed: %s", exc)
        return False


def _search_pexels(query: str, headers: dict, per_page: int = 5) -> list[str]:
    """Search Pexels and return a list of portrait video URLs."""
    urls = []
    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": query, "orientation": "portrait", "size": "medium", "per_page": per_page},
            timeout=15,
        )
        resp.raise_for_status()
        for video in resp.json().get("videos", []):
            files    = video.get("video_files", [])
            portrait = [f for f in files if f.get("height", 0) >= f.get("width", 1)] or files
            if portrait:
                urls.append(portrait[0]["link"])
    except Exception as exc:
        logger.debug("Pexels search '%s' failed: %s", query, exc)
    return urls


def _fetch_pexels_clips(keywords: list[str], duration: float, max_clips: int = 5) -> list[Path]:
    """
    Download multiple different Pexels clips using varied keyword queries.
    Returns a list of saved clip paths.
    """
    if not config.PEXELS_API_KEY:
        return []

    headers = {"Authorization": config.PEXELS_API_KEY}

    # Build a diverse set of search queries from keywords
    queries = []
    kw = keywords[:4] if len(keywords) >= 4 else keywords + keywords  # pad if short
    queries.append(" ".join(kw[:2]))          # e.g. "mind psychology"
    queries.append(kw[0])                     # e.g. "mind"
    if len(kw) > 1: queries.append(kw[1])    # e.g. "psychology"
    if len(kw) > 2: queries.append(kw[2])    # e.g. "science"
    if len(kw) > 3: queries.append(" ".join(kw[2:4]))  # e.g. "science human"
    queries = list(dict.fromkeys(queries))    # deduplicate, preserve order

    saved: list[Path] = []
    used_urls: set[str] = set()

    for i, query in enumerate(queries):
        if len(saved) >= max_clips:
            break
        urls = _search_pexels(query, headers, per_page=3)
        for url in urls:
            if url in used_urls:
                continue
            used_urls.add(url)
            dest = config.OUTPUT_DIR / f"bg_{i}_{len(saved)}.mp4"
            logger.info("Downloading clip #%d [%s]: %s", len(saved) + 1, query, url)
            if _download_pexels_clip(url, dest, headers):
                saved.append(dest)
                break   # one clip per query is enough

    logger.info("Downloaded %d Pexels clips.", len(saved))
    return saved


def _fetch_pixabay_clip(keywords: list[str], duration: float) -> Optional[Path]:
    if not config.PIXABAY_API_KEY:
        return None
    query  = "+".join(keywords[:2])
    params = {"key": config.PIXABAY_API_KEY, "q": query,
              "video_type": "film", "orientation": "vertical", "per_page": 5}
    try:
        resp = requests.get("https://pixabay.com/api/videos/", params=params, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if hits:
            dest = config.BG_VIDEO_FILE
            urllib.request.urlretrieve(hits[0]["videos"]["medium"]["url"], str(dest))
            return dest
    except Exception as exc:
        logger.warning("Pixabay fetch failed: %s", exc)
    return None


def _stitch_footage(clip_paths: list[Path], duration: float):
    """
    Load multiple clips, resize to (W x H), and concatenate them.
    If combined duration is still shorter than needed, loop the whole sequence.
    Returns a single VideoFileClip-like object trimmed to `duration`.
    """
    clips = []
    for p in clip_paths:
        try:
            c = VideoFileClip(str(p), audio=False).resized((W, H)).with_fps(FPS)
            clips.append(c)
        except Exception as exc:
            logger.warning("Could not load clip %s: %s", p, exc)

    if not clips:
        return None

    # Concatenate all clips
    combined = concatenate_videoclips(clips)

    # If still shorter than audio, loop the whole combined footage
    if combined.duration < duration:
        loops = int(np.ceil(duration / combined.duration))
        combined = concatenate_videoclips([combined] * loops)

    return combined.subclipped(0, duration)


# ── Segment-based clip builder (gradient fallback) ────────────────────────────

def _build_gradient_clips(caption_chunks, duration, script_text):
    n_sections   = max(1, len(caption_chunks) // 3)
    sections     = _split_script_sections(script_text, n_sections) if script_text else [""]
    palette_step = max(1, len(PALETTES) // max(n_sections, 1))

    last_end  = caption_chunks[-1]["end"] if caption_chunks else duration
    tail_dur  = max(0.0, duration - last_end)

    def _sd(c):
        return max(0.05, c["end"] - c["start"])

    raw_total = sum(_sd(c) for c in caption_chunks) + tail_dur
    scale     = duration / raw_total if raw_total > 0 else 1.0

    clips = []
    for idx, chunk in enumerate(caption_chunks):
        sec_idx = min(idx // 3, len(sections) - 1)
        pal_idx = (sec_idx * palette_step) % len(PALETTES)
        frame   = _render_gradient_frame(PALETTES[pal_idx], sections[sec_idx], chunk["text"])
        clips.append(ImageClip(frame, duration=_sd(chunk) * scale).with_fps(FPS))

    if tail_dur * scale > 0.05:
        frame = _render_gradient_frame(PALETTES[-1], "", "")
        clips.append(ImageClip(frame, duration=tail_dur * scale).with_fps(FPS))

    combined = concatenate_videoclips(clips)
    if combined.duration > duration + 0.1:
        combined = combined.subclipped(0, duration)
    return combined


# ── Main export function ──────────────────────────────────────────────────────

def create_video(
    audio_path: Path,
    keywords: list[str],
    output_path: Path | None = None,
    word_timings: list[dict] | None = None,
    script_text: str = "",
) -> Path:
    """Compose and export the final 9:16 video."""
    output_path = Path(output_path or config.VIDEO_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    audio_clip = AudioFileClip(str(audio_path))
    duration   = audio_clip.duration
    logger.info("Audio duration: %.2f s", duration)

    caption_chunks = _group_captions(word_timings or [], words_per_chunk=5)
    if not caption_chunks:
        caption_chunks = [{"text": "", "start": 0.0, "end": duration, "words": []}]

    # Build caption lookup for footage path
    def _caption_at(t: float) -> str:
        for chunk in caption_chunks:
            if chunk["start"] <= t <= chunk["end"]:
                return chunk["text"]
        return ""

    # ── Try stock footage (multiple clips) ───────────────────────────────────
    clip_paths = _fetch_pexels_clips(keywords, duration, max_clips=5)

    # Pixabay fallback (single clip) if Pexels returned nothing
    if not clip_paths:
        px = _fetch_pixabay_clip(keywords, duration)
        if px:
            clip_paths = [px]

    if clip_paths:
        try:
            logger.info("Stitching %d clips into background…", len(clip_paths))
            footage = _stitch_footage(clip_paths, duration)

            if footage is None:
                raise RuntimeError("All clips failed to load.")

            bar_h = 280          # caption height (matches _render_caption_bar_rgba)
            bar_y = H // 2 - bar_h // 2   # vertical center of screen

            # One RGBA caption ImageClip per chunk, positioned at bottom of screen
            cap_clips = []
            for chunk in caption_chunks:
                chunk_dur = max(0.1, chunk["end"] - chunk["start"])
                bar_arr   = _render_caption_bar_rgba(chunk["text"])
                cap_clip  = (
                    ImageClip(bar_arr)
                    .with_position((0, bar_y))
                    .with_start(chunk["start"])
                    .with_duration(chunk_dur)
                )
                cap_clips.append(cap_clip)

            # Footage plays continuously; captions overlay at correct times
            composite  = CompositeVideoClip([footage] + cap_clips, size=(W, H))
            final_clip = composite.subclipped(0, duration)
            final      = final_clip.with_audio(audio_clip)

            logger.info("Multi-clip footage + captions composited successfully.")
        except Exception as exc:
            logger.warning("Footage compositing failed (%s); falling back to gradient.", exc)
            bg_video = _build_gradient_clips(caption_chunks, duration, script_text)
            final    = bg_video.with_audio(audio_clip)
    else:
        logger.info("No stock footage available — using gradient background.")
        bg_video = _build_gradient_clips(caption_chunks, duration, script_text)
        final    = bg_video.with_audio(audio_clip)


    # ── Export ───────────────────────────────────────────────────────────────
    logger.info(
        "Exporting -> %s  [%dx%d @ %dfps | %s + %s | %s]",
        output_path, W, H, FPS, config.VIDEO_CODEC, config.AUDIO_CODEC, config.VIDEO_BITRATE,
    )
    try:
        final.write_videofile(
            str(output_path),
            fps=FPS,
            codec=config.VIDEO_CODEC,
            audio_codec=config.AUDIO_CODEC,
            bitrate=config.VIDEO_BITRATE,
            threads=4,
            preset="fast",
            logger="bar",
        )
    except Exception as exc:
        raise RuntimeError(f"Video export error: {exc}") from exc
    finally:
        try:
            audio_clip.close()
            final.close()
        except Exception:
            pass

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Output video missing or empty: {output_path}")

    logger.info("Video ready: %s (%.1f MB)",
                output_path, output_path.stat().st_size / (1024 * 1024))
    return output_path
