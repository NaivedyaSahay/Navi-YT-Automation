"""
video_engine.py
---------------
Intelligent, High-Definition, 100% Free 9:16 Video Rendering Engine
Powered by MoviePy 2.x and backend FFmpeg.

Features:
  1. Smart Media Discovery: Scans, validates, and naturally sorts local media assets
     (MP4, MOV, MKV, WEBM, JPG, PNG, WEBP).
  2. Resolution Standardization: Proportional scaling and centering into vertical
     1080x1920 (9:16) with zero aspect ratio distortion or squishing.
     Supports 'crop_cover' (center zoom-crop) and 'blur_pad' (blurred background).
  3. Dynamic Motion for Images: Subtle Ken Burns pan/zoom to keep still images engaging.
  4. Cinematic Transitions: Smooth crossfades between stitched clips to eliminate robotic cuts.
  5. High-Fidelity Export: libx264 @ 8M bitrate, AAC 192k, YUV420p, high profile,
     faststart moov atom to survive Meta (Instagram Reels & Facebook) re-compression.

Public API:
  - scan_and_sort_media(folder_or_files, sort_by="natural") -> List[Path]
  - normalize_clip_to_916(media, target_width=1080, target_height=1920, ...) -> VideoClip
  - stitch_video_sequence(media_items, target_duration, ...) -> VideoClip
  - export_video_hd(clip, output_path, ...) -> Path
"""

from __future__ import annotations

import logging
import math
import os
import re
from pathlib import Path
from typing import List, Optional, Union, Sequence

import numpy as np
from PIL import Image
from moviepy import (
    VideoFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips,
)
import moviepy.video.fx as vfx

import config

logger = logging.getLogger("video_engine")

SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
SUPPORTED_EXTS = SUPPORTED_VIDEO_EXTS | SUPPORTED_IMAGE_EXTS


# ─────────────────────────────────────────────────────────────────────────────
# 1. Smart Asset Organization & Discovery
# ─────────────────────────────────────────────────────────────────────────────

def _natural_sort_key(s: str):
    """Sort strings containing numbers in human natural order (e.g. clip_2 before clip_10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def scan_and_sort_media(
    folder_or_files: Union[Path, str, Sequence[Union[Path, str]]],
    recursive: bool = False,
    sort_by: str = "natural",
) -> List[Path]:
    """
    Scans, filters, validates, and sorts media files logically.

    Args:
        folder_or_files: Directory path or list of candidate paths.
        recursive: Whether to scan subdirectories if given a folder.
        sort_by: 'natural' (default alphanumeric), 'mtime' (newest first),
                 'name' (strict alphabetical), or 'random'.

    Returns:
        List of valid, non-zero-byte Path objects.
    """
    candidates: List[Path] = []

    if isinstance(folder_or_files, (str, Path)):
        p = Path(folder_or_files)
        if p.is_dir():
            iterator = p.rglob("*") if recursive else p.iterdir()
            candidates = [f for f in iterator if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]
        elif p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            candidates = [p]
    elif isinstance(folder_or_files, (list, tuple)):
        for item in folder_or_files:
            p = Path(item)
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                candidates.append(p)
            elif p.is_dir():
                iterator = p.rglob("*") if recursive else p.iterdir()
                candidates.extend(f for f in iterator if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS)

    # Filter out empty or unreadable files
    valid_files: List[Path] = []
    for f in candidates:
        try:
            if f.exists() and f.stat().st_size > 1024:  # At least 1 KB
                valid_files.append(f)
            else:
                logger.debug("Skipping empty or tiny media file: %s", f)
        except OSError:
            logger.debug("Could not access file: %s", f)

    # Sort files
    if sort_by == "natural":
        valid_files.sort(key=lambda p: _natural_sort_key(p.name))
    elif sort_by == "mtime":
        valid_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    elif sort_by == "name":
        valid_files.sort(key=lambda p: p.name.lower())
    elif sort_by == "random":
        import random
        random.shuffle(valid_files)

    logger.info("Found and validated %d media file(s) [sort: %s].", len(valid_files), sort_by)
    return valid_files


# ─────────────────────────────────────────────────────────────────────────────
# 2. Resolution Standardization & 9:16 Aspect Normalization
# ─────────────────────────────────────────────────────────────────────────────

def _apply_ken_burns_image(
    image_path: Path,
    duration: float,
    target_w: int,
    target_h: int,
    zoom_ratio: float = 1.10,
    motion_type: str = "zoom_in",
) -> VideoFileClip | ImageClip:
    """
    Creates dynamic cinematic camera motion (slow zoom-in, zoom-out, pan-right, tilt-up)
    for static images, giving the feel of a high-budget live-action documentary.
    """
    pil_img = Image.open(str(image_path)).convert("RGB")
    src_w, src_h = pil_img.size

    # Base scale to fill target_w x target_h with extra margin for panning
    margin = 1.12
    base_scale = max(target_w / src_w, target_h / src_h) * margin
    new_src_w = int(round(src_w * base_scale))
    new_src_h = int(round(src_h * base_scale))
    scaled_img = pil_img.resize((new_src_w, new_src_h), Image.Resampling.LANCZOS)
    img_array = np.array(scaled_img)

    def frame_transform(get_frame, t):
        progress = min(1.0, max(0.0, t / max(0.01, duration)))

        # Determine zoom and center offsets based on motion_type
        if motion_type == "zoom_out":
            cur_zoom = zoom_ratio - (zoom_ratio - 1.0) * progress
            cx_offset = 0.0
            cy_offset = 0.0
        elif motion_type == "pan_right":
            cur_zoom = 1.08
            cx_offset = (progress - 0.5) * (new_src_w * 0.06)
            cy_offset = 0.0
        elif motion_type == "pan_left":
            cur_zoom = 1.08
            cx_offset = (0.5 - progress) * (new_src_w * 0.06)
            cy_offset = 0.0
        elif motion_type == "tilt_up":
            cur_zoom = 1.08
            cx_offset = 0.0
            cy_offset = (0.5 - progress) * (new_src_h * 0.06)
        else:  # default "zoom_in"
            cur_zoom = 1.0 + (zoom_ratio - 1.0) * progress
            cx_offset = 0.0
            cy_offset = 0.0

        # Sub-window inside scaled image
        win_w = target_w / cur_zoom
        win_h = target_h / cur_zoom

        center_x = (new_src_w / 2.0) + cx_offset
        center_y = (new_src_h / 2.0) + cy_offset

        x1 = max(0, int(round(center_x - win_w / 2.0)))
        y1 = max(0, int(round(center_y - win_h / 2.0)))
        x2 = min(new_src_w, int(round(x1 + win_w)))
        y2 = min(new_src_h, int(round(y1 + win_h)))

        # Boundary safety clamp
        if x2 - x1 < int(win_w):
            x1 = max(0, x2 - int(win_w))
        if y2 - y1 < int(win_h):
            y1 = max(0, y2 - int(win_h))

        sub = img_array[y1:y2, x1:x2].astype(np.uint8)
        resized_sub = Image.fromarray(sub).resize((target_w, target_h), Image.Resampling.LANCZOS)
        return np.array(resized_sub)

    base_clip = ImageClip(img_array).with_duration(duration).with_fps(config.VIDEO_FPS)
    return base_clip.transform(frame_transform)


def normalize_clip_to_916(
    media: Union[Path, str, any],
    target_width: int = config.VIDEO_WIDTH,
    target_height: int = config.VIDEO_HEIGHT,
    fps: int = config.VIDEO_FPS,
    duration: Optional[float] = None,
    mode: str = "crop_cover",
    ken_burns: bool = True,
    motion_type: str = "zoom_in",
) -> any:
    """
    Standardizes any video or image into exact vertical 9:16 layout (1080x1920)
    cleanly without stretching, squishing, or distorting the source asset.
    """
    is_image = False
    clip = None

    if isinstance(media, (str, Path)):
        media_path = Path(media)
        if not media_path.exists():
            raise FileNotFoundError(f"Media file not found: {media_path}")

        ext = media_path.suffix.lower()
        if ext in SUPPORTED_IMAGE_EXTS:
            is_image = True
            clip_dur = duration or 5.0
            if ken_burns:
                try:
                    clip = _apply_ken_burns_image(
                        media_path,
                        clip_dur,
                        target_width,
                        target_height,
                        motion_type=motion_type,
                    )
                except Exception as exc:
                    logger.debug("Ken burns transform failed (%s), falling back to static ImageClip", exc)
                    clip = ImageClip(str(media_path)).with_duration(clip_dur)
            else:
                clip = ImageClip(str(media_path)).with_duration(clip_dur)
        else:
            # Video file
            clip = VideoFileClip(str(media_path), audio=False)
            if duration and duration > 0:
                clip = clip.subclipped(0, min(clip.duration, duration))
    else:
        clip = media
        if duration and duration > 0 and hasattr(clip, "subclipped"):
            clip = clip.subclipped(0, min(clip.duration, duration))

    # Standardize FPS
    clip = clip.with_fps(fps)

    # If Ken Burns already generated target size, return directly
    if clip.size[0] == target_width and clip.size[1] == target_height:
        return clip

    src_w, src_h = clip.size
    target_ratio = target_width / target_height
    src_ratio = src_w / src_h

    # Perfect match check (e.g. already 9:16)
    if math.isclose(src_ratio, target_ratio, rel_tol=0.01):
        return clip.resized((target_width, target_height))

    if mode == "blur_pad":
        fg_scale = min(target_width / src_w, target_height / src_h)
        fg_w = int(round(src_w * fg_scale))
        fg_h = int(round(src_h * fg_scale))
        fg = clip.resized((fg_w, fg_h)).with_position(("center", "center"))

        bg_scale = max(target_width / src_w, target_height / src_h)
        bg_scaled = clip.resized(bg_scale)
        bg = (
            bg_scaled.cropped(
                x_center=bg_scaled.w / 2,
                y_center=bg_scaled.h / 2,
                width=target_width,
                height=target_height,
            )
            .with_effects([vfx.MultiplyColor(0.35)])
        )
        return CompositeVideoClip([bg, fg], size=(target_width, target_height))

    # Default: 'crop_cover' (center zoom-crop without distortion)
    scale = max(target_width / src_w, target_height / src_h)
    scaled = clip.resized(scale)
    cropped = scaled.cropped(
        x_center=scaled.w / 2,
        y_center=scaled.h / 2,
        width=target_width,
        height=target_height,
    )
    return cropped


# ─────────────────────────────────────────────────────────────────────────────
# 3. Smart Asset Stitching with Cinematic Transitions
# ─────────────────────────────────────────────────────────────────────────────

def stitch_video_sequence(
    media_items: Sequence[Union[Path, str, any]],
    target_duration: float,
    max_clip_duration: float = 6.0,
    clip_durations: Optional[List[float]] = None,
    transition_duration: float = 0.5,
    crossfade: bool = True,
    mode: str = "crop_cover",
) -> any:
    """
    Normalizes a sequence of video clips or images into 9:16 and stitches them
    together with smooth crossfades and alternating directional camera motions.
    """
    if not media_items:
        raise ValueError("stitch_video_sequence called with empty media_items list.")

    motion_cycle = ["zoom_in", "pan_right", "zoom_out", "tilt_up"]
    loaded_clips = []

    for i, item in enumerate(media_items):
        item_dur = clip_durations[i] if (clip_durations and i < len(clip_durations)) else max_clip_duration
        # Add transition padding to ensure overlap doesn't shorten individual scene
        padded_dur = item_dur + (transition_duration if crossfade and i > 0 else 0.0)
        motion = motion_cycle[i % len(motion_cycle)]

        try:
            norm_clip = normalize_clip_to_916(
                item,
                duration=padded_dur,
                mode=mode,
                motion_type=motion,
            )
            norm_clip = norm_clip.subclipped(0, padded_dur)
            loaded_clips.append(norm_clip)
        except Exception as exc:
            logger.warning("Failed to normalize media item '%s': %s", item, exc)

    if not loaded_clips:
        raise RuntimeError("No valid clips could be prepared for stitching.")

    logger.info("Stitching %d normalized 9:16 clips (Target Duration: %.2fs)...",
                len(loaded_clips), target_duration)

    if len(loaded_clips) == 1:
        combined = loaded_clips[0]
    elif crossfade and transition_duration > 0 and len(loaded_clips) > 1:
        # Apply smooth CrossFadeIn to each clip after the first
        transition_clips = [loaded_clips[0]]
        for c in loaded_clips[1:]:
            trans_c = c.with_effects([vfx.CrossFadeIn(transition_duration)])
            transition_clips.append(trans_c)

        combined = concatenate_videoclips(
            transition_clips,
            padding=-transition_duration,
            method="compose",
        )
    else:
        combined = concatenate_videoclips(loaded_clips, method="compose")

    # Loop if total duration is shorter than target_duration
    if combined.duration < target_duration:
        loops = int(math.ceil(target_duration / max(0.1, combined.duration)))
        logger.info("Sequence duration (%.2fs) < target (%.2fs). Looping %dx...",
                    combined.duration, target_duration, loops)
        combined = concatenate_videoclips([combined] * loops, method="compose")

    return combined.subclipped(0, target_duration)


# ─────────────────────────────────────────────────────────────────────────────
# 4. High-Fidelity Video Export Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def export_video_hd(
    clip: any,
    output_path: Union[Path, str],
    fps: int = config.VIDEO_FPS,
    codec: str = config.VIDEO_CODEC,
    audio_codec: str = config.AUDIO_CODEC,
    bitrate: str = config.VIDEO_BITRATE,
    audio_bitrate: str = "192k",
    threads: int = 4,
    preset: str = "fast",
) -> Path:
    """
    Renders and exports the final video via MoviePy with explicit FFmpeg parameters
    tuned for Instagram Reels & Facebook retention and crisp quality:
      - 30 fps standard
      - libx264 high profile, level 4.2
      - yuv420p pixel format (Instagram requirement)
      - 8M bitrate (survives Meta re-compression without macroblocking)
      - +faststart (moov atom at file start for instant playback)
      - 44.1kHz AAC stereo audio
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Exporting High-Definition Reels Video -> %s", out)
    logger.info("Settings: %dx%d @ %dfps | Video: %s (%s) | Audio: %s (%s)",
                clip.size[0], clip.size[1], fps, codec, bitrate, audio_codec, audio_bitrate)

    ffmpeg_params = [
        "-pix_fmt", "yuv420p",        # Required for Instagram & mobile playback
        "-profile:v", "high",         # High profile H.264 for crisp detail
        "-level", "4.2",              # Wide compatibility for 1080p mobile video
        "-movflags", "+faststart",    # Move index to start so video plays without buffering
        "-ar", "44100",               # Clean 44.1 kHz audio sampling
    ]

    try:
        clip.write_videofile(
            str(out),
            fps=fps,
            codec=codec,
            audio_codec=audio_codec if clip.audio is not None else None,
            bitrate=bitrate,
            audio_bitrate=audio_bitrate if clip.audio is not None else None,
            threads=threads,
            preset=preset,
            logger="bar",
            ffmpeg_params=ffmpeg_params,
        )
    except Exception as exc:
        raise RuntimeError(f"High-definition video export failed: {exc}") from exc

    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"Exported video missing or 0 bytes: {out}")

    file_size_mb = out.stat().st_size / (1024 * 1024)
    logger.info("Video successfully rendered: %s (%.2f MB)", out, file_size_mb)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 5. CLI & Standalone Verification
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print("Testing Video Engine...")

    # Quick test scanning output directory
    found = scan_and_sort_media(config.OUTPUT_DIR)
    print(f"Scanned output dir: found {len(found)} media files.")

    # Generate synthetic 9:16 test render
    from moviepy import ColorClip
    test_clip = ColorClip(size=(640, 480), color=(30, 80, 160), duration=2)
    norm = normalize_clip_to_916(test_clip)
    print(f"Normalized clip size: {norm.size} (Expected: 1080x1920)")

    test_out = config.OUTPUT_DIR / "test_engine_export.mp4"
    export_video_hd(norm, test_out)
    if test_out.exists():
        print(f"Export verified: {test_out} ({test_out.stat().st_size} bytes)")
        test_out.unlink()
    print("Video Engine self-test PASSED!")
