"""
config.py
---------
Centralised configuration loader for the YouTube automation pipeline.
Reads all settings from a .env file and exposes them as typed constants.
"""

import os
import logging
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
GEMINI_API_KEY: str  = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY: str    = os.getenv("GROQ_API_KEY", "")
PEXELS_API_KEY: str  = os.getenv("PEXELS_API_KEY", "")       # optional
PIXABAY_API_KEY: str = os.getenv("PIXABAY_API_KEY", "")      # optional

# ── Trend settings ────────────────────────────────────────────────────────────
TREND_REGION: str = os.getenv("TREND_REGION", "IN")   # ISO country code
TREND_N: int      = int(os.getenv("TREND_N", "5"))     # candidates to fetch

# ── Gemini model ──────────────────────────────────────────────────────────────
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ── TTS Voice ─────────────────────────────────────────────────────────────────
TTS_VOICE: str = os.getenv("TTS_VOICE", "en-US-ChristopherNeural")
TTS_RATE: str = os.getenv("TTS_RATE", "+0%")   # e.g. "+10%" to speed up
TTS_VOLUME: str = os.getenv("TTS_VOLUME", "+0%")

# ── Video settings ────────────────────────────────────────────────────────────
VIDEO_WIDTH: int = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT: int = int(os.getenv("VIDEO_HEIGHT", "1920"))
VIDEO_FPS: int = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_CODEC: str = os.getenv("VIDEO_CODEC", "libx264")
AUDIO_CODEC: str = os.getenv("AUDIO_CODEC", "aac")
VIDEO_BITRATE: str = os.getenv("VIDEO_BITRATE", "4000k")
BACKGROUND_COLOR: tuple = (18, 18, 30)   # dark fallback background

# ── Output paths ──────────────────────────────────────────────────────────────
OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_FILE: Path = OUTPUT_DIR / "voiceover.mp3"
VIDEO_FILE: Path = OUTPUT_DIR / "final_video.mp4"
BG_VIDEO_FILE: Path = OUTPUT_DIR / "background.mp4"

# ── YouTube / OAuth ───────────────────────────────────────────────────────────
CLIENT_SECRETS_FILE: str = os.getenv("CLIENT_SECRETS_FILE", "client_secrets.json")
TOKEN_FILE: str = os.getenv("TOKEN_FILE", "token.json")
YOUTUBE_SCOPES: list = ["https://www.googleapis.com/auth/youtube.upload"]
DEFAULT_PRIVACY_STATUS: str = os.getenv("DEFAULT_PRIVACY_STATUS", "unlisted")  # "public" | "unlisted" | "private"
DEFAULT_CATEGORY_ID: str = os.getenv("DEFAULT_CATEGORY_ID", "22")              # 22 = People & Blogs

# ── Validation helper ──────────────────────────────────────────────────────────

def validate() -> None:
    """Warn about missing critical environment variables without crashing."""
    if not GROQ_API_KEY and not GEMINI_API_KEY:
        logger.warning("Neither GROQ_API_KEY nor GEMINI_API_KEY is set — script generation may fail.")
    if not PEXELS_API_KEY and not PIXABAY_API_KEY:
        logger.warning(
            "Neither PEXELS_API_KEY nor PIXABAY_API_KEY is set – "
            "the video editor will use a generated colour background instead of stock footage."
        )
    logger.info("Configuration loaded successfully.")
