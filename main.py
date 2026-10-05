"""
main.py
-------
CLI Entry Point & Pipeline Orchestrator for Navi-Automation YouTube Shorts Bot.
Generates Indian Mythological & Philosophical YouTube Shorts with AI cinematic visuals,
high-retention Groq/Gemini scripts, Hindi Sarvam/Edge-TTS voiceovers, dynamic animated captions,
and publishes directly to YouTube Shorts via YouTube Data API v3.

Usage:
  python main.py                                      # Auto-discover trending mythological topic + upload
  python main.py "The curse of Karna"                # Explicit topic
  python main.py --category "Lord Shiva"             # From a specific mythological category
  python main.py "Arjuna and Krishna" --no-upload    # Generate video locally without uploading
  python main.py --privacy unlisted                  # Upload as unlisted
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows so box-drawing / Devanagari don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import config
from topic_picker import get_trending_topics, record_posted_topic
from script_generator import generate_script
from voice_generator import generate_voiceover
from video_composer import compose_video
import uploader

logger = logging.getLogger("main")

BANNER = """
+==============================================================+
|   [*]  Navi-Automation — YouTube Shorts Mythological Bot     |
|   Groq / Gemini — Sarvam / EdgeTTS — FLUX AI — YouTube API   |
+==============================================================+
"""


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Automated Indian Mythological YouTube Shorts generator and uploader.",
    )
    parser.add_argument("command_or_topic", nargs="?", help="Video topic or test command")
    parser.add_argument("--topic", help="Explicit video topic")
    parser.add_argument("--auto", action="store_true", help="Auto-discover fresh mythological topic")
    parser.add_argument("--category", choices=config.ALLOWED_CATEGORIES, help="Target mythological category")
    parser.add_argument("--no-upload", action="store_true", help="Skip YouTube upload step (render video only)")
    parser.add_argument(
        "--privacy",
        choices=["public", "unlisted", "private"],
        default=config.DEFAULT_PRIVACY_STATUS,
        help="YouTube video privacy status (default: from .env or 'public')",
    )
    parser.add_argument("--voice", help="TTS voice override (e.g. hi-IN-SwaraNeural or Sarvam speaker)")
    parser.add_argument("--output-dir", help="Override output directory")
    return parser.parse_args()


def run_pipeline(
    topic: str | None = None,
    category: str | None = None,
    no_upload: bool = False,
    privacy: str | None = None,
    voice: str | None = None,
    output_dir: str | None = None,
) -> Path:
    print(BANNER)
    logger.info("==================================================")
    logger.info("  🚀 Starting Navi-Automation YouTube Shorts Pipeline ")
    logger.info("==================================================")

    # 1. Validate environment configuration
    config.validate()

    # 2. Topic discovery & selection
    if not topic:
        logger.info("Discovering fresh, unposted mythological topic...")
        discovered = get_trending_topics(n=1, category=category)
        if not discovered:
            raise RuntimeError("Could not find a suitable mythological topic.")
        selected_topic = discovered[0]["topic"]
        selected_category = discovered[0].get("category", category or "General")
    else:
        selected_topic = topic
        selected_category = category or "Custom"

    logger.info("📌 Target Topic: '%s' [Category: %s]", selected_topic, selected_category)

    # 3. Generate script via Master Mythological Prompter Agent
    script_data = generate_script(selected_topic)
    title = script_data.get("title", selected_topic)
    yt_title = script_data.get("youtube_title", f"{title} #Shorts")
    yt_description = script_data.get("youtube_description", script_data.get("script", ""))
    yt_tags = script_data.get("youtube_tags", ["Shorts", "Mythology", "SanatanDharma"])
    script_text = script_data.get("script", "")
    keywords = script_data.get("keywords", ["ancient indian temple", "sacred fire ritual"])
    image_prompts = script_data.get("image_prompts", [])
    scene_ratios = script_data.get("scene_ratios", [0.20, 0.32, 0.28, 0.20])

    logger.info("📜 YouTube Title: '%s'", yt_title)
    logger.info("📝 Script Preview: '%s...'", script_text[:80])

    # 4. Generate Hindi TTS voiceover & word timing boundaries
    out_dir = Path(output_dir) if output_dir else config.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / "voiceover.mp3"
    video_path = out_dir / "final_video.mp4"

    audio_file, word_timings = generate_voiceover(
        text=script_text,
        output_path=audio_path,
        voice=voice or config.TTS_VOICE,
    )

    # 5. Composite AI mythological scenes + voiceover + BGM + captions
    final_video = compose_video(
        audio_path=audio_file,
        word_timings=word_timings,
        script_text=script_text,
        keywords=keywords,
        image_prompts=image_prompts,
        scene_ratios=scene_ratios,
        output_path=video_path,
    )

    # 6. Upload to YouTube Shorts
    if not no_upload:
        logger.info("📤 Uploading video to YouTube Shorts (%s)...", privacy or config.DEFAULT_PRIVACY_STATUS)
        try:
            video_id = uploader.upload_video(
                video_path=final_video,
                title=yt_title,
                description=yt_description,
                tags=yt_tags,
                category_id=config.DEFAULT_CATEGORY_ID,
                privacy_status=privacy or config.DEFAULT_PRIVACY_STATUS,
            )
            logger.info("✅ Successfully uploaded to YouTube Shorts!")
            logger.info("🔗 Watch link: https://www.youtube.com/shorts/%s", video_id)
        except Exception as exc:
            logger.error("❌ YouTube upload failed: %s", exc)
            logger.info("The generated video is saved at: %s", final_video.resolve())
            raise
    else:
        logger.info("⏭️ --no-upload specified: skipping YouTube upload step.")

    # 7. Record topic to prevent repetition
    try:
        record_posted_topic(selected_topic, selected_category)
    except Exception as exc:
        logger.warning("Could not record posted topic: %s", exc)

    logger.info("==================================================")
    logger.info("  ✨ YouTube Shorts Pipeline Completed!           ")
    logger.info("  🎬 Final Video: %s", final_video.resolve())
    logger.info("==================================================")

    return final_video


def main():
    args = parse_args()
    topic = args.topic or (args.command_or_topic if args.command_or_topic != "test" else None)
    no_upload = args.no_upload or (args.command_or_topic == "test")

    try:
        run_pipeline(
            topic=topic,
            category=args.category,
            no_upload=no_upload,
            privacy=args.privacy,
            voice=args.voice,
            output_dir=args.output_dir,
        )
    except KeyboardInterrupt:
        logger.info("Pipeline cancelled by user.")
        sys.exit(0)
    except Exception as exc:
        logger.exception("Pipeline fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
