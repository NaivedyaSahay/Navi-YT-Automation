"""
uploaders/threads_uploader.py
------------------------------
Meta Threads pure text post publisher subclassing BaseUploader.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import requests

import config
from metadata_adapter import MetadataAdapter
from uploaders.base import BaseUploader, UploadResult

logger = logging.getLogger("threads_uploader")


class ThreadsUploader(BaseUploader):
    """Handles pure text quote posting on Threads."""

    def __init__(self):
        super().__init__("threads")

    def upload_quote(self, quote_data: Dict[str, Any], **kwargs: Any) -> UploadResult:
        user_id = config.THREADS_USER_ID
        access_token = config.THREADS_ACCESS_TOKEN

        if not user_id or not access_token:
            return UploadResult(
                "threads",
                False,
                error_message="THREADS_USER_ID or THREADS_ACCESS_TOKEN is not configured in .env",
            )

        post_text = MetadataAdapter.for_threads_quote(quote_data)

        try:
            # 1. Create Media Container (TEXT type)
            container_url = f"https://graph.threads.net/v1.0/{user_id}/threads"
            container_payload = {
                "media_type": "TEXT",
                "text": post_text,
                "access_token": access_token,
            }
            res = requests.post(container_url, data=container_payload, timeout=30)
            if res.status_code != 200:
                return UploadResult("threads", False, error_message=f"Container creation failed: {res.text}")

            creation_id = res.json().get("id")

            # 2. Publish Container
            publish_url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
            publish_payload = {
                "creation_id": creation_id,
                "access_token": access_token,
            }
            pub_res = requests.post(publish_url, data=publish_payload, timeout=30)
            if pub_res.status_code != 200:
                return UploadResult("threads", False, error_message=f"Publish failed: {pub_res.text}")

            post_id = pub_res.json().get("id")
            post_url = f"https://www.threads.net/post/{post_id}" if post_id else None
            return UploadResult("threads", True, post_id=post_id, post_url=post_url)

        except Exception as exc:
            return UploadResult("threads", False, error_message=str(exc))

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        **kwargs: Any,
    ) -> UploadResult:
        return UploadResult("threads", False, error_message="Threads target is configured for pure text quote posts.")
