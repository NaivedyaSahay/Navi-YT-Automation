"""
uploaders/facebook_uploader.py
------------------------------
Facebook Page Reels uploader via Meta Graph API subclassing BaseUploader.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

import requests

import config
from metadata_adapter import MetadataAdapter
from uploaders.base import BaseUploader, UploadResult

logger = logging.getLogger("facebook_uploader")


class FacebookUploader(BaseUploader):
    """Handles video publishing to Facebook Page Reels."""

    def __init__(self):
        super().__init__("facebook")

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        **kwargs: Any,
    ) -> UploadResult:
        page_id = config.FB_PAGE_ID
        access_token = config.FB_PAGE_ACCESS_TOKEN

        if not page_id or not access_token:
            return UploadResult(
                "facebook",
                False,
                error_message="FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN is not configured in .env",
            )

        meta = MetadataAdapter.for_facebook(title, description, tags)

        try:
            # 1. Start Reel Upload Session
            start_url = f"https://graph.facebook.com/v19.0/{page_id}/video_reels"
            start_params = {
                "upload_phase": "start",
                "access_token": access_token,
            }
            start_res = requests.post(start_url, params=start_params, timeout=30)
            if start_res.status_code != 200:
                return UploadResult("facebook", False, error_message=f"Start session failed: {start_res.text}")

            start_data = start_res.json()
            video_id = start_data.get("video_id")
            upload_url = start_data.get("upload_url")

            # 2. Upload Video Binary
            file_size = os.path.getsize(video_path)
            upload_headers = {
                "Authorization": f"OAuth {access_token}",
                "offset": "0",
                "file_size": str(file_size),
            }
            with open(video_path, "rb") as vf:
                upload_res = requests.post(upload_url, headers=upload_headers, data=vf, timeout=300)
                if upload_res.status_code != 200:
                    return UploadResult("facebook", False, error_message=f"Binary transfer failed: {upload_res.text}")

            # 3. Publish Reel
            finish_url = f"https://graph.facebook.com/v19.0/{page_id}/video_reels"
            finish_params = {
                "access_token": access_token,
                "video_id": video_id,
                "upload_phase": "finish",
                "video_state": "PUBLISHED",
                "description": meta["description"],
            }
            finish_res = requests.post(finish_url, params=finish_params, timeout=30)
            if finish_res.status_code != 200:
                return UploadResult("facebook", False, error_message=f"Publish phase failed: {finish_res.text}")

            reel_url = f"https://www.facebook.com/reel/{video_id}"
            return UploadResult("facebook", True, post_id=video_id, post_url=reel_url)

        except Exception as exc:
            return UploadResult("facebook", False, error_message=str(exc))

    def upload_quote(self, quote_data: Dict[str, Any], **kwargs: Any) -> UploadResult:
        return UploadResult("facebook", False, error_message="Facebook target is configured for video Reels.")
