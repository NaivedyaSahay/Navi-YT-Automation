"""
uploaders/instagram_uploader.py
-------------------------------
Instagram Reels uploader via Meta Graph API subclassing BaseUploader.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict

import requests

import config
from metadata_adapter import MetadataAdapter
from uploaders.base import BaseUploader, UploadResult

logger = logging.getLogger("instagram_uploader")


class InstagramUploader(BaseUploader):
    """Handles video publishing to Instagram Reels."""

    def __init__(self):
        super().__init__("instagram")

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        video_url: str | None = None,
        **kwargs: Any,
    ) -> UploadResult:
        ig_user_id = config.IG_USER_ID
        access_token = config.IG_ACCESS_TOKEN

        if not ig_user_id or not access_token:
            return UploadResult(
                "instagram",
                False,
                error_message="IG_USER_ID or IG_ACCESS_TOKEN is not configured in .env",
            )

        meta = MetadataAdapter.for_instagram(title, description, tags)

        try:
            # 1. Create Media Container
            container_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
            container_params: dict[str, Any] = {
                "media_type": "REELS",
                "caption": meta["caption"],
                "access_token": access_token,
            }

            if video_url:
                container_params["video_url"] = video_url
                res = requests.post(container_url, data=container_params, timeout=30)
            else:
                # Direct upload container creation
                container_params["upload_type"] = "resumable"
                res = requests.post(container_url, data=container_params, timeout=30)

            if res.status_code != 200:
                return UploadResult("instagram", False, error_message=f"Container creation failed: {res.text}")

            creation_id = res.json().get("id")

            # 2. Wait for Instagram processing status
            status_url = f"https://graph.facebook.com/v19.0/{creation_id}"
            status_params = {
                "fields": "status_code",
                "access_token": access_token,
            }

            for _ in range(30):
                s_res = requests.get(status_url, params=status_params, timeout=15)
                if s_res.status_code == 200:
                    status_code = s_res.json().get("status_code")
                    if status_code == "FINISHED":
                        break
                    elif status_code == "ERROR":
                        return UploadResult("instagram", False, error_message="Instagram container processing error.")
                time.sleep(5)

            # 3. Publish Media Container
            publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
            publish_params = {
                "creation_id": creation_id,
                "access_token": access_token,
            }
            pub_res = requests.post(publish_url, data=publish_params, timeout=30)
            if pub_res.status_code != 200:
                return UploadResult("instagram", False, error_message=f"Publish failed: {pub_res.text}")

            post_id = pub_res.json().get("id")
            post_url = f"https://www.instagram.com/p/{post_id}/" if post_id else None
            return UploadResult("instagram", True, post_id=post_id, post_url=post_url)

        except Exception as exc:
            return UploadResult("instagram", False, error_message=str(exc))

    def upload_quote(self, quote_data: Dict[str, Any], **kwargs: Any) -> UploadResult:
        return UploadResult("instagram", False, error_message="Instagram target is configured for video Reels.")
