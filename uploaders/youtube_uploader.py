"""
uploaders/youtube_uploader.py
------------------------------
YouTube Data API v3 uploader subclassing BaseUploader.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

import config
from uploaders.base import BaseUploader, UploadResult

logger = logging.getLogger("youtube_uploader")

_YOUTUBE_API_SERVICE = "youtube"
_YOUTUBE_API_VERSION = "v3"
_CHUNK_SIZE = 50 * 1024 * 1024


def _get_credentials() -> Credentials:
    token_path = Path(config.TOKEN_FILE)
    secrets_path = Path(config.CLIENT_SECRETS_FILE)
    scopes = config.YOUTUBE_SCOPES

    creds: Optional[Credentials] = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        except Exception as exc:
            logger.warning("Could not load cached YouTube token (%s).", exc)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except Exception as exc:
            logger.warning("YouTube token refresh failed (%s).", exc)
            creds = None

    if not creds or not creds.valid:
        if not secrets_path.exists():
            raise FileNotFoundError(f"client_secrets.json not found at '{secrets_path.resolve()}'.")

        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), scopes)
        creds = flow.run_local_server(port=0, prompt="consent", access_type="offline", open_browser=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


class YouTubeUploader(BaseUploader):
    """Handles video uploads to YouTube Shorts."""

    def __init__(self):
        super().__init__("youtube")

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        privacy_status: str | None = None,
        category_id: str | None = None,
        **kwargs: Any,
    ) -> UploadResult:
        video_path = Path(video_path)
        if not video_path.exists():
            return UploadResult("youtube", False, error_message=f"Video file missing: {video_path}")

        privacy_status = privacy_status or config.DEFAULT_PRIVACY_STATUS
        category_id = category_id or config.DEFAULT_CATEGORY_ID

        try:
            creds = _get_credentials()
            youtube = build(_YOUTUBE_API_SERVICE, _YOUTUBE_API_VERSION, credentials=creds)

            body = {
                "snippet": {
                    "title": title[:100],
                    "description": f"{description[:4800]}\n\n#Shorts",
                    "tags": tags[:20],
                    "categoryId": category_id,
                    "defaultLanguage": "en",
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            media = MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=_CHUNK_SIZE, resumable=True)
            request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info("YouTube upload progress: %d%%", int(status.progress() * 100))

            video_id = response["id"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            return UploadResult("youtube", True, post_id=video_id, post_url=video_url)

        except HttpError as exc:
            return UploadResult("youtube", False, error_message=f"HTTP {exc.resp.status}: {exc.content}")
        except Exception as exc:
            return UploadResult("youtube", False, error_message=str(exc))

    def upload_quote(self, quote_data: Dict[str, Any], **kwargs: Any) -> UploadResult:
        return UploadResult("youtube", False, error_message="YouTube is reserved for video uploads.")
