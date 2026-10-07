"""
uploader.py
-----------
Uploads a video file to YouTube using the YouTube Data API v3 with OAuth 2.0.

First run: Opens a browser window to request consent and caches the token
           in `token.json` for all future headless runs.

Subsequent runs: Reads the cached token, refreshes it automatically if expired,
                 and uploads without any user interaction.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

import config

logger = logging.getLogger("uploader")

# YouTube API resource types
_YOUTUBE_API_SERVICE = "youtube"
_YOUTUBE_API_VERSION = "v3"

# Resumable upload chunk size: 50 MB
_CHUNK_SIZE = 50 * 1024 * 1024


# ─────────────────────────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────────────────────────

def _is_ci_environment() -> bool:
    """Check if running in a non-interactive CI/CD environment (e.g. GitHub Actions)."""
    return any(
        os.getenv(var) in ("true", "1", "True")
        for var in ["CI", "GITHUB_ACTIONS", "CONTINUOUS_INTEGRATION"]
    )


def _get_credentials() -> Credentials:
    """
    Load OAuth2 credentials from the token cache, or run the initial
    browser-based consent flow and cache the result.

    Returns:
        A valid google.oauth2.credentials.Credentials object.

    Raises:
        FileNotFoundError: If client_secrets.json is missing.
        RuntimeError: If the OAuth flow fails or token is expired in CI.
    """
    token_path = Path(config.TOKEN_FILE)
    secrets_path = Path(config.CLIENT_SECRETS_FILE)
    scopes = config.YOUTUBE_SCOPES

    creds: Optional[Credentials] = None

    # ── Try loading cached token ──────────────────────────────────────────────
    if token_path.exists():
        try:
            content = token_path.read_text(encoding="utf-8").strip()
            # Handle accidental formatting/copy defects (e.g. missing opening curly brace or leading token key)
            if content.startswith('"ya29') or content.startswith('"token"') or not content.startswith('{'):
                if content.startswith('"token":'):
                    content = '{' + content
                elif content.startswith('"ya29'):
                    content = '{"token": ' + content
            if not content.endswith('}'):
                content = content + '}'
            import json
            data = json.loads(content)
            creds = Credentials.from_authorized_user_info(data, scopes)
            logger.info("Loaded cached OAuth token from: %s", token_path)
        except Exception:
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), scopes)
                logger.info("Loaded cached OAuth token from: %s", token_path)
            except Exception as exc:
                logger.warning("Could not load cached token (%s) – will re-authenticate.", exc)
                creds = None

    # ── Refresh expired token ─────────────────────────────────────────────────
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("OAuth token refreshed successfully.")
            _save_token(creds, token_path)
        except Exception as exc:
            logger.warning("Token refresh failed (%s) – will re-authenticate.", exc)
            creds = None

    # ── Initial OAuth flow (browser) ──────────────────────────────────────────
    if not creds or not creds.valid:
        if _is_ci_environment():
            raise RuntimeError(
                "OAuth token is missing, expired, or revoked in CI environment (GitHub Actions)!\n"
                "Action required:\n"
                "1. Publish your Google Cloud OAuth app to 'In Production' status to prevent 7-day token expiry.\n"
                "2. Run the script locally (`python main.py --no-upload` or `python uploader.py`) to sign in and generate a valid `token.json`.\n"
                "3. Update the GitHub Repository Secret `TOKEN_JSON` with the contents of the new `token.json` file."
            )

        if not secrets_path.exists():
            raise FileNotFoundError(
                f"client_secrets.json not found at '{secrets_path.resolve()}'.\n"
                "Download it from Google Cloud Console → APIs & Services → Credentials "
                "→ OAuth 2.0 Client IDs → Download JSON."
            )

        logger.info(
            "No valid credentials found. Starting OAuth consent flow.\n"
            "A browser window will open – sign in and grant access."
        )

        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), scopes)
            creds = flow.run_local_server(
                port=0,                          # pick any free port
                prompt="consent",
                access_type="offline",
                open_browser=True,
            )
        except Exception as exc:
            logger.error("OAuth flow failed: %s", exc)
            raise RuntimeError(f"OAuth authentication error: {exc}") from exc

        _save_token(creds, token_path)
        logger.info("Credentials cached at: %s", token_path)

    return creds


def _save_token(creds: Credentials, path: Path) -> None:
    """Persist credentials to disk so future runs are headless."""
    try:
        path.write_text(creds.to_json(), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not save token to %s: %s", path, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy_status: str | None = None,
    category_id: str | None = None,
) -> str:
    """
    Upload a video file to YouTube.

    Args:
        video_path:     Path to the MP4 file.
        title:          Video title (max 100 chars).
        description:    Video description (max 5000 chars).
        tags:           List of tag strings.
        privacy_status: "public" | "unlisted" | "private". Defaults to config.
        category_id:    YouTube category numeric ID. Defaults to config.

    Returns:
        The YouTube video ID of the uploaded video.

    Raises:
        FileNotFoundError: If the video file is missing.
        HttpError: On API-level errors.
        RuntimeError: On unexpected failures.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    privacy_status = privacy_status or config.DEFAULT_PRIVACY_STATUS
    category_id = category_id or config.DEFAULT_CATEGORY_ID

    logger.info("Authenticating with YouTube API …")
    creds = _get_credentials()
    youtube = build(_YOUTUBE_API_SERVICE, _YOUTUBE_API_VERSION, credentials=creds)

    # ── Build request body ────────────────────────────────────────────────────
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:500],          # API limit: 500 total tag chars
            "categoryId": category_id,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        chunksize=_CHUNK_SIZE,
        resumable=True,
    )

    logger.info(
        "Starting upload: '%s' (%s) → YouTube [%s]",
        title, privacy_status, video_path,
    )

    try:
        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                logger.info("Upload progress: %d%%", pct)

        video_id: str = response["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info("Upload complete! Video ID: %s | URL: %s", video_id, video_url)
        return video_id

    except HttpError as exc:
        logger.error("YouTube API error (HTTP %s): %s", exc.resp.status, exc.content)
        raise
    except Exception as exc:
        logger.error("Unexpected upload error: %s", exc)
        raise RuntimeError(f"Upload failed: {exc}") from exc
