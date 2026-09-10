"""
main.py
-------
Entry point for the Multi-Platform Auto-Publisher Pipeline:
- Video Generation (Shorts/Reels) → Published to YouTube, Pinterest, Facebook, Instagram.
- Pure Text Motivational Quotes → Published to X (Twitter) and Threads.

Usage:
    python main.py "your video topic here"                                # manual topic
    python main.py --auto                                                 # auto-discover topic + multi-platform post
    python main.py --auto --platforms youtube,instagram,threads           # selected platforms
    python main.py --mode quote --quote-category philosophers             # quote posts only
    python main.py --mode video --auto                                    # video posts only
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows so box-drawing / emoji don't crash
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import config
import metadata_adapter
import quote_generator
import script_generator
import trend_finder
from uploaders.multi_publisher import MultiPublisher
import video_editor
import voice_generator

# ── Logger ────────────────────────────────────────────────────────────────────
logger = logging.getLogger("main")

BANNER = """
+==============================================================+
|   [*] Navi-Automation Multi-Platform Content Engine          |
|       YouTube | Pinterest | Facebook | Instagram | X | Threads|
+==============================================================+
"""


# ─────────────────────────────────────────────────────────────────────────────
# CLI argument parser
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Multi-Platform Video & Pure Text Quote Auto-Publisher.",
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
        "--mode",
        choices=["all", "video", "quote"],
        default="all",
        help="Execution mode: 'all' (video + quote), 'video' only, or 'quote' only.",
    )
    parser.add_argument(
        "--platforms",
        default=None,
        help="Comma-separated list of target platforms (e.g. 'youtube,pinterest,facebook,instagram,x,threads' or 'all').",
    )
    parser.add_argument(
        "--quote-category",
        "--category",
        dest="quote_category",
        choices=quote_generator.CATEGORIES + ["random"],
        default="random",
        help="Quote source category (philosophers, movies, series, books, cartoons, anime, personalities, ai).",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip the social upload step (generate assets locally only).",
    )
    parser.add_argument(
        "--privacy",
        choices=["public", "unlisted", "private"],
        default=None,
        help="YouTube video privacy status.",
    )
    parser.add_argument(
        "--voice",
        default=None,
        help="Edge TTS voice name.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override the output directory for generated files.",
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Do not delete intermediate files after export.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-discover trending topic from Google Trends + Reddit.",
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
    logger.info("  STEP %d — %s", n, label)
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def run_pipeline(
    topic: str | None = None,
    mode: str = "all",
    platforms_arg: str | None = None,
    quote_category: str = "random",
    no_upload: bool = False,
    privacy: str | None = None,
    voice: str | None = None,
    output_dir: str | None = None,
    keep_files: bool = False,
) -> None:
    """Execute the multi-platform video & quote generation + distribution pipeline."""

    print(BANNER)
    start_time = time.time()

    if output_dir:
        config.OUTPUT_DIR = Path(output_dir)
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        config.AUDIO_FILE = config.OUTPUT_DIR / "voiceover.mp3"
        config.VIDEO_FILE = config.OUTPUT_DIR / "final_video.mp4"
        config.BG_VIDEO_FILE = config.OUTPUT_DIR / "background.mp4"

    try:
        config.validate()
    except EnvironmentError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    # ── Parse target platforms ────────────────────────────────────────────────
    if platforms_arg and platforms_arg.strip().lower() != "all":
        target_platforms = [p.strip().lower() for p in platforms_arg.split(",") if p.strip()]
    else:
        target_platforms = config.ENABLED_PLATFORMS

    video_path: Path | None = None
    script_data: dict | None = None
    quote_data: dict | None = None

    step_count = 1

    # ─────────────────────────────────────────────────────────────────────────
    # STEP: Generate Video (YouTube, Pinterest, Facebook, Instagram)
    # ─────────────────────────────────────────────────────────────────────────
    if mode in ("all", "video"):
        if not topic:
            topic = "Mind-blowing facts about life"

        _step(step_count, "Generating Video Script")
        step_count += 1
        try:
            script_data = script_generator.generate_script(topic)
        except Exception as exc:
            logger.error("Script generation failed: %s", exc)
            sys.exit(1)

        print("\n📝 Generated Video Script:")
        print(f"   Title      : {script_data['title']}")
        print(f"   Script     : {script_data['script'][:120]}…")
        print(f"   Keywords   : {', '.join(script_data.get('keywords', []))}\n")

        _step(step_count, "Generating Voiceover")
        step_count += 1
        try:
            audio_path, word_timings = voice_generator.generate_voiceover(
                text=script_data["script"],
                voice=voice,
            )
        except Exception as exc:
            logger.error("Voiceover generation failed: %s", exc)
            sys.exit(1)

        _step(step_count, "Building Vertical Video (9:16)")
        step_count += 1
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

        print(f"🎬 Video rendered successfully at: {video_path}\n")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP: Generate Pure Text Motivational Quote (X & Threads)
    # ─────────────────────────────────────────────────────────────────────────
    if mode in ("all", "quote"):
        _step(step_count, "Generating Pure Text Motivational Quote")
        step_count += 1
        quote_cat = None if quote_category == "random" else quote_category
        quote_data = quote_generator.generate_quote(category=quote_cat)

        print("\n💬 Generated Motivational Quote:")
        print(f"   Category : {quote_data['category'].capitalize()}")
        print(f"   Author   : {quote_data['author']}")
        print(f"   Quote    : “{quote_data['quote']}”")
        print("\n   [X Post]       : " + quote_data['formatted_x_post'].replace('\n', ' '))
        print("   [Threads Post] : " + quote_data['formatted_threads_post'].replace('\n', ' ') + "\n")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP: Multi-Platform Publishing
    # ─────────────────────────────────────────────────────────────────────────
    if no_upload:
        logger.info("Skipping social publishing (--no-upload set).")
        print("⏭️  Publishing skipped. Generated content is ready locally.")
    else:
        _step(step_count, "Multi-Platform Social Distribution")
        publisher = MultiPublisher()
        publisher.publish(
            video_path=video_path,
            video_meta=script_data,
            quote_data=quote_data,
            platforms=target_platforms,
        )

    # ── Cleanup ───────────────────────────────────────────────────────────────
    if not keep_files:
        for path in [config.AUDIO_FILE, config.BG_VIDEO_FILE]:
            try:
                if Path(path).exists():
                    Path(path).unlink()
            except Exception:
                pass

    elapsed = time.time() - start_time
    print(f"\n⏱️  Pipeline completed in {elapsed:.1f} seconds.")


HISTORY_FILE = Path("posted_topics.json")

def _load_history() -> list[str]:
    if HISTORY_FILE.exists():
        try:
            import json
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def _save_history(topic: str) -> None:
    history = _load_history()
    history.append(topic)
    history = history[-100:]
    try:
        import json
        HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not save topic history: %s", exc)


def _discover_topic(region: str) -> str:
    print("\n🔍 Discovering trending topics…\n")
    try:
        topics = trend_finder.get_trending_topics(n=config.TREND_N, region=region)
    except Exception as exc:
        logger.error("Trend discovery failed: %s", exc)
        sys.exit(1)

    if not topics:
        logger.error("No trending topics found.")
        sys.exit(1)

    import random
    history = set(t.lower() for t in _load_history())
    fresh_topics = [t for t in topics if t["topic"].lower() not in history]
    if not fresh_topics:
        fresh_topics = topics

    chosen = random.choice(fresh_topics)
    _save_history(chosen["topic"])

    print(f"✅ Auto-selected topic: \"{chosen['topic']}\" [{chosen['source']}]\n")
    return chosen["topic"]


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()
    region = args.region or config.TREND_REGION

    topic = None
    if args.mode in ("all", "video"):
        if args.auto:
            topic = _discover_topic(region)
        else:
            topic = args.topic or args.topic_flag
            if not topic:
                topic = input("🎯 Enter the video topic: ").strip()

    run_pipeline(
        topic=topic,
        mode=args.mode,
        platforms_arg=args.platforms,
        quote_category=args.quote_category,
        no_upload=args.no_upload,
        privacy=args.privacy,
        voice=args.voice,
        output_dir=args.output_dir,
        keep_files=args.keep_files,
    )


if __name__ == "__main__":
    main()
