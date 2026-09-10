"""
uploaders/x_uploader.py
-----------------------
X (Twitter) pure text tweet publisher via Twitter API v2 subclassing BaseUploader.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import requests
from requests_oauthlib import OAuth1

import config
from metadata_adapter import MetadataAdapter
from uploaders.base import BaseUploader, UploadResult

logger = logging.getLogger("x_uploader")


class XUploader(BaseUploader):
    """Handles pure text quote tweet posting on X (Twitter)."""

    def __init__(self):
        super().__init__("x")

    def upload_quote(self, quote_data: Dict[str, Any], **kwargs: Any) -> UploadResult:
        api_key = config.TWITTER_API_KEY
        api_secret = config.TWITTER_API_SECRET
        access_token = config.TWITTER_ACCESS_TOKEN
        token_secret = config.TWITTER_ACCESS_TOKEN_SECRET

        if not all([api_key, api_secret, access_token, token_secret]):
            return UploadResult(
                "x",
                False,
                error_message="Twitter OAuth 1.0a credentials (API Key, Secret, Access Token, Secret) missing in .env",
            )

        tweet_text = MetadataAdapter.for_x_quote(quote_data)
        url = "https://api.twitter.com/2/tweets"

        auth = OAuth1(api_key, api_secret, access_token, token_secret)
        payload = {"text": tweet_text}

        try:
            res = requests.post(url, auth=auth, json=payload, timeout=30)
            if res.status_code not in (200, 201):
                return UploadResult("x", False, error_message=f"Tweet creation failed (HTTP {res.status_code}): {res.text}")

            data = res.json()
            tweet_id = data.get("data", {}).get("id")
            tweet_url = f"https://x.com/user/status/{tweet_id}" if tweet_id else None
            return UploadResult("x", True, post_id=tweet_id, post_url=tweet_url)

        except Exception as exc:
            return UploadResult("x", False, error_message=str(exc))

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        **kwargs: Any,
    ) -> UploadResult:
        return UploadResult("x", False, error_message="X target is configured for pure text quote posts.")
