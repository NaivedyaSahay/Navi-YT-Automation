"""
uploaders/pinterest_uploader.py
-------------------------------
Pinterest API v5 Video Pin uploader subclassing BaseUploader.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import requests

import config
from metadata_adapter import MetadataAdapter
from uploaders.base import BaseUploader, UploadResult

logger = logging.getLogger("pinterest_uploader")


class PinterestUploader(BaseUploader):
    """Handles video pin publishing to Pinterest using Pinterest API v5."""

    def __init__(self):
        super().__init__("pinterest")

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        **kwargs: Any,
    ) -> UploadResult:
        token = config.PINTEREST_ACCESS_TOKEN
        board_id = config.PINTEREST_BOARD_ID

        if not token or not board_id:
            return UploadResult(
                "pinterest",
                False,
                error_message="PINTEREST_ACCESS_TOKEN or PINTEREST_BOARD_ID is not configured in .env",
            )

        meta = MetadataAdapter.for_pinterest(title, description, tags)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            # 1. Register media container
            register_url = "https://api.pinterest.com/v5/media"
            register_payload = {"media_type": "video"}
            reg_res = requests.post(register_url, headers=headers, json=register_payload, timeout=30)
            if reg_res.status_code not in (200, 201):
                return UploadResult("pinterest", False, error_message=f"Media register failed: {reg_res.text}")

            reg_data = reg_res.json()
            media_id = reg_data.get("media_id")
            upload_url = reg_data.get("upload_url")
            upload_parameters = reg_data.get("upload_parameters", {})

            # 2. Upload video file to S3 storage returned by Pinterest
            with open(video_path, "rb") as vf:
                files = {"file": vf}
                up_res = requests.post(upload_url, data=upload_parameters, files=files, timeout=300)
                if up_res.status_code not in (200, 204):
                    return UploadResult("pinterest", False, error_message=f"File binary upload failed: {up_res.status_code}")

            # 3. Create Pin
            create_pin_url = "https://api.pinterest.com/v5/pins"
            pin_payload = {
                "board_id": board_id,
                "title": meta["title"],
                "description": meta["description"],
                "media_source": {
                    "source_type": "video_id",
                    "cover_image_url": None,
                    "media_id": media_id,
                },
            }
            pin_res = requests.post(create_pin_url, headers=headers, json=pin_payload, timeout=30)
            if pin_res.status_code not in (200, 201):
                return UploadResult("pinterest", False, error_message=f"Pin creation failed: {pin_res.text}")

            pin_data = pin_res.json()
            pin_id = pin_data.get("id")
            pin_url = f"https://www.pinterest.com/pin/{pin_id}/" if pin_id else None
            return UploadResult("pinterest", True, post_id=pin_id, post_url=pin_url)

        except Exception as exc:
            return UploadResult("pinterest", False, error_message=str(exc))

    def upload_quote(self, quote_data: Dict[str, Any], **kwargs: Any) -> UploadResult:
        return UploadResult("pinterest", False, error_message="Pinterest target is configured for video pins.")
