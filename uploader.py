"""
uploader.py
-----------
Legacy entry wrapper delegating YouTube video uploads to the uploaders package.
"""

from __future__ import annotations

from pathlib import Path

from uploaders.youtube_uploader import YouTubeUploader


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy_status: str | None = None,
    category_id: str | None = None,
) -> str:
    """
    Backward-compatible wrapper for uploading a video to YouTube.
    """
    yt = YouTubeUploader()
    res = yt.upload_video(
        video_path=Path(video_path),
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status,
        category_id=category_id,
    )
    if not res.success:
        raise RuntimeError(f"YouTube upload failed: {res.error_message}")
    return res.post_id or ""
