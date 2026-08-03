"""
main.py
-------
Entry point for the YouTube Shorts automation pipeline.

Usage:
    python main.py "your video topic here"          # manual topic
    python main.py --auto                            # auto-discover trending topic + upload
    python main.py --auto --no-upload               # auto-discover + generate only
    python main.py "AI breakthroughs" --privacy public
    python main.py --topic "Python tips" --voice en-US-JennyNeural
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
import time

# Force UTF-8 output on Windows so box-drawing / emoji don't crash
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

import config
import script_generator
import voice_generator
import video_editor
import uploader
import trend_finder

# ── Logger ────────────────────────────────────────────────────────────────────
logger = logging.getLogger("main")

BANNER = """
+======================================================+
|   [*]  Navi-Automation  YouTube Shorts Bot           |
|        Gemini - EdgeTTS - MoviePy - YouTube API      |
+======================================================+
"""


# ─────────────────────────────────────────────────────────────────────────────
# CLI argument parser
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Fully automated YouTube Shorts generator and uploader.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="Video topic (e.g. '3 crazy facts about black holes').",
    )
    parser.add_argument(
        "--topic",
        dest="topic_flag",
        default=None,
        metavar="TOPIC",
        help="Alternative way to pass the topic.",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip the YouTube upload step (generate video only).",
    )
    parser.add_argument(
        "--privacy",
        choices=["public", "unlisted", "private"],
        default=None,
        help="YouTube video privacy status (default: from .env or 'unlisted').",
    )
    parser.add_argument(
        "--voice",
        default=None,
        help="Edge TTS voice name (default: from .env or 'en-US-ChristopherNeural').",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override the output directory for generated files.",
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Do not delete intermediate files (audio, background) after export.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-discover trending topic from Google Trends + Reddit and generate a video.",
    )
    parser.add_argument(
        "--region",
        default=None,
        metavar="CC",
        help="Country code for trend discovery (default: IN). E.g. US, GB, IN.",
    )
    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline stages
# ─────────────────────────────────────────────────────────────────────────────

def _step(n: int, label: str) -> None:
    logger.info("")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  STEP %d / 4 — %s", n, label)
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def run_pipeline(
    topic: str,
    no_upload: bool = False,
    privacy: str | None = None,
    voice: str | None = None,
    output_dir: str | None = None,
    keep_files: bool = False,
) -> None:
    """Execute the full generation → upload pipeline."""

    print(BANNER)
    start_time = time.time()

    # ── Override output dir if requested ──────────────────────────────────────
    if output_dir:
        import config as _cfg
        _cfg.OUTPUT_DIR = Path(output_dir)
        _cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        _cfg.AUDIO_FILE = _cfg.OUTPUT_DIR / "voiceover.mp3"
        _cfg.VIDEO_FILE = _cfg.OUTPUT_DIR / "final_video.mp4"
        _cfg.BG_VIDEO_FILE = _cfg.OUTPUT_DIR / "background.mp4"

    # ── Validate config ───────────────────────────────────────────────────────
    try:
        config.validate()
    except EnvironmentError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1 — Generate script
    # ─────────────────────────────────────────────────────────────────────────
    _step(1, "Generating Script")
    try:
        script_data = script_generator.generate_script(topic)
    except Exception as exc:
        logger.error("Script generation failed: %s", exc)
        sys.exit(1)

    print("\n📝 Generated Script:")
    print(f"   Title      : {script_data['title']}")
    print(f"   Script     : {script_data['script'][:120]}…")
    print(f"   Tags       : {', '.join(script_data['tags'][:5])} …")
    print(f"   Keywords   : {', '.join(script_data.get('keywords', []))}")
    print()

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2 — Generate voiceover
    # ─────────────────────────────────────────────────────────────────────────
    _step(2, "Generating Voiceover")
    try:
        audio_path, word_timings = voice_generator.generate_voiceover(
            text=script_data["script"],
            voice=voice,
        )
    except Exception as exc:
        logger.error("Voiceover generation failed: %s", exc)
        sys.exit(1)

    print(f"🎙️  Voiceover saved to: {audio_path}")
    print()

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3 — Build video
    # ─────────────────────────────────────────────────────────────────────────
    _step(3, "Building Video")
    try:
        video_path = video_editor.create_video(
            audio_path=audio_path,
            keywords=script_data.get("keywords", ["nature"]),
            word_timings=word_timings,
            script_text=script_data.get("script", ""),
        )
    except Exception as exc:
        logger.error("Video creation failed: %s", exc)
        sys.exit(1)

    print(f"🎬  Video saved to: {video_path}")
    print()

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4 — Upload to YouTube (optional)
    # ─────────────────────────────────────────────────────────────────────────
    if no_upload:
        logger.info("Skipping upload (--no-upload flag is set).")
        print("⏭️  Upload skipped. Your video is ready locally.")
    else:
        _step(4, "Uploading to YouTube")
        try:
            video_id = uploader.upload_video(
                video_path=video_path,
                title=script_data["title"],
                description=script_data["description"],
                tags=script_data["tags"],
                privacy_status=privacy,
            )
            print(f"\n✅ Uploaded! Watch at: https://www.youtube.com/watch?v={video_id}")
        except FileNotFoundError as exc:
            logger.error("OAuth setup error: %s", exc)
            print("\n⚠️  Upload skipped – client_secrets.json not found.")
            print("    See README.md → 'YouTube OAuth Setup' for instructions.")
        except Exception as exc:
            logger.error("Upload failed: %s", exc)
            print(f"\n❌ Upload failed: {exc}")

    # ── Clean up intermediate files ───────────────────────────────────────────
    if not keep_files:
        for path in [config.AUDIO_FILE, config.BG_VIDEO_FILE]:
            try:
                if Path(path).exists():
                    Path(path).unlink()
                    logger.debug("Removed intermediate file: %s", path)
            except Exception:
                pass

    elapsed = time.time() - start_time
    print(f"\n⏱️  Pipeline completed in {elapsed:.1f} seconds.")
    logger.info("Pipeline finished in %.1f s.", elapsed)


def _discover_topic(region: str) -> str:
    """Fetch trending topics and return the best one."""
    print("\n🔍 Discovering trending topics…\n")
    try:
        topics = trend_finder.get_trending_topics(n=config.TREND_N, region=region)
    except Exception as exc:
        logger.error("Trend discovery failed: %s", exc)
        sys.exit(1)

    if not topics:
        logger.error("No trending topics found. Try again later or provide a topic manually.")
        sys.exit(1)

    print("🔥 Trending Topics Found:")
    print("  " + "-" * 50)
    for i, t in enumerate(topics, 1):
        print(f"  {i}. {t['topic']}")
        print(f"     └─ Source: {t['source']}")
    print("  " + "-" * 50)

    chosen = topics[0]
    print(f"\n✅ Auto-selected: \"{chosen['topic']}\" [{chosen['source']}]\n")
    return chosen["topic"]


# ───────────────────────────────────────────────────────────────────────────────
# Entry point
# ───────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()
    region = args.region or config.TREND_REGION

    # ─ Determine topic ─────────────────────────────────────────────────
    if args.auto:
        topic = _discover_topic(region)
    else:
        topic = args.topic or args.topic_flag
        if not topic:
            topic = input("🎯 Enter the video topic: ").strip()
        if not topic:
            parser.error("Provide a topic or use --auto to discover one automatically.")

    run_pipeline(
        topic=topic,
        no_upload=args.no_upload,
        privacy=args.privacy,
        voice=args.voice,
        output_dir=args.output_dir,
        keep_files=args.keep_files,
    )


if __name__ == "__main__":
    main()
