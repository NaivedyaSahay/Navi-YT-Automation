"""
config.py
---------
Centralised configuration loader for the YouTube Shorts automation pipeline.
Reads all settings from a .env file and exposes them as typed constants.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Locate and load the .env file ────────────────────────────────────────────
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("config")

# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY: str     = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY: str   = os.getenv("GEMINI_API_KEY", "")
HF_TOKEN: str         = os.getenv("HF_TOKEN", "")
HF_IMAGE_MODEL: str   = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
LOCAL_MYTHOLOGY_SCENES_DIR: Path = Path(__file__).parent / "assets" / "mythology_scenes"
PEXELS_API_KEY: str   = os.getenv("PEXELS_API_KEY", "")       # optional
PIXABAY_API_KEY: str  = os.getenv("PIXABAY_API_KEY", "")      # optional

# ── AI Model Settings ─────────────────────────────────────────────────────────
GROQ_MODEL: str   = os.getenv("GROQ_MODEL", "groq/compound")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# ── TTS Voice Provider Settings ───────────────────────────────────────────────
TTS_PROVIDER: str   = os.getenv("TTS_PROVIDER", "edge-tts")   # "edge-tts" (exact subtitle sync) or "sarvam"
SARVAM_API_KEY: str = os.getenv("SARVAM_API_KEY", "")
SARVAM_SPEAKER: str = os.getenv("SARVAM_SPEAKER", "ratan")  # ratan, shubh, aditya, kavya, ritu
SARVAM_MODEL: str   = os.getenv("SARVAM_MODEL", "bulbul:v3")

# Edge-TTS Settings (Primary - Swara Dramatic Expressive with exact WordBoundary timestamps)
TTS_VOICE: str  = os.getenv("TTS_VOICE", "hi-IN-SwaraNeural")
TTS_RATE: str   = os.getenv("TTS_RATE", "+0%")
TTS_PITCH: str  = os.getenv("TTS_PITCH", "+0Hz")
TTS_VOLUME: str = os.getenv("TTS_VOLUME", "+0%")

# ── Background Music (BGM) Settings ───────────────────────────────────────────
BGM_DIR: Path       = Path(__file__).parent / "background_music"
BGM_DIR.mkdir(parents=True, exist_ok=True)
BGM_VOLUME: float   = float(os.getenv("BGM_VOLUME", "0.035"))  # 3.5% volume (subtle background bed)
ENABLE_BGM: bool    = os.getenv("ENABLE_BGM", "true").lower() in ("true", "1", "yes")

# ── Video settings (9:16 Shorts format) ───────────────────────────────────────
VIDEO_WIDTH: int  = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT: int = int(os.getenv("VIDEO_HEIGHT", "1920"))
VIDEO_FPS: int    = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_CODEC: str  = os.getenv("VIDEO_CODEC", "libx264")
AUDIO_CODEC: str  = os.getenv("AUDIO_CODEC", "aac")
VIDEO_BITRATE: str = os.getenv("VIDEO_BITRATE", "8M")
BACKGROUND_COLOR: tuple = (18, 18, 30)   # dark fallback background

# ── Output paths ──────────────────────────────────────────────────────────────
OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_FILE: Path     = OUTPUT_DIR / "voiceover.mp3"
VIDEO_FILE: Path     = OUTPUT_DIR / "final_video.mp4"
BG_VIDEO_FILE: Path  = OUTPUT_DIR / "background.mp4"
POSTED_TOPICS_FILE: Path = Path(__file__).parent / "posted_topics.json"
USE_AI_VISUALS_ONLY: bool = True

# ── Allowed Categories ────────────────────────────────────────────────────────
ALLOWED_CATEGORIES = [
    "Mahabharata",
    "Ramayana",
    "Lord Shiva",
    "Bhagavad Gita",
    "Lord Krishna",
    "Karna & Dharma",
    "Hanuman",
    "Karma & Destiny",
    "Puranic Legends",
    "Vedic Wisdom",
    "Spiritual Life Lessons",
]

# ── YouTube / OAuth ───────────────────────────────────────────────────────────
CLIENT_SECRETS_FILE: str = os.getenv("CLIENT_SECRETS_FILE", "client_secrets.json")
TOKEN_FILE: str = os.getenv("TOKEN_FILE", "token.json")
YOUTUBE_SCOPES: list = ["https://www.googleapis.com/auth/youtube.upload"]
DEFAULT_PRIVACY_STATUS: str = os.getenv("DEFAULT_PRIVACY_STATUS", "public")  # "public" | "unlisted" | "private"
DEFAULT_CATEGORY_ID: str = os.getenv("DEFAULT_CATEGORY_ID", "22")              # 22 = People & Blogs, 27 = Education

# ── Validation helper ──────────────────────────────────────────────────────────
def validate() -> None:
    """Warn about missing critical environment variables without crashing."""
    if not GROQ_API_KEY and not GEMINI_API_KEY:
        logger.warning("Neither GROQ_API_KEY nor GEMINI_API_KEY is set — script generation may fail.")
    if not HF_TOKEN:
        logger.warning("HF_TOKEN is not set — AI visual generator will fall back to local scene assets.")
    if not SARVAM_API_KEY:
        logger.info("SARVAM_API_KEY not set — using Edge-TTS ('%s') as primary voice.", TTS_VOICE)

    secrets_path = Path(__file__).parent / CLIENT_SECRETS_FILE
    token_path = Path(__file__).parent / TOKEN_FILE
    if not secrets_path.exists() and not token_path.exists():
        logger.warning(
            "Neither %s nor %s found! YouTube uploads will require authentication setup.",
            CLIENT_SECRETS_FILE,
            TOKEN_FILE,
        )

    logger.info("Configuration loaded successfully.")
