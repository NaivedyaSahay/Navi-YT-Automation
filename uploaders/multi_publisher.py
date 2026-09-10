"""
uploaders/multi_publisher.py
-----------------------------
Orchestrates multi-platform content publishing across YouTube, Pinterest, Facebook,
Instagram, X (Twitter), and Threads.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import config
from uploaders.base import BaseUploader, UploadResult
from uploaders.facebook_uploader import FacebookUploader
from uploaders.instagram_uploader import InstagramUploader
from uploaders.pinterest_uploader import PinterestUploader
from uploaders.threads_uploader import ThreadsUploader
from uploaders.x_uploader import XUploader
from uploaders.youtube_uploader import YouTubeUploader

logger = logging.getLogger("multi_publisher")


class MultiPublisher:
    """Manager for multi-platform distribution."""

    def __init__(self):
        self.uploaders: Dict[str, BaseUploader] = {
            "youtube": YouTubeUploader(),
            "pinterest": PinterestUploader(),
            "facebook": FacebookUploader(),
            "instagram": InstagramUploader(),
            "x": XUploader(),
            "threads": ThreadsUploader(),
        }

    def publish(
        self,
        video_path: Path | None = None,
        video_meta: Dict[str, Any] | None = None,
        quote_data: Dict[str, Any] | None = None,
        platforms: List[str] | None = None,
    ) -> Dict[str, UploadResult]:
        """
        Publish video to (youtube, pinterest, facebook, instagram) and pure text quotes to (x, threads).

        Args:
            video_path: Path to MP4 file.
            video_meta: Dict with title, description, tags.
            quote_data: Dict with quote text, author, formatted posts.
            platforms: List of platform names to target, or None for config default.

        Returns:
            Dict mapping platform name -> UploadResult.
        """
        target_platforms = [p.lower().strip() for p in (platforms or config.ENABLED_PLATFORMS)]
        results: Dict[str, UploadResult] = {}

        logger.info("Starting Multi-Platform Publishing to: %s", ", ".join(target_platforms))

        video_meta = video_meta or {}
        v_title = video_meta.get("title", "Navi Automation Video")
        v_desc = video_meta.get("description", "")
        v_tags = video_meta.get("tags", [])

        # ── 1. Video Distribution (YouTube, Pinterest, FB, IG) ───────────────────
        video_targets = {"youtube", "pinterest", "facebook", "instagram"}
        active_video_targets = [p for p in target_platforms if p in video_targets]

        if active_video_targets:
            if not video_path or not Path(video_path).exists():
                logger.warning("Video file not available – skipping video uploads.")
                for p in active_video_targets:
                    results[p] = UploadResult(p, False, error_message="Video file not generated or missing.")
            else:
                for p in active_video_targets:
                    uploader = self.uploaders.get(p)
                    if not uploader:
                        results[p] = UploadResult(p, False, error_message=f"Unknown uploader: {p}")
                        continue

                    logger.info("Publishing video → %s ...", p.upper())
                    try:
                        res = uploader.upload_video(Path(video_path), v_title, v_desc, v_tags)
                        results[p] = res
                        logger.info(str(res))
                    except Exception as exc:
                        logger.error("[%s] Unexpected error: %s", p.upper(), exc)
                        results[p] = UploadResult(p, False, error_message=str(exc))

        # ── 2. Pure Text Quote Distribution (X, Threads) ──────────────────────────
        quote_targets = {"x", "threads"}
        active_quote_targets = [p for p in target_platforms if p in quote_targets]

        if active_quote_targets:
            if not quote_data:
                logger.warning("Quote data not provided – skipping text quote posts.")
                for p in active_quote_targets:
                    results[p] = UploadResult(p, False, error_message="Quote data missing.")
            else:
                for p in active_quote_targets:
                    uploader = self.uploaders.get(p)
                    if not uploader:
                        results[p] = UploadResult(p, False, error_message=f"Unknown uploader: {p}")
                        continue

                    logger.info("Publishing pure text quote → %s ...", p.upper())
                    try:
                        res = uploader.upload_quote(quote_data)
                        results[p] = res
                        logger.info(str(res))
                    except Exception as exc:
                        logger.error("[%s] Unexpected error: %s", p.upper(), exc)
                        results[p] = UploadResult(p, False, error_message=str(exc))

        self._log_summary(results)
        return results

    def _log_summary(self, results: Dict[str, UploadResult]) -> None:
        logger.info("")
        logger.info("======================================================")
        logger.info("           MULTI-PLATFORM PUBLISHING SUMMARY          ")
        logger.info("======================================================")
        for platform, res in results.items():
            logger.info("%s", str(res))
        logger.info("======================================================")
